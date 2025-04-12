# import uuid
# import meilisearch
# import os
# import json
# from datetime import datetime
# from flask import current_app
# import logging
# from zchat.storage.api import add_document as storage_add_document, get_document as storage_get_document, update_document as storage_update_document, delete_document as storage_delete_document, search as storage_search

# # 全局客户端实例
# client = None

# def init_app(app):
#     """初始化MeiliSearch

#     Args:
#         app: Flask应用
#     """
#     host = app.config.get('MEILISEARCH_HOST', 'http://localhost:7700')
#     api_key = app.config.get('MEILISEARCH_KEY', None)
#     timeout = app.config.get('MEILISEARCH_TIMEOUT', 10)

#     app.logger.info(f"初始化MeiliSearch: {host}")

#     # 创建客户端实例
#     try:
#         ms_client = meilisearch.Client(
#             host,
#             api_key,
#             timeout=timeout
#         )
#         # 测试连接
#         ms_client.health()
#         app.meilisearch = ms_client

#         # 设置全局客户端
#         global client
#         client = ms_client

#         # 确保核心索引存在
#         _ensure_core_indexes(app)

#         app.logger.info("MeiliSearch初始化成功")
#     except Exception as e:
#         app.logger.error(f"MeiliSearch初始化失败: {str(e)}")
#         app.logger.warning("应用将继续运行，但搜索功能可能不可用")

# def _ensure_core_indexes(app):
#     """确保核心索引存在

#     Args:
#         app: Flask应用
#     """
#     try:
#         # 确保documents索引存在
#         try:
#             app.meilisearch.get_index('documents')
#             app.logger.debug("documents索引已存在")
#         except meilisearch.errors.MeiliSearchApiError as e:
#             if e.code == 'index_not_found':
#                 app.logger.info("创建documents索引")
#                 app.meilisearch.create_index('documents', {'primaryKey': 'id'})
#                 app.meilisearch.index('documents').update_settings({
#                     'searchableAttributes': [
#                         'content',
#                         'metadata.title',
#                         'metadata.description',
#                         'metadata.tags'
#                     ],
#                     'filterableAttributes': [
#                         'type',
#                         'metadata.category',
#                         'metadata.tags',
#                         'created_at'
#                     ],
#                     'sortableAttributes': [
#                         'created_at',
#                         'updated_at'
#                     ]
#                 })
#             else:
#                 raise
#     except Exception as e:
#         app.logger.error(f"核心索引创建失败: {str(e)}")
#         app.logger.error(f"异常类型: {type(e)}")

# def get_client():
#     """获取MeiliSearch客户端

#     Returns:
#         MeiliSearch客户端实例
#     """
#     if client is None:
#         # 如果客户端不存在，尝试从当前应用获取
#         if hasattr(current_app, 'meilisearch'):
#             return current_app.meilisearch
#         else:
#             current_app.logger.error("MeiliSearch客户端未初始化")
#             raise RuntimeError("MeiliSearch客户端未初始化")
#     return client

# def store_document(doc_type, content, metadata=None):
#     """存储文档到文档存储和MeiliSearch

#     Args:
#         doc_type: 文档类型
#         content: 文档内容
#         metadata: 文档元数据

#     Returns:
#         文档ID
#     """
#     # 创建文档记录
#     doc_id = str(uuid.uuid4())
#     created_at = datetime.now().isoformat()

#     document = {
#         'id': doc_id,
#         'type': doc_type,
#         'content': content,
#         'metadata': metadata or {},
#         'created_at': created_at,
#         'updated_at': created_at
#     }

#     # 存储到文档存储
#     try:
#         storage_add_document(current_app, 'documents', document)
#         current_app.logger.debug(f"已将文档 {doc_id} 存储到文档存储")
#     except Exception as e:
#         current_app.logger.error(f"文档存储错误: {str(e)}")
#         raise

#     # 索引到MeiliSearch
#     try:
#         meili_client = get_client()
#         meili_client.index('documents').add_documents([document])
#         current_app.logger.debug(f"已将文档 {doc_id} 索引到MeiliSearch")
#     except Exception as e:
#         current_app.logger.error(f"MeiliSearch索引错误: {str(e)}")
#         # MeiliSearch错误不应阻止整个操作，我们已经保存到文档存储了

#     return doc_id

# def get_document(doc_id):
#     """从文档存储获取文档

#     Args:
#         doc_id: 文档ID

#     Returns:
#         文档数据或None
#     """
#     try:
#         doc = storage_get_document(current_app, 'documents', doc_id)
#         return doc
#     except Exception as e:
#         current_app.logger.error(f"获取文档 {doc_id} 失败: {str(e)}")
#         return None

# def search_documents(query, filters=None, limit=20, offset=0):
#     """使用MeiliSearch搜索文档

#     Args:
#         query: 搜索查询
#         filters: 过滤条件
#         limit: 结果数量限制
#         offset: 结果起始偏移量

#     Returns:
#         搜索结果列表
#     """
#     try:
#         meili_client = get_client()

#         # 准备搜索参数
#         search_params = {
#             'limit': limit,
#             'offset': offset
#         }

#         # 添加过滤条件
#         if filters:
#             search_params['filter'] = filters

#         # 执行搜索
#         results = meili_client.index('documents').search(query, search_params)
#         current_app.logger.debug(f"MeiliSearch搜索成功: 找到 {len(results['hits'])} 条结果")
#         return {
#             'hits': results['hits'],
#             'total': results.get('estimatedTotalHits', 0),
#             'processing_time_ms': results.get('processingTimeMs', 0)
#         }
#     except Exception as e:
#         current_app.logger.error(f"MeiliSearch搜索错误: {str(e)}")
#         # 如果MeiliSearch搜索失败，回退到文档存储搜索
#         return fallback_search_storage(query, filters, limit, offset)

# def fallback_search_storage(query, filters=None, limit=20, offset=0):
#     """文档存储搜索回退方案

#     当MeiliSearch不可用时，使用文档存储进行基本搜索

#     Args:
#         query: 搜索查询
#         filters: 过滤条件
#         limit: 结果数量限制
#         offset: 结果起始偏移量

#     Returns:
#         搜索结果字典
#     """
#     current_app.logger.info(f"使用文档存储回退搜索: {query}")
#     try:
#         # 准备搜索选项
#         options = {
#             'limit': limit,
#             'offset': offset
#         }

#         # 添加过滤条件
#         if filters:
#             filter_list = []
#             for key, value in filters.items():
#                 filter_list.append(f"{key}={value}")
#             options['filter'] = filter_list

#         # 执行搜索
#         results = storage_search(current_app, 'documents', query, options)

#         return {
#             'hits': results.get('hits', []),
#             'total': results.get('estimatedTotalHits', 0),
#             'processing_time_ms': 0  # 文档存储不提供处理时间
#         }
#     except Exception as e:
#         current_app.logger.error(f"文档存储搜索错误: {str(e)}")
#         # 如果两种搜索都失败，返回空结果
#         return {'hits': [], 'total': 0, 'processing_time_ms': 0}

# def update_document(doc_id, content=None, metadata=None):
#     """更新文档存储和MeiliSearch中的文档

#     Args:
#         doc_id: 文档ID
#         content: 新的文档内容（可选）
#         metadata: 新的文档元数据（可选）

#     Returns:
#         更新后的文档或None
#     """
#     try:
#         # 获取当前文档
#         doc = get_document(doc_id)
#         if not doc:
#             current_app.logger.warning(f"要更新的文档 {doc_id} 不存在")
#             return None

#         # 更新字段
#         updated_doc = doc.copy()
#         if content is not None:
#             updated_doc['content'] = content
#         if metadata is not None:
#             updated_doc['metadata'] = metadata
#         updated_doc['updated_at'] = datetime.now().isoformat()

#         # 更新文档存储
#         storage_update_document(current_app, 'documents', updated_doc)
#         current_app.logger.debug(f"已更新文档存储中的文档 {doc_id}")

#         # 更新MeiliSearch
#         try:
#             meili_client = get_client()
#             meili_client.index('documents').update_documents([updated_doc])
#             current_app.logger.debug(f"已更新MeiliSearch中的文档 {doc_id}")
#         except Exception as e:
#             current_app.logger.error(f"MeiliSearch文档更新错误: {str(e)}")
#             # MeiliSearch更新失败不应阻止整个操作

#         return updated_doc
#     except Exception as e:
#         current_app.logger.error(f"更新文档 {doc_id} 失败: {str(e)}")
#         return None

# def delete_document(doc_id):
#     """删除文档存储和MeiliSearch中的文档

#     Args:
#         doc_id: 文档ID

#     Returns:
#         是否删除成功
#     """
#     storage_success = False
#     meili_success = False

#     # 从文档存储删除
#     try:
#         result = storage_delete_document(current_app, 'documents', doc_id)
#         storage_success = result.get('status') == 'success'

#         if storage_success:
#             current_app.logger.debug(f"已从文档存储中删除文档 {doc_id}")
#         else:
#             current_app.logger.warning(f"未能从文档存储中删除文档 {doc_id}，可能不存在")
#     except Exception as e:
#         current_app.logger.error(f"从文档存储删除文档 {doc_id} 失败: {str(e)}")

#     # 从MeiliSearch删除
#     try:
#         meili_client = get_client()
#         meili_client.index('documents').delete_document(doc_id)
#         meili_success = True
#         current_app.logger.debug(f"已从MeiliSearch中删除文档 {doc_id}")
#     except Exception as e:
#         current_app.logger.error(f"从MeiliSearch删除文档 {doc_id} 失败: {str(e)}")

#     # 任一成功即视为成功
#     return storage_success or meili_success

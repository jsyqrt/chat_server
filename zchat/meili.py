from meilisearch import Client
from flask import current_app, g
import json
import uuid
import time
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional
# Remove direct import of db module to avoid circular dependencies
# from . import db

# 全局MeiliSearch客户端
client = None

def init_app(app):
    """初始化MeiliSearch客户端

    Args:
        app: Flask应用实例
    """
    global client

    try:
        # 使用配置中的主机和密钥创建客户端
        client = Client(app.config['MEILISEARCH_HOST'], app.config['MEILISEARCH_KEY'])

        # 设置客户端超时时间
        client.timeout = app.config.get('MEILISEARCH_TIMEOUT', 5)

        # 健康检查
        try:
            health = client.health()
            app.logger.info(f"MeiliSearch健康状态: {health['status']}")
        except Exception as health_error:
            app.logger.warning(f"MeiliSearch健康检查失败: {str(health_error)}")
            # 继续尝试使用客户端，即使健康检查失败

        # 确保核心索引存在
        try:
            _ensure_core_indexes(app)
        except Exception as index_error:
            app.logger.error(f"创建核心索引失败: {str(index_error)}")
            # 继续使用客户端，即使索引创建失败

        # 将客户端添加到应用配置中，方便访问
        app.meilisearch = client

        app.logger.info("MeiliSearch初始化完成")

    except Exception as e:
        app.logger.error(f"MeiliSearch初始化失败: {str(e)}")
        app.logger.warning("应用将在没有MeiliSearch的情况下继续运行，搜索功能可能不可用")

def _ensure_core_indexes(app):
    """确保核心索引存在

    Args:
        app: Flask应用实例
    """
    try:
        # 获取现有索引
        indexes = client.get_indexes()

        # 处理索引，确保我们能获取到uid
        existing_index_uids = []
        for index in indexes:
            # 有些版本的MeiliSearch可能返回不同格式的索引对象
            # 所以我们需要兼容处理
            if hasattr(index, 'uid'):
                existing_index_uids.append(index.uid)
            elif isinstance(index, dict) and 'uid' in index:
                existing_index_uids.append(index['uid'])
            elif isinstance(index, str):
                existing_index_uids.append(index)

        # 定义核心索引及其配置
        core_indexes = {
            'documents': {
                'primaryKey': 'id',
                'searchableAttributes': ['content', 'metadata.title', 'metadata.tags'],
                'filterableAttributes': ['type', 'created_at', 'updated_at', 'metadata.user_id'],
                'sortableAttributes': ['created_at', 'updated_at']
            }
        }

        # 创建不存在的索引
        for index_name, settings in core_indexes.items():
            if index_name not in existing_index_uids:
                app.logger.info(f"创建索引: {index_name}")
                client.create_index(index_name, {'primaryKey': settings['primaryKey']})

                # 配置索引设置
                index = client.index(index_name)
                if 'searchableAttributes' in settings:
                    index.update_searchable_attributes(settings['searchableAttributes'])
                if 'filterableAttributes' in settings:
                    index.update_filterable_attributes(settings['filterableAttributes'])
                if 'sortableAttributes' in settings:
                    index.update_sortable_attributes(settings['sortableAttributes'])
    except Exception as e:
        app.logger.error(f"核心索引创建失败: {str(e)}")
        app.logger.error(f"异常类型: {type(e)}")

def get_client():
    """获取MeiliSearch客户端

    Returns:
        MeiliSearch客户端实例
    """
    if client is None:
        # 如果客户端不存在，尝试从当前应用获取
        if hasattr(current_app, 'meilisearch'):
            return current_app.meilisearch
        else:
            current_app.logger.error("MeiliSearch客户端未初始化")
            raise RuntimeError("MeiliSearch客户端未初始化")
    return client

def store_document(doc_type, content, metadata=None):
    """存储文档到MongoDB和MeiliSearch

    Args:
        doc_type: 文档类型
        content: 文档内容
        metadata: 文档元数据

    Returns:
        文档ID
    """
    # 创建文档记录
    doc_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()

    document = {
        'id': doc_id,
        'type': doc_type,
        'content': content,
        'metadata': metadata or {},
        'created_at': created_at,
        'updated_at': created_at
    }

    # 存储到MongoDB
    try:
        # Import db module here to avoid circular imports
        from . import db
        collection = db.get_documents_collection()
        collection.insert_one(document)
        current_app.logger.debug(f"已将文档 {doc_id} 存储到MongoDB")
    except Exception as e:
        current_app.logger.error(f"MongoDB存储错误: {str(e)}")
        raise

    # 索引到MeiliSearch
    try:
        meili_client = get_client()
        # 为了防止MongoDB _id字段的序列化问题，创建副本
        meili_doc = document.copy()
        meili_client.index('documents').add_documents([meili_doc])
        current_app.logger.debug(f"已将文档 {doc_id} 索引到MeiliSearch")
    except Exception as e:
        current_app.logger.error(f"MeiliSearch索引错误: {str(e)}")
        # MeiliSearch错误不应阻止整个操作，我们已经保存到MongoDB了

    return doc_id

def get_document(doc_id):
    """从MongoDB获取文档

    Args:
        doc_id: 文档ID

    Returns:
        文档数据或None
    """
    try:
        # Import db module here to avoid circular imports
        from . import db
        collection = db.get_documents_collection()
        doc = collection.find_one({'id': doc_id})
        if doc and '_id' in doc:
            # 移除MongoDB _id字段
            doc.pop('_id')
        return doc
    except Exception as e:
        current_app.logger.error(f"获取文档 {doc_id} 失败: {str(e)}")
        return None

def search_documents(query, filters=None, limit=20, offset=0):
    """使用MeiliSearch搜索文档

    Args:
        query: 搜索查询
        filters: 过滤条件
        limit: 结果数量限制
        offset: 结果起始偏移量

    Returns:
        搜索结果列表
    """
    try:
        meili_client = get_client()

        # 准备搜索参数
        search_params = {
            'limit': limit,
            'offset': offset
        }

        # 添加过滤条件
        if filters:
            search_params['filter'] = filters

        # 执行搜索
        results = meili_client.index('documents').search(query, search_params)
        current_app.logger.debug(f"MeiliSearch搜索成功: 找到 {len(results['hits'])} 条结果")
        return {
            'hits': results['hits'],
            'total': results.get('estimatedTotalHits', 0),
            'processing_time_ms': results.get('processingTimeMs', 0)
        }
    except Exception as e:
        current_app.logger.error(f"MeiliSearch搜索错误: {str(e)}")
        # 如果MeiliSearch搜索失败，回退到MongoDB
        return fallback_search_mongodb(query, filters, limit, offset)

def fallback_search_mongodb(query, filters=None, limit=20, offset=0):
    """MongoDB搜索回退方案

    当MeiliSearch不可用时，使用MongoDB进行基本文本搜索

    Args:
        query: 搜索查询
        filters: 过滤条件（MongoDB格式）
        limit: 结果数量限制
        offset: 结果起始偏移量

    Returns:
        搜索结果字典
    """
    current_app.logger.info(f"使用MongoDB回退搜索: {query}")
    try:
        # Import db module here to avoid circular imports
        from . import db
        collection = db.get_documents_collection()

        # 构建搜索查询
        search_query = {'$text': {'$search': query}}
        if filters:
            for key, value in filters.items():
                search_query[key] = value

        # 确保文本索引存在
        try:
            # 检查是否已存在文本索引
            indexes = collection.index_information()
            has_text_index = any('text' in index.get('key', []) for index in indexes.values())

            if not has_text_index:
                current_app.logger.info("在MongoDB documents集合上创建文本索引")
                collection.create_index([('content', 'text'), ('metadata.title', 'text')])
        except Exception as e:
            current_app.logger.warning(f"创建MongoDB文本索引失败: {str(e)}")

        # 执行搜索
        total = collection.count_documents(search_query)
        cursor = collection.find(search_query).skip(offset).limit(limit)

        # 准备结果
        hits = []
        for doc in cursor:
            if '_id' in doc:
                # 将ObjectId转换为字符串
                doc['_id'] = str(doc['_id'])
            hits.append(doc)

        return {
            'hits': hits,
            'total': total,
            'processing_time_ms': 0  # MongoDB不提供处理时间
        }
    except Exception as e:
        current_app.logger.error(f"MongoDB搜索错误: {str(e)}")
        # 如果两种搜索都失败，返回空结果
        return {'hits': [], 'total': 0, 'processing_time_ms': 0}

def update_document(doc_id, content=None, metadata=None):
    """更新MongoDB和MeiliSearch中的文档

    Args:
        doc_id: 文档ID
        content: 新的文档内容（可选）
        metadata: 新的文档元数据（可选）

    Returns:
        更新后的文档或None
    """
    try:
        # Import db module here to avoid circular imports
        from . import db
        collection = db.get_documents_collection()

        # 准备更新数据
        update_data = {'updated_at': datetime.now().isoformat()}
        if content is not None:
            update_data['content'] = content
        if metadata is not None:
            update_data['metadata'] = metadata

        # 更新MongoDB
        result = collection.update_one({'id': doc_id}, {'$set': update_data})
        if result.matched_count == 0:
            current_app.logger.warning(f"未找到要更新的文档: {doc_id}")
            return None

        # 获取更新后的完整文档
        updated_doc = collection.find_one({'id': doc_id})
        if updated_doc:
            # 删除MongoDB _id字段
            meili_doc = updated_doc.copy()
            if '_id' in meili_doc:
                del meili_doc['_id']

            # 更新MeiliSearch
            try:
                meili_client = get_client()
                meili_client.index('documents').update_documents([meili_doc])
                current_app.logger.debug(f"已在MeiliSearch中更新文档 {doc_id}")
            except Exception as e:
                current_app.logger.error(f"MeiliSearch更新错误: {str(e)}")
                # MeiliSearch错误不应阻止整个操作

            return updated_doc
        else:
            current_app.logger.warning(f"更新后无法检索文档: {doc_id}")
            return None
    except Exception as e:
        current_app.logger.error(f"更新文档 {doc_id} 失败: {str(e)}")
        return None

def delete_document(doc_id):
    """删除MongoDB和MeiliSearch中的文档

    Args:
        doc_id: 文档ID

    Returns:
        操作成功的布尔值
    """
    try:
        # 从MongoDB删除
        # Import db module here to avoid circular imports
        from . import db
        collection = db.get_documents_collection()
        result = collection.delete_one({'id': doc_id})
        mongodb_success = result.deleted_count > 0

        if mongodb_success:
            current_app.logger.debug(f"已从MongoDB中删除文档 {doc_id}")
        else:
            current_app.logger.warning(f"未能从MongoDB中删除文档 {doc_id}，可能不存在")

        # 从MeiliSearch删除
        try:
            meili_client = get_client()
            meili_client.index('documents').delete_document(doc_id)
            current_app.logger.debug(f"已从MeiliSearch中删除文档 {doc_id}")
            meili_success = True
        except Exception as e:
            current_app.logger.error(f"MeiliSearch删除错误: {str(e)}")
            meili_success = False

        return mongodb_success
    except Exception as e:
        current_app.logger.error(f"删除文档 {doc_id} 失败: {str(e)}")
        return False

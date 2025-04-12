import json
import time
import logging
import threading
from typing import Dict, List, Any, Optional, Union
import pymongo
from bson.objectid import ObjectId
from .abstract import DocumentStore

class MongoDBDocumentStore(DocumentStore):
    """基于MongoDB的文档存储实现，针对文档存储场景优化"""

    def __init__(self, uri: str, db_name: str):
        """初始化MongoDB存储

        Args:
            uri: MongoDB连接URI
            db_name: 数据库名称
        """
        self.uri = uri
        self.db_name = db_name
        self.local = threading.local()  # 使用线程本地存储，但主要用于兼容性
        self.lock = threading.RLock()   # 使用可重入锁
        self.logger = logging.getLogger(__name__)

        # 进程级别的共享连接 (连接池) - 在初始化时直接创建
        self._client = pymongo.MongoClient(
            uri,
            w=1,                # 等待主节点确认写入
            journal=True,       # 确保写入操作记录到journal
            retryWrites=True,   # 启用写入重试
            maxPoolSize=10,     # 限制每个进程的最大连接数
            minPoolSize=1,      # 保持至少一个连接活跃
            maxIdleTimeMS=30000 # 空闲连接30秒后关闭
        )
        self._db = self._client[db_name]
        self.logger.info(f"已初始化MongoDB连接池: {db_name}")

        # 跟踪当前请求的写入操作，用于确保持久化
        self._pending_writes = 0
        self._last_sync_time = time.time()

        # 初始化数据库
        self._init_db()

    def _get_connection(self):
        """获取数据库连接，始终使用连接池中的连接

        Returns:
            MongoDB数据库连接
        """
        # 直接返回进程级别的共享连接，不再使用线程本地存储
        return self._db

    def _init_db(self):
        """初始化数据库"""
        db = self._get_connection()

        # 检查并创建collections元集合
        if "meta_collections" not in db.list_collection_names():
            db.create_collection("meta_collections")
            db["meta_collections"].create_index("name", unique=True)

    def create_collection(self, collection_name: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建一个新的集合

        Args:
            collection_name: 集合名称
            options: 集合选项，可以包含 primaryKey 和 indexedFields

        Returns:
            包含操作状态的字典
        """
        db = self._get_connection()

        if options is None:
            options = {}

        primary_key = options.get('primaryKey', 'id')
        indexed_fields = options.get('indexedFields', [])

        with self.lock:
            try:
                # 检查集合是否已存在
                if db["meta_collections"].find_one({"name": collection_name}):
                    return {"status": "error", "message": f"Collection {collection_name} already exists"}

                # 创建实际的集合
                db.create_collection(collection_name)

                # 添加索引
                for field in indexed_fields:
                    db[collection_name].create_index(field)

                # 主键总是被索引
                if primary_key != "_id":  # MongoDB的默认主键是_id
                    db[collection_name].create_index(primary_key, unique=True)

                # 记录集合元数据
                now = time.time()
                meta_data = {
                    "name": collection_name,
                    "primary_key": primary_key,
                    "created_at": now,
                    "options": options,
                    "indexed_fields": indexed_fields
                }
                db["meta_collections"].insert_one(meta_data)

                return {"status": "success", "collectionName": collection_name}
            except Exception as e:
                self.logger.error(f"创建集合{collection_name}失败: {str(e)}")
                return {"status": "error", "message": str(e)}

    def delete_collection(self, collection_name: str) -> Dict[str, Any]:
        """删除一个集合及其所有文档

        Args:
            collection_name: 集合名称

        Returns:
            包含操作状态的字典
        """
        db = self._get_connection()

        with self.lock:
            try:
                # 检查集合是否存在
                if not db["meta_collections"].find_one({"name": collection_name}):
                    return {"status": "error", "message": f"Collection {collection_name} does not exist"}

                # 删除集合
                db.drop_collection(collection_name)

                # 删除元数据
                db["meta_collections"].delete_one({"name": collection_name})

                return {"status": "success", "message": f"Collection {collection_name} deleted"}
            except Exception as e:
                self.logger.error(f"删除集合{collection_name}失败: {str(e)}")
                return {"status": "error", "message": str(e)}

    def list_collections(self) -> Dict[str, List[Dict[str, Any]]]:
        """列出所有集合

        Returns:
            包含集合列表的字典
        """
        db = self._get_connection()

        with self.lock:
            collections = []
            for collection in db["meta_collections"].find():
                collections.append({
                    'name': collection['name'],
                    'primaryKey': collection['primary_key'],
                    'createdAt': collection['created_at'],
                    'options': collection['options']
                })

            return {"collections": collections}

    def _get_collection_primary_key(self, collection_name: str) -> Optional[str]:
        """获取集合的主键

        Args:
            collection_name: 集合名称

        Returns:
            主键名称，如果集合不存在则为None
        """
        db = self._get_connection()

        collection_meta = db["meta_collections"].find_one({"name": collection_name})
        if collection_meta is None:
            return None

        return collection_meta["primary_key"]

    def _get_indexed_fields(self, collection_name: str) -> List[str]:
        """获取集合的索引字段

        Args:
            collection_name: 集合名称

        Returns:
            索引字段列表
        """
        db = self._get_connection()

        collection_meta = db["meta_collections"].find_one({"name": collection_name})
        if collection_meta is None:
            return []

        return collection_meta.get("indexed_fields", [])

    def add_document(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """向集合中添加文档

        Args:
            collection_name: 集合名称
            document: 要添加的文档

        Returns:
            包含操作状态的字典
        """
        db = self._get_connection()

        # 获取集合的主键
        primary_key = self._get_collection_primary_key(collection_name)
        if not primary_key:
            # 如果集合不存在，则创建它
            self.create_collection(collection_name)
            primary_key = 'id'  # 默认主键

        # 确保文档有主键
        if primary_key not in document:
            return {"status": "error", "message": f"Document must have primary key {primary_key}"}

        doc_id = str(document[primary_key])

        # 准备文档
        now = time.time()
        doc_with_timestamps = document.copy()
        if 'created_at' not in doc_with_timestamps:
            doc_with_timestamps['created_at'] = now
        if 'updated_at' not in doc_with_timestamps:
            doc_with_timestamps['updated_at'] = now

        # MongoDB的特殊处理: 如果主键不是_id，则设置_id等于主键值，但同时保留原始主键
        mongo_doc = doc_with_timestamps.copy()
        if primary_key != "_id":
            mongo_doc["_id"] = doc_id

        with self.lock:
            try:
                # 插入文档并增加等待持久化的写入计数
                result = db[collection_name].insert_one(mongo_doc)
                self._pending_writes += 1

                # 每10次写入操作或30秒后强制同步一次
                if self._pending_writes >= 10 or (time.time() - self._last_sync_time) > 30:
                    self.ensure_writes()

                return {"status": "success", "documentId": doc_id}
            except pymongo.errors.DuplicateKeyError:
                return {"status": "error", "message": f"Document with id {doc_id} already exists"}
            except Exception as e:
                self.logger.error(f"添加文档到{collection_name}失败: {str(e)}")
                return {"status": "error", "message": str(e)}

    def update_document(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """更新集合中的文档

        Args:
            collection_name: 集合名称
            document: 要更新的文档

        Returns:
            包含操作状态的字典
        """
        db = self._get_connection()

        # 获取集合的主键
        primary_key = self._get_collection_primary_key(collection_name)
        if not primary_key:
            return {"status": "error", "message": f"Collection {collection_name} does not exist"}

        # 确保文档有主键
        if primary_key not in document:
            return {"status": "error", "message": f"Document must have primary key {primary_key}"}

        doc_id = str(document[primary_key])

        with self.lock:
            try:
                # 构建查询条件
                query = {"_id": doc_id} if primary_key == "_id" else {primary_key: doc_id}

                # 检查文档是否存在
                existing_doc = db[collection_name].find_one(query)
                if existing_doc is None:
                    return self.add_document(collection_name, document)

                # 更新时间戳
                now = time.time()
                document['updated_at'] = now

                # 使用$set而不是替换整个文档，这样我们只更新提供的字段
                db[collection_name].update_one(
                    query,
                    {"$set": document}
                )

                # 增加等待持久化的写入计数
                self._pending_writes += 1

                # 每10次写入操作或30秒后强制同步一次
                if self._pending_writes >= 10 or (time.time() - self._last_sync_time) > 30:
                    self.ensure_writes()

                return {"status": "success", "documentId": doc_id}
            except Exception as e:
                self.logger.error(f"更新{collection_name}中的文档失败: {str(e)}")
                return {"status": "error", "message": str(e)}

    def get_document(self, collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """通过ID获取文档

        Args:
            collection_name: 集合名称
            doc_id: 文档ID

        Returns:
            文档，如果不存在则为None
        """
        db = self._get_connection()

        # 获取集合的主键
        primary_key = self._get_collection_primary_key(collection_name)
        if not primary_key:
            return None

        with self.lock:
            try:
                # 构建查询条件
                query = {"_id": doc_id} if primary_key == "_id" else {primary_key: doc_id}

                # 查询文档
                document = db[collection_name].find_one(query)

                if document is None:
                    return None

                # 移除MongoDB的_id字段，除非它是主键
                if primary_key != "_id" and "_id" in document:
                    document.pop("_id")

                return document
            except Exception as e:
                self.logger.error(f"获取{collection_name}中的文档{doc_id}失败: {str(e)}")
                return None

    def delete_document(self, collection_name: str, doc_id: str) -> Dict[str, Any]:
        """删除文档

        Args:
            collection_name: 集合名称
            doc_id: 文档ID

        Returns:
            包含操作状态的字典
        """
        db = self._get_connection()

        # 获取集合的主键
        primary_key = self._get_collection_primary_key(collection_name)
        if not primary_key:
            return {"status": "error", "message": f"Collection {collection_name} does not exist"}

        with self.lock:
            try:
                # 构建查询条件
                query = {"_id": doc_id} if primary_key == "_id" else {primary_key: doc_id}

                # 删除文档
                result = db[collection_name].delete_one(query)

                if result.deleted_count == 0:
                    return {"status": "error", "message": f"Document with id {doc_id} does not exist"}

                return {"status": "success", "message": f"Document with id {doc_id} deleted"}
            except Exception as e:
                self.logger.error(f"删除{collection_name}中的文档{doc_id}失败: {str(e)}")
                return {"status": "error", "message": str(e)}

    def search(self, collection_name: str, query: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """搜索文档

        Args:
            collection_name: 集合名称
            query: 搜索查询
            options: 搜索选项，可以包含 filter, sort, limit, offset

        Returns:
            包含搜索结果的字典
        """
        db = self._get_connection()

        if options is None:
            options = {}

        filters = options.get('filter', [])
        sort_options = options.get('sort', [])

        # 确保 limit 和 offset 是整数
        try:
            limit = int(options.get('limit', 20))
        except (ValueError, TypeError):
            limit = 20

        try:
            offset = int(options.get('offset', 0))
        except (ValueError, TypeError):
            offset = 0

        with self.lock:
            try:
                # 构建MongoDB查询
                mongo_query = {}

                # 处理过滤器
                if filters:
                    for filter_expr in filters:
                        if '=' in filter_expr:
                            field, value = filter_expr.split('=', 1)
                        elif ':' in filter_expr:
                            field, value = filter_expr.split(':', 1)
                        else:
                            continue

                        field = field.strip()
                        value = value.strip()

                        # 处理嵌套字段
                        if '.' in field:
                            mongo_query[field] = value
                        else:
                            mongo_query[field] = value

                # 处理文本查询
                if query:
                    # MongoDB中使用$text需要先创建文本索引
                    # 这里使用简单的正则表达式模糊匹配
                    mongo_query["$or"] = [
                        {"_id": {"$regex": query, "$options": "i"}},
                        {"content": {"$regex": query, "$options": "i"}}
                    ]

                # 处理排序
                mongo_sort = []
                if sort_options:
                    for sort_expr in sort_options:
                        if ':' in sort_expr:
                            field, direction = sort_expr.split(':')
                            mongo_sort.append((field, -1 if direction.lower() == "desc" else 1))
                        else:
                            mongo_sort.append((sort_expr, 1))  # 默认升序

                # 执行查询
                cursor = db[collection_name].find(mongo_query)

                # 应用排序
                if mongo_sort:
                    cursor = cursor.sort(mongo_sort)

                # 应用分页
                total_count = db[collection_name].count_documents(mongo_query)
                cursor = cursor.skip(offset).limit(limit)

                # 处理结果
                hits = []
                for doc in cursor:
                    # 移除MongoDB的_id字段，除非它是我们的主键
                    primary_key = self._get_collection_primary_key(collection_name)
                    if primary_key != "_id" and "_id" in doc:
                        doc_copy = doc.copy()
                        doc_copy.pop("_id")
                        hits.append(doc_copy)
                    else:
                        hits.append(doc)

                return {
                    "hits": hits,
                    "offset": offset,
                    "limit": limit,
                    "estimatedTotalHits": total_count,
                    "query": query,
                    "processingTimeMs": 0  # 不计算处理时间
                }
            except Exception as e:
                self.logger.error(f"搜索{collection_name}集合失败: {str(e)}")
                return {
                    "hits": [],
                    "offset": offset,
                    "limit": limit,
                    "estimatedTotalHits": 0,
                    "query": query,
                    "processingTimeMs": 0,
                    "error": str(e)
                }

    def ensure_writes(self):
        """确保所有挂起的写入操作已完成并同步到磁盘

        在HTTP请求结束前调用此方法，确保所有写入都已持久化
        """
        if self._pending_writes > 0:
            try:
                # 对主数据库执行fsync命令以刷新写入
                admin_db = self._client.admin
                admin_db.command('fsync')
                self.logger.debug(f"MongoDB写入已同步到磁盘 ({self._pending_writes}个操作)")
                # 重置计数器和时间戳
                self._pending_writes = 0
                self._last_sync_time = time.time()
            except Exception as e:
                self.logger.warning(f"MongoDB同步写入失败: {str(e)}")

    def close(self):
        """关闭数据库连接

        注意：此方法不应在每个请求后调用，
        而是在应用关闭或进程退出时调用一次。
        """
        try:
            # 首先确保所有写入已完成
            self.ensure_writes()

            # 然后关闭连接
            if self._client is not None:
                self._client.close()
                self._client = None
                self._db = None
                self.logger.info("MongoDB连接池已关闭")
        except Exception as e:
            self.logger.error(f"关闭MongoDB连接失败: {str(e)}")
            # 不要在这里抛出异常，以免影响应用运行
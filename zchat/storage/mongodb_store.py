import json
import time
import threading
import logging
import weakref
from typing import Dict, List, Any, Optional, Union
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.read_preferences import ReadPreference
from pymongo.errors import ConnectionFailure, DuplicateKeyError, OperationFailure
from .abstract import DocumentStore

# 全局连接池
class MongoConnectionPool:
    """MongoDB连接池，在应用级别管理连接"""

    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MongoConnectionPool, cls).__new__(cls)
                cls._instance.clients = {}
                cls._instance.logger = logging.getLogger(__name__)
                # 保持连接池的实例引用计数
                cls._instance.ref_counts = {}
        return cls._instance

    def get_client(self, connection_key, conn_params):
        """获取或创建MongoDB客户端连接

        Args:
            connection_key: 连接的唯一标识符（通常是host:port:db_name）
            conn_params: MongoDB连接参数

        Returns:
            MongoDB客户端连接
        """
        with self._lock:
            if connection_key not in self.clients:
                self.logger.debug(f"创建新的MongoDB连接: {connection_key}")
                client = MongoClient(**conn_params)
                # 验证连接是否成功
                client.admin.command('ping')
                self.clients[connection_key] = client
                self.ref_counts[connection_key] = 1
                self.logger.info(f"MongoDB连接成功: {connection_key}")
            else:
                self.ref_counts[connection_key] += 1
                self.logger.debug(f"复用MongoDB连接: {connection_key} (引用计数: {self.ref_counts[connection_key]})")

            return self.clients[connection_key]

    def release_client(self, connection_key):
        """释放MongoDB客户端连接

        Args:
            connection_key: 连接的唯一标识符
        """
        with self._lock:
            if connection_key in self.ref_counts:
                self.ref_counts[connection_key] -= 1
                self.logger.debug(f"释放MongoDB连接: {connection_key} (引用计数: {self.ref_counts[connection_key]})")

                # 如果引用计数为0，关闭并移除连接
                if self.ref_counts[connection_key] <= 0:
                    if connection_key in self.clients:
                        self.logger.info(f"关闭MongoDB连接: {connection_key}")
                        self.clients[connection_key].close()
                        del self.clients[connection_key]
                    if connection_key in self.ref_counts:
                        del self.ref_counts[connection_key]

    def close_all(self):
        """关闭所有MongoDB连接"""
        with self._lock:
            for key, client in list(self.clients.items()):
                self.logger.info(f"关闭MongoDB连接: {key}")
                client.close()
            self.clients.clear()
            self.ref_counts.clear()

    def get_stats(self):
        """获取连接池统计信息"""
        with self._lock:
            stats = {
                "total_connections": len(self.clients),
                "connections": {}
            }
            for key, count in self.ref_counts.items():
                stats["connections"][key] = {
                    "ref_count": count
                }
            return stats

# 初始化全局连接池
mongo_pool = MongoConnectionPool()

class MongoDBDocumentStore(DocumentStore):
    """基于MongoDB的文档存储实现"""

    def __init__(self, host: str = 'localhost', port: int = 27017,
                 username: str = None, password: str = None,
                 db_name: str = 'zchat', auth_source: str = 'admin',
                 replica_set: str = None, tls: bool = False,
                 max_pool_size: int = 100, min_pool_size: int = 10,
                 max_idle_time_ms: int = 10000,
                 server_selection_timeout_ms: int = 30000,
                 connect_timeout_ms: int = 20000,
                 socket_timeout_ms: int = 20000,
                 read_preference: str = 'primary'):
        """初始化MongoDB存储

        Args:
            host: MongoDB服务器地址或连接字符串
            port: MongoDB服务器端口
            username: 用户名
            password: 密码
            db_name: 数据库名称
            auth_source: 认证数据库
            replica_set: 副本集名称（如果适用）
            tls: 是否使用TLS连接
            max_pool_size: 连接池最大连接数
            min_pool_size: 连接池最小连接数
            max_idle_time_ms: 连接最大空闲时间(毫秒)
            server_selection_timeout_ms: 服务器选择超时时间(毫秒)
            connect_timeout_ms: 连接超时时间(毫秒)
            socket_timeout_ms: 套接字超时时间(毫秒)
            read_preference: 读取首选项('primary', 'primaryPreferred', 'secondary', 'secondaryPreferred', 'nearest')
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.db_name = db_name
        self.auth_source = auth_source
        self.replica_set = replica_set
        self.tls = tls

        # 连接池配置
        self.max_pool_size = max_pool_size
        self.min_pool_size = min_pool_size
        self.max_idle_time_ms = max_idle_time_ms
        self.server_selection_timeout_ms = server_selection_timeout_ms
        self.connect_timeout_ms = connect_timeout_ms
        self.socket_timeout_ms = socket_timeout_ms
        self.read_preference = read_preference

        # 读取首选项映射
        self.read_preference_map = {
            'primary': ReadPreference.PRIMARY,
            'primaryPreferred': ReadPreference.PRIMARY_PREFERRED,
            'secondary': ReadPreference.SECONDARY,
            'secondaryPreferred': ReadPreference.SECONDARY_PREFERRED,
            'nearest': ReadPreference.NEAREST
        }

        # 创建连接标识符
        self.connection_key = f"{host}:{port}/{db_name}"

        # 替换线程本地存储为直接client引用
        self.client = None

        self.lock = threading.RLock()   # 使用可重入锁
        self.logger = logging.getLogger(__name__)

        # 创建析构器，确保在对象被回收时释放连接
        self._finalizer = weakref.finalize(self, self._cleanup, self.connection_key)

        # 初始化连接和数据库
        self._init_db()

    def _cleanup(self, connection_key):
        """清理资源的析构方法"""
        mongo_pool.release_client(connection_key)

    def _get_client(self):
        """获取或创建MongoDB客户端连接"""
        if self.client is None:
            try:
                # 构建连接参数
                conn_params = {
                    'host': self.host,
                    'port': self.port,
                    # 连接池设置
                    'maxPoolSize': self.max_pool_size,
                    'minPoolSize': self.min_pool_size,
                    'maxIdleTimeMS': self.max_idle_time_ms,
                    # 超时设置
                    'serverSelectionTimeoutMS': self.server_selection_timeout_ms,
                    'connectTimeoutMS': self.connect_timeout_ms,
                    'socketTimeoutMS': self.socket_timeout_ms,
                    # 读取首选项 - 使用字符串
                    'readPreference': self.read_preference,
                    # 连接池选项
                    'retryWrites': True,
                    'retryReads': True,
                    # 添加应用名称以便在MongoDB日志中识别
                    'appName': 'zchat-app'
                }

                # 如果提供了用户名和密码，添加认证信息
                if self.username and self.password:
                    conn_params.update({
                        'username': self.username,
                        'password': self.password,
                        'authSource': self.auth_source
                    })

                # 如果配置了副本集，添加副本集配置
                if self.replica_set:
                    conn_params['replicaSet'] = self.replica_set

                # TLS配置
                if self.tls:
                    conn_params['tls'] = True

                # 从连接池获取连接
                self.client = mongo_pool.get_client(self.connection_key, conn_params)

            except ConnectionFailure as e:
                self.logger.error(f"MongoDB连接失败: {str(e)}")
                raise
            except Exception as e:
                self.logger.error(f"MongoDB初始化失败: {str(e)}")
                raise

        return self.client

    def _get_db(self):
        """获取数据库连接"""
        client = self._get_client()
        return client[self.db_name]

    def _init_db(self):
        """初始化数据库结构"""
        try:
            # 获取数据库连接
            db = self._get_db()

            # 确保collections集合存在并创建索引
            if 'collections' not in db.list_collection_names():
                db.create_collection('collections')

            # 为集合表创建索引
            db.collections.create_index([('name', ASCENDING)], unique=True)

            # 获取所有已定义的集合
            for coll_doc in db.collections.find():
                collection_name = coll_doc['name']
                # 确保该集合存在索引
                self._ensure_collection_indexes(collection_name)

            self.logger.info("MongoDB数据库初始化完成")
        except Exception as e:
            self.logger.error(f"MongoDB初始化失败: {str(e)}")
            raise

    def _ensure_collection_indexes(self, collection_name: str):
        """确保集合有正确的索引配置

        Args:
            collection_name: 集合名称
        """
        db = self._get_db()

        # 获取集合的主键和索引字段
        coll_info = db.collections.find_one({'name': collection_name})
        if not coll_info:
            return

        primary_key = coll_info.get('primary_key', 'id')
        indexed_fields = coll_info.get('indexed_fields', [])

        # 对主键创建唯一索引
        db[collection_name].create_index([(primary_key, ASCENDING)], unique=True)

        # 对其他索引字段创建索引
        for field in indexed_fields:
            if field != primary_key:  # 避免重复创建主键索引
                db[collection_name].create_index([(field, ASCENDING)])

        # 添加更新时间索引，用于查询优化
        db[collection_name].create_index([('updated_at', DESCENDING)])

    def create_collection(self, collection_name: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建一个新的集合

        Args:
            collection_name: 集合名称
            options: 集合选项，可以包含 primaryKey 和 indexedFields

        Returns:
            包含操作状态的字典
        """
        db = self._get_db()

        if options is None:
            options = {}

        primary_key = options.get('primaryKey', 'id')
        indexed_fields = options.get('indexedFields', [])

        # 确保主键始终在索引字段中
        if primary_key not in indexed_fields:
            indexed_fields.append(primary_key)

        with self.lock:
            try:
                # 检查集合是否已存在
                if db.collections.find_one({'name': collection_name}):
                    return {"status": "error", "message": f"Collection {collection_name} already exists"}

                # 创建新集合（在MongoDB中，集合会在第一次插入文档时自动创建）
                now = time.time()
                db.collections.insert_one({
                    'name': collection_name,
                    'primary_key': primary_key,
                    'created_at': now,
                    'indexed_fields': indexed_fields,
                    'options': options
                })

                # 确保集合存在并创建索引
                if collection_name not in db.list_collection_names():
                    db.create_collection(collection_name)

                # 创建索引
                self._ensure_collection_indexes(collection_name)

                return {"status": "success", "collectionName": collection_name}
            except Exception as e:
                self.logger.error(f"创建集合失败: {str(e)}")
                return {"status": "error", "message": str(e)}

    def delete_collection(self, collection_name: str) -> Dict[str, Any]:
        """删除一个集合及其所有文档

        Args:
            collection_name: 集合名称

        Returns:
            包含操作状态的字典
        """
        db = self._get_db()

        with self.lock:
            try:
                # 检查集合是否存在
                if not db.collections.find_one({'name': collection_name}):
                    return {"status": "error", "message": f"Collection {collection_name} does not exist"}

                # 删除集合
                db.drop_collection(collection_name)

                # 从collections元数据中删除
                db.collections.delete_one({'name': collection_name})

                return {"status": "success", "message": f"Collection {collection_name} deleted"}
            except Exception as e:
                self.logger.error(f"删除集合失败: {str(e)}")
                return {"status": "error", "message": str(e)}

    def list_collections(self) -> Dict[str, List[Dict[str, Any]]]:
        """列出所有集合

        Returns:
            包含集合列表的字典
        """
        db = self._get_db()

        collections = []
        for coll in db.collections.find():
            collections.append({
                'name': coll['name'],
                'primaryKey': coll['primary_key'],
                'createdAt': coll['created_at'],
                'options': coll.get('options', {})
            })

        return {"collections": collections}

    def _get_collection_primary_key(self, collection_name: str) -> Optional[str]:
        """获取集合的主键

        Args:
            collection_name: 集合名称

        Returns:
            主键名称，如果集合不存在则为None
        """
        db = self._get_db()

        coll_info = db.collections.find_one({'name': collection_name})
        if coll_info is None:
            return None

        return coll_info['primary_key']

    def add_document(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """向集合中添加文档

        Args:
            collection_name: 集合名称
            document: 要添加的文档

        Returns:
            包含操作状态的字典
        """
        db = self._get_db()

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

        try:
            # 插入文档
            result = db[collection_name].insert_one(doc_with_timestamps)

            if result.acknowledged:
                return {"status": "success", "documentId": doc_id}
            else:
                return {"status": "error", "message": "Document insertion not acknowledged"}
        except DuplicateKeyError:
            return {"status": "error", "message": f"Document with id {doc_id} already exists"}
        except Exception as e:
            self.logger.error(f"添加文档失败: {str(e)}")
            return {"status": "error", "message": str(e)}

    def update_document(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """更新集合中的文档

        Args:
            collection_name: 集合名称
            document: 要更新的文档

        Returns:
            包含操作状态的字典
        """
        db = self._get_db()

        # 获取集合的主键
        primary_key = self._get_collection_primary_key(collection_name)
        if not primary_key:
            return {"status": "error", "message": f"Collection {collection_name} does not exist"}

        # 确保文档有主键
        if primary_key not in document:
            return {"status": "error", "message": f"Document must have primary key {primary_key}"}

        doc_id = str(document[primary_key])

        try:
            # 更新时间戳
            now = time.time()
            document['updated_at'] = now

            # 查询条件：根据主键查找文档
            query = {primary_key: doc_id}

            # 更新操作
            result = db[collection_name].update_one(
                query,
                {'$set': document}
            )

            # 如果没有找到文档，则创建一个新的
            if result.matched_count == 0:
                return self.add_document(collection_name, document)

            if result.acknowledged:
                return {"status": "success", "documentId": doc_id}
            else:
                return {"status": "error", "message": "Document update not acknowledged"}
        except Exception as e:
            self.logger.error(f"更新文档失败: {str(e)}")
            return {"status": "error", "message": str(e)}

    def get_document(self, collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """通过ID获取文档

        Args:
            collection_name: 集合名称
            doc_id: 文档ID

        Returns:
            文档，如果不存在则为None
        """
        db = self._get_db()

        # 获取集合的主键
        primary_key = self._get_collection_primary_key(collection_name)
        if not primary_key:
            return None

        try:
            # 根据主键查询文档
            query = {primary_key: doc_id}
            document = db[collection_name].find_one(query)

            # MongoDB会自动添加_id字段，我们通常不需要它
            if document and '_id' in document:
                del document['_id']

            return document
        except Exception as e:
            self.logger.error(f"获取文档失败: {str(e)}")
            return None

    def delete_document(self, collection_name: str, doc_id: str) -> Dict[str, Any]:
        """删除文档

        Args:
            collection_name: 集合名称
            doc_id: 文档ID

        Returns:
            包含操作状态的字典
        """
        db = self._get_db()

        # 获取集合的主键
        primary_key = self._get_collection_primary_key(collection_name)
        if not primary_key:
            return {"status": "error", "message": f"Collection {collection_name} does not exist"}

        try:
            # 根据主键删除文档
            query = {primary_key: doc_id}
            result = db[collection_name].delete_one(query)

            if result.deleted_count == 0:
                return {"status": "error", "message": f"Document with id {doc_id} does not exist"}

            if result.acknowledged:
                return {"status": "success", "message": f"Document with id {doc_id} deleted"}
            else:
                return {"status": "error", "message": "Document deletion not acknowledged"}
        except Exception as e:
            self.logger.error(f"删除文档失败: {str(e)}")
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
        db = self._get_db()

        if options is None:
            options = {}

        filters = options.get('filter', [])
        sort_options = options.get('sort', [])
        limit = int(options.get('limit', 20))
        offset = int(options.get('offset', 0))

        try:
            # 构建查询
            mongo_query = {}

            # 处理文本查询
            if query:
                # 简单的模糊匹配，在实际应用中可能需要更复杂的文本搜索
                mongo_query['$text'] = {'$search': query}

            # 处理过滤器
            for filter_expr in filters:
                if '=' in filter_expr:
                    field, value = filter_expr.split('=', 1)
                elif ':' in filter_expr:
                    field, value = filter_expr.split(':', 1)
                else:
                    continue

                field = field.strip()
                value = value.strip()

                # 将值添加到查询中
                mongo_query[field] = value

            # 构建排序选项
            mongo_sort = []
            for sort_expr in sort_options:
                if ':' in sort_expr:
                    field, direction = sort_expr.split(':')
                    mongo_sort.append((field, DESCENDING if direction.lower() == 'desc' else ASCENDING))
                else:
                    # 默认升序
                    mongo_sort.append((sort_expr, ASCENDING))

            # 如果没有指定排序，默认按照更新时间降序
            if not mongo_sort:
                mongo_sort = [('updated_at', DESCENDING)]

            # 执行查询
            start_time = time.time()
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
                # 移除MongoDB的_id字段
                if '_id' in doc:
                    del doc['_id']
                hits.append(doc)

            processing_time = (time.time() - start_time) * 1000  # 转换为毫秒

            return {
                "hits": hits,
                "offset": offset,
                "limit": limit,
                "estimatedTotalHits": total_count,
                "query": query,
                "processingTimeMs": int(processing_time)
            }
        except Exception as e:
            self.logger.error(f"搜索失败: {str(e)}")
            return {
                "hits": [],
                "offset": offset,
                "limit": limit,
                "estimatedTotalHits": 0,
                "query": query,
                "processingTimeMs": 0,
                "error": str(e)
            }

    def bulk_add_documents(self, collection_name: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量添加多个文档，比单独添加更高效

        Args:
            collection_name: 集合名称
            documents: 要添加的文档列表

        Returns:
            包含操作状态的字典
        """
        db = self._get_db()

        # 获取集合的主键
        primary_key = self._get_collection_primary_key(collection_name)
        if not primary_key:
            # 如果集合不存在，则创建它
            self.create_collection(collection_name)
            primary_key = 'id'  # 默认主键

        # 准备文档，添加时间戳
        now = time.time()
        docs_with_timestamps = []
        doc_ids = []

        for document in documents:
            # 确保文档有主键
            if primary_key not in document:
                continue

            doc_id = str(document[primary_key])
            doc_ids.append(doc_id)

            doc_with_timestamps = document.copy()
            if 'created_at' not in doc_with_timestamps:
                doc_with_timestamps['created_at'] = now
            if 'updated_at' not in doc_with_timestamps:
                doc_with_timestamps['updated_at'] = now

            docs_with_timestamps.append(doc_with_timestamps)

        if not docs_with_timestamps:
            return {"status": "error", "message": "No valid documents to insert"}

        try:
            # 批量插入文档，ordered=False表示遇到错误继续执行其余插入
            result = db[collection_name].insert_many(docs_with_timestamps, ordered=False)

            if result.acknowledged:
                return {
                    "status": "success",
                    "insertedCount": len(result.inserted_ids),
                    "documentIds": doc_ids
                }
            else:
                return {"status": "error", "message": "Documents insertion not acknowledged"}
        except Exception as e:
            self.logger.error(f"批量添加文档失败: {str(e)}")
            return {"status": "error", "message": str(e)}

    def close(self):
        """关闭数据库连接"""
        if self.client is not None:
            mongo_pool.release_client(self.connection_key)
            self.client = None
            self.logger.info(f"MongoDB连接已释放: {self.connection_key}")

    def ensure_writes(self):
        """确保所有写入操作已完成"""
        # MongoDB在写入完成后会自动确认，不需要额外操作
        pass

    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计信息

        Returns:
            包含连接统计信息的字典
        """
        stats = {"status": "unknown"}

        try:
            # 获取客户端
            client = self._get_client()

            # 获取服务器状态
            server_status = client.admin.command('serverStatus')

            # 获取连接信息
            connections = server_status.get('connections', {})

            # 获取连接池状态
            pool_stats = mongo_pool.get_stats()

            stats = {
                "status": "ok",
                "current": connections.get('current', 0),
                "available": connections.get('available', 0),
                "totalCreated": connections.get('totalCreated', 0),
                "active": connections.get('active', 0),
                "maxPoolSize": self.max_pool_size,
                "minPoolSize": self.min_pool_size,
                "appConnectionPool": pool_stats
            }
        except Exception as e:
            self.logger.error(f"获取连接统计信息失败: {str(e)}")
            stats["error"] = str(e)

        return stats

# 应用退出时关闭所有连接
import atexit
atexit.register(mongo_pool.close_all)
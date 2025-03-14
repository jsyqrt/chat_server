from typing import Dict, List, Any, Optional
from flask import current_app
import os
from .factory import StorageFactory
from .abstract import DocumentStore
import time

class DocumentStoreService:
    """文档存储服务，提供高级文档存储功能"""

    def __init__(self, app=None):
        self.app = app
        self.store = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """初始化应用

        Args:
            app: Flask应用
        """
        self.app = app

        # 配置存储
        store_type = app.config.get('DOCUMENT_STORE_TYPE', 'sqlite')
        store_config = app.config.get('DOCUMENT_STORE_CONFIG', {})

        if store_type == 'sqlite' and 'db_path' not in store_config:
            store_config['db_path'] = os.path.join(app.instance_path, 'document_store.db')

        # 创建存储实例
        self.store = StorageFactory.create_store(store_type, **store_config)

        # 将服务添加到应用
        app.document_store = self

        # 创建初始集合
        with app.app_context():
            self._create_initial_collections()

    def _create_initial_collections(self):
        """创建初始集合"""
        self.create_collection('mindmaps')

    def create_collection(self, collection_name: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建集合

        Args:
            collection_name: 集合名称
            options: 集合选项

        Returns:
            操作结果
        """
        return self.store.create_collection(collection_name, options)

    def delete_collection(self, collection_name: str) -> Dict[str, Any]:
        """删除集合

        Args:
            collection_name: 集合名称

        Returns:
            操作结果
        """
        return self.store.delete_collection(collection_name)

    def list_collections(self) -> Dict[str, List[Dict[str, Any]]]:
        """列出所有集合

        Returns:
            集合列表
        """
        return self.store.list_collections()

    def add_document(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """添加文档

        Args:
            collection_name: 集合名称
            document: 文档

        Returns:
            操作结果
        """
        return self.store.add_document(collection_name, document)

    def update_document(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """更新文档

        Args:
            collection_name: 集合名称
            document: 文档

        Returns:
            操作结果
        """
        return self.store.update_document(collection_name, document)

    def get_document(self, collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取文档

        Args:
            collection_name: 集合名称
            doc_id: 文档ID

        Returns:
            文档，如果不存在则为None
        """
        return self.store.get_document(collection_name, doc_id)

    def delete_document(self, collection_name: str, doc_id: str) -> Dict[str, Any]:
        """删除文档

        Args:
            collection_name: 集合名称
            doc_id: 文档ID

        Returns:
            操作结果
        """
        return self.store.delete_document(collection_name, doc_id)

    def search(self, collection_name: str, query: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """搜索文档

        Args:
            collection_name: 集合名称
            query: 搜索查询
            options: 搜索选项

        Returns:
            搜索结果
        """
        return self.store.search(collection_name, query, options)

    # --- 特定于思维导图的方法 ---

    def create_user_mindmap_status_collection(self, user_id: str) -> Dict[str, Any]:
        """创建用户思维导图状态集合

        Args:
            user_id: 用户ID

        Returns:
            操作结果
        """
        collection_name = f'user_mindmap_status_{user_id}'

        # 检查集合是否已存在
        collections = self.list_collections()
        exists = False
        for collection in collections['collections']:
            if collection['name'] == collection_name:
                exists = True
                break

        if not exists:
            # 创建集合，指定主键为 mindmap_id
            return self.create_collection(collection_name, {'primaryKey': 'mindmap_id'})

        return {"status": "success", "message": f"Collection {collection_name} already exists"}

    def add_mindmap(self, mindmap: Dict[str, Any]) -> Dict[str, Any]:
        """添加思维导图

        Args:
            mindmap: 思维导图

        Returns:
            操作结果
        """
        return self.add_document('mindmaps', mindmap)

    def update_mindmap(self, mindmap: Dict[str, Any]) -> Dict[str, Any]:
        """更新思维导图

        Args:
            mindmap: 思维导图

        Returns:
            操作结果
        """
        return self.update_document('mindmaps', mindmap)

    def get_mindmap(self, mindmap_id: str) -> Optional[Dict[str, Any]]:
        """获取思维导图

        Args:
            mindmap_id: 思维导图ID

        Returns:
            思维导图，如果不存在则为None
        """
        return self.get_document('mindmaps', mindmap_id)

    def delete_mindmap(self, mindmap_id: str) -> Dict[str, Any]:
        """删除思维导图

        Args:
            mindmap_id: 思维导图ID

        Returns:
            操作结果
        """
        return self.delete_document('mindmaps', mindmap_id)

    def add_user_mindmap_status(self, user_id: str, mindmap_status: Dict[str, Any]) -> Dict[str, Any]:
        """添加用户思维导图状态

        Args:
            user_id: 用户ID
            mindmap_status: 思维导图状态

        Returns:
            操作结果
        """
        # 确保集合存在
        self.create_user_mindmap_status_collection(user_id)

        # 添加文档
        collection_name = f'user_mindmap_status_{user_id}'
        return self.add_document(collection_name, mindmap_status)

    def update_user_mindmap_status(self, user_id: str, mindmap_status: Dict[str, Any]) -> Dict[str, Any]:
        """更新用户思维导图状态

        Args:
            user_id: 用户ID
            mindmap_status: 思维导图状态

        Returns:
            操作结果
        """
        # 确保集合存在
        self.create_user_mindmap_status_collection(user_id)

        # 更新文档
        collection_name = f'user_mindmap_status_{user_id}'
        return self.update_document(collection_name, mindmap_status)

    def get_user_mindmap_status(self, user_id: str, mindmap_id: str) -> Dict[str, Any]:
        """获取用户思维导图状态

        Args:
            user_id: 用户ID
            mindmap_id: 思维导图ID

        Returns:
            思维导图状态
        """
        # 确保集合存在
        self.create_user_mindmap_status_collection(user_id)

        # 查询文档
        collection_name = f'user_mindmap_status_{user_id}'
        return self.search(collection_name, '', {'filter': [f'mindmap_id={mindmap_id}']})

    def get_user_mindmap_status_list(self, user_id: str, offset: int = 0, limit: int = 3) -> List[Dict[str, Any]]:
        """获取用户思维导图状态列表

        Args:
            user_id: 用户ID
            offset: 偏移量
            limit: 限制

        Returns:
            思维导图状态列表
        """
        # 确保集合存在
        self.create_user_mindmap_status_collection(user_id)

        # 查询文档
        collection_name = f'user_mindmap_status_{user_id}'
        result = self.search(collection_name, '', {
            'offset': offset,
            'limit': limit,
            'sort': ['updated_at:desc']
        })
        return result['hits']

    def find_mindmaps_by_topic(self, topic: str, limit: int = 10) -> List[Dict[str, Any]]:
        """按主题查找思维导图

        Args:
            topic: 主题
            limit: 限制

        Returns:
            思维导图列表
        """
        result = self.search('mindmaps', topic, {'limit': limit})
        return result['hits']

    def find_mindmaps_by_user(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """按用户查找思维导图

        Args:
            user_id: 用户ID
            limit: 限制

        Returns:
            思维导图列表
        """
        result = self.search('mindmaps', '', {'filter': [f'created_by={user_id}'], 'limit': limit})
        return result['hits']

    def upsert_user_mindmap_status(self, user_id: str, mindmap_status: Dict[str, Any]) -> Dict[str, Any]:
        """更新或插入用户思维导图状态

        如果状态已存在则更新，否则插入新状态

        Args:
            user_id: 用户ID
            mindmap_status: 思维导图状态

        Returns:
            操作结果
        """
        # 确保集合存在
        self.create_user_mindmap_status_collection(user_id)

        collection_name = f'user_mindmap_status_{user_id}'

        # 检查文档是否存在
        if 'mindmap_id' not in mindmap_status:
            return {"status": "error", "message": "mindmap_id is required"}

        mindmap_id = mindmap_status['mindmap_id']
        existing = self.search(collection_name, '', {'filter': [f'mindmap_id={mindmap_id}']})

        # 更新时间戳
        now = time.time()
        mindmap_status_with_timestamp = mindmap_status.copy()
        mindmap_status_with_timestamp['updated_at'] = now

        if existing and len(existing.get('hits', [])) > 0:
            # 文档存在，更新它
            return self.update_document(collection_name, mindmap_status_with_timestamp)
        else:
            # 文档不存在，添加它
            if 'created_at' not in mindmap_status_with_timestamp:
                mindmap_status_with_timestamp['created_at'] = now
            return self.add_document(collection_name, mindmap_status_with_timestamp)
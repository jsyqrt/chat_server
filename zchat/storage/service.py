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

    def create_collection(self, collection_name: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建集合

        Args:
            collection_name: 集合名称
            options: 集合选项

        Returns:
            操作结果
        """
        # 添加默认索引字段
        if options is None:
            options = {}

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

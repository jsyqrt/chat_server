from typing import Dict, List, Any, Optional
from flask import current_app
import os
from .factory import StorageFactory
from .abstract import DocumentStore
import time
import logging

class DocumentStoreService:
    """文档存储服务，提供高级文档存储功能"""

    def __init__(self, app=None):
        self.app = app
        self.store = None
        self.logger = logging.getLogger(__name__)

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

        # 为SQLite设置默认路径
        if store_type == 'sqlite' and 'db_path' not in store_config:
            store_config['db_path'] = os.path.join(app.instance_path, 'document_store.db')

        try:
            # 创建存储实例
            self.store = StorageFactory.create_store(store_type, **store_config)
            self.logger.info(f"成功初始化文档存储: {store_type}")
        except Exception as e:
            self.logger.error(f"初始化文档存储失败: {str(e)}")
            # 如果指定的存储类型初始化失败，尝试回退到SQLite
            if store_type != 'sqlite':
                self.logger.warning(f"尝试回退到SQLite存储")
                store_type = 'sqlite'
                store_config = {'db_path': os.path.join(app.instance_path, 'document_store.db')}
                try:
                    self.store = StorageFactory.create_store(store_type, **store_config)
                    self.logger.info(f"成功回退到SQLite存储")
                except Exception as e2:
                    self.logger.critical(f"回退到SQLite存储也失败: {str(e2)}")
                    raise

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

        try:
            return self.store.create_collection(collection_name, options)
        except Exception as e:
            self.logger.error(f"创建集合{collection_name}失败: {str(e)}")
            return {"status": "error", "message": str(e)}

    def delete_collection(self, collection_name: str) -> Dict[str, Any]:
        """删除集合

        Args:
            collection_name: 集合名称

        Returns:
            操作结果
        """
        try:
            return self.store.delete_collection(collection_name)
        except Exception as e:
            self.logger.error(f"删除集合{collection_name}失败: {str(e)}")
            return {"status": "error", "message": str(e)}

    def list_collections(self) -> Dict[str, List[Dict[str, Any]]]:
        """列出所有集合

        Returns:
            集合列表
        """
        try:
            return self.store.list_collections()
        except Exception as e:
            self.logger.error(f"列出集合失败: {str(e)}")
            return {"collections": []}

    def add_document(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """添加文档

        Args:
            collection_name: 集合名称
            document: 文档

        Returns:
            操作结果
        """
        try:
            return self.store.add_document(collection_name, document)
        except Exception as e:
            self.logger.error(f"添加文档到{collection_name}失败: {str(e)}")
            return {"status": "error", "message": str(e)}

    def bulk_add_documents(self, collection_name: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量添加多个文档

        对于MongoDB，这比单独添加每个文档更高效

        Args:
            collection_name: 集合名称
            documents: 文档列表

        Returns:
            操作结果
        """
        try:
            # 如果存储实现支持批量添加，则使用批量添加
            if hasattr(self.store, 'bulk_add_documents'):
                return self.store.bulk_add_documents(collection_name, documents)

            # 否则回退到单独添加每个文档
            self.logger.warning(f"存储引擎不支持批量添加，将单独添加每个文档")
            results = {"status": "success", "added": 0, "failed": 0, "documentIds": []}

            for document in documents:
                result = self.store.add_document(collection_name, document)
                if result.get("status") == "success":
                    results["added"] += 1
                    if "documentId" in result:
                        results["documentIds"].append(result["documentId"])
                else:
                    results["failed"] += 1

            return results
        except Exception as e:
            self.logger.error(f"批量添加文档到{collection_name}失败: {str(e)}")
            return {"status": "error", "message": str(e)}

    def update_document(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """更新文档

        Args:
            collection_name: 集合名称
            document: 文档

        Returns:
            操作结果
        """
        try:
            return self.store.update_document(collection_name, document)
        except Exception as e:
            self.logger.error(f"更新{collection_name}中的文档失败: {str(e)}")
            return {"status": "error", "message": str(e)}

    def get_document(self, collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取文档

        Args:
            collection_name: 集合名称
            doc_id: 文档ID

        Returns:
            文档，如果不存在则为None
        """
        try:
            return self.store.get_document(collection_name, doc_id)
        except Exception as e:
            self.logger.error(f"获取{collection_name}中的文档{doc_id}失败: {str(e)}")
            return None

    def delete_document(self, collection_name: str, doc_id: str) -> Dict[str, Any]:
        """删除文档

        Args:
            collection_name: 集合名称
            doc_id: 文档ID

        Returns:
            操作结果
        """
        try:
            return self.store.delete_document(collection_name, doc_id)
        except Exception as e:
            self.logger.error(f"删除{collection_name}中的文档{doc_id}失败: {str(e)}")
            return {"status": "error", "message": str(e)}

    def search(self, collection_name: str, query: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """搜索文档

        Args:
            collection_name: 集合名称
            query: 搜索查询
            options: 搜索选项

        Returns:
            搜索结果
        """
        try:
            return self.store.search(collection_name, query, options)
        except Exception as e:
            self.logger.error(f"搜索{collection_name}集合失败: {str(e)}")
            return {"hits": [], "status": "error", "message": str(e)}

    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计信息

        仅适用于支持此功能的存储引擎（如MongoDB）

        Returns:
            连接统计信息
        """
        try:
            if hasattr(self.store, 'get_connection_stats'):
                return self.store.get_connection_stats()
            else:
                return {"status": "error", "message": "存储引擎不支持获取连接统计信息"}
        except Exception as e:
            self.logger.error(f"获取连接统计信息失败: {str(e)}")
            return {"status": "error", "message": str(e)}

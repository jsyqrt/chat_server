from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union

class DocumentStore(ABC):
    """抽象文档存储接口，定义了所有文档存储实现必须提供的方法"""

    @abstractmethod
    def create_collection(self, collection_name: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建一个新的集合"""
        pass

    @abstractmethod
    def delete_collection(self, collection_name: str) -> Dict[str, Any]:
        """删除一个集合及其所有文档"""
        pass

    @abstractmethod
    def list_collections(self) -> Dict[str, List[Dict[str, Any]]]:
        """列出所有集合"""
        pass

    @abstractmethod
    def add_document(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """向集合中添加文档"""
        pass

    @abstractmethod
    def update_document(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """更新集合中的文档"""
        pass

    @abstractmethod
    def get_document(self, collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """通过ID获取文档"""
        pass

    @abstractmethod
    def delete_document(self, collection_name: str, doc_id: str) -> Dict[str, Any]:
        """删除文档"""
        pass

    @abstractmethod
    def search(self, collection_name: str, query: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """搜索文档"""
        pass

    def bulk_add_documents(self, collection_name: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量添加多个文档，比单独添加每个文档更高效

        这是一个可选实现的方法，如果存储引擎支持批量添加，应该重写此方法。
        默认实现是顺序添加每个文档。

        Args:
            collection_name: 集合名称
            documents: 要添加的文档列表

        Returns:
            包含操作状态的字典
        """
        results = {"status": "success", "added": 0, "failed": 0, "documentIds": []}

        for document in documents:
            result = self.add_document(collection_name, document)
            if result.get("status") == "success":
                results["added"] += 1
                if "documentId" in result:
                    results["documentIds"].append(result["documentId"])
            else:
                results["failed"] += 1

        return results

    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计信息

        这是一个可选实现的方法，默认返回不支持的消息。

        Returns:
            包含连接统计信息的字典
        """
        return {"status": "error", "message": "此存储引擎不支持获取连接统计信息"}

    def close(self):
        """关闭数据库连接"""
        pass

    def ensure_writes(self):
        """确保所有写入操作已完成"""
        pass
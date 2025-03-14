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
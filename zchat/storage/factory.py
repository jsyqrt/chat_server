from typing import Dict, Optional, Type
from .abstract import DocumentStore
from .sqlite_store import SQLiteDocumentStore
from .mongodb_store import MongoDBDocumentStore

class StorageFactory:
    """存储工厂，用于创建和管理存储实例"""

    _stores: Dict[str, Type[DocumentStore]] = {
        'sqlite': SQLiteDocumentStore,
        'mongodb': MongoDBDocumentStore
    }

    @classmethod
    def register_store(cls, name: str, store_class: Type[DocumentStore]):
        """注册新的存储类型

        Args:
            name: 存储类型名称
            store_class: 存储类
        """
        cls._stores[name] = store_class

    @classmethod
    def create_store(cls, store_type: str, **kwargs) -> DocumentStore:
        """创建存储实例

        Args:
            store_type: 存储类型名称
            **kwargs: 传递给存储构造函数的参数

        Returns:
            存储实例

        Raises:
            ValueError: 如果存储类型不存在
        """
        if store_type not in cls._stores:
            raise ValueError(f"未知的存储类型: {store_type}")

        return cls._stores[store_type](**kwargs)
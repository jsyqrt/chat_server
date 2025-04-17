"""
数据库监控工具

这个模块提供了数据库操作的监控功能，用于跟踪数据库查询的性能指标。
"""

from flask import current_app
from .monitoring import DBQueryTimer

def track_query(query_type):
    """
    数据库查询跟踪装饰器

    用于跟踪各种数据库操作的执行时间。

    Args:
        query_type: 查询类型，如'select', 'insert', 'update', 'delete'等
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with DBQueryTimer(query_type=query_type):
                return func(*args, **kwargs)
        return wrapper
    return decorator

# 常用查询类型
SELECT = 'select'
INSERT = 'insert'
UPDATE = 'update'
DELETE = 'delete'
COMPLEX = 'complex'
AGGREGATE = 'aggregate'
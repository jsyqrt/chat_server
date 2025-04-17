"""
API调用监控工具

这个模块提供了对外部API调用的监控功能，用于跟踪API调用的成功率和性能。
"""

import functools
import time
from flask import current_app
from .monitoring import record_api_request

def monitor_api_call(api_name):
    """
    API调用监控装饰器

    用于跟踪外部API调用的执行结果。

    Args:
        api_name: API名称，用于标识被调用的API
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # 调用原始函数
                result = func(*args, **kwargs)

                # 记录成功的API调用
                record_api_request(api_name, "success")

                return result
            except Exception as e:
                # 记录失败的API调用
                record_api_request(api_name, "error")

                # 重新抛出异常，让调用者处理
                raise
        return wrapper
    return decorator

# 可以添加对常用API的封装
class APIMonitor:
    """API监控工具类"""

    @staticmethod
    def record_success(api_name):
        """记录API调用成功"""
        record_api_request(api_name, "success")

    @staticmethod
    def record_error(api_name):
        """记录API调用失败"""
        record_api_request(api_name, "error")

    @staticmethod
    def record_timeout(api_name):
        """记录API调用超时"""
        record_api_request(api_name, "timeout")

    @classmethod
    def with_monitoring(cls, api_name, func, *args, **kwargs):
        """
        使用监控执行API调用函数

        Args:
            api_name: API名称
            func: 要执行的函数
            args, kwargs: 传递给func的参数

        Returns:
            函数执行结果
        """
        try:
            result = func(*args, **kwargs)
            cls.record_success(api_name)
            return result
        except Exception as e:
            cls.record_error(api_name)
            raise
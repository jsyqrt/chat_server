# -*- coding: utf-8 -*-
import os
import sys
import json
import logging
from typing import List, Optional

from alibabacloud_dysmsapi20170525.client import Client as Dysmsapi20170525Client
from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dysmsapi20170525 import models as dysmsapi_20170525_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient

# 获取logger
logger = logging.getLogger(__name__)

# 导入监控工具
try:
    from ..monitoring import record_api_request
    from ..monitoring.api_monitor import APIMonitor, monitor_api_call
    MONITORING_AVAILABLE = True
except ImportError:
    logger.warning("监控模块不可用，SMS服务将在无监控模式下运行")
    MONITORING_AVAILABLE = False

    # 创建空的监控函数以避免错误
    def record_api_request(api_name, status):
        pass

    class APIMonitor:
        @staticmethod
        def record_success(api_name):
            pass

        @staticmethod
        def record_error(api_name):
            pass

        @staticmethod
        def record_timeout(api_name):
            pass

    def monitor_api_call(api_name):
        def decorator(func):
            return func
        return decorator

class AliSMSClient:
    def __init__(self, access_key_id: str = None, access_key_secret: str = None,
                 sign_name: str = None, template_code: str = None):
        """
        初始化阿里云短信客户端

        Args:
            access_key_id: 阿里云AccessKey ID，如果不提供则从环境变量获取
            access_key_secret: 阿里云AccessKey Secret，如果不提供则从环境变量获取
            sign_name: 短信签名，如果不提供则从环境变量获取
            template_code: 短信模板代码，如果不提供则从环境变量获取
        """
        self.access_key_id = access_key_id or os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID')
        self.access_key_secret = access_key_secret or os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
        self.sign_name = sign_name or os.getenv('ALI_SMS_SIGN_NAME', '原猫信息')
        self.template_code = template_code or os.getenv('ALI_SMS_TEMPLATE_CODE', 'SMS_319000120')

        # 验证必要参数
        if not self.access_key_id or not self.access_key_secret:
            logger.warning("阿里云AccessKey未配置，将使用默认凭据")

        logger.info(f"初始化阿里云短信客户端，签名: {self.sign_name}, 模板: {self.template_code}")

    def create_client(self) -> Dysmsapi20170525Client:
        """
        创建阿里云短信客户端

        Returns:
            Dysmsapi20170525Client: 短信客户端实例
        """
        try:
            # 如果提供了具体的AccessKey，使用静态凭据
            if self.access_key_id and self.access_key_secret:
                config = open_api_models.Config(
                    access_key_id=self.access_key_id,
                    access_key_secret=self.access_key_secret
                )
            else:
                # 否则使用默认凭据链
                credential = CredentialClient()
                config = open_api_models.Config(
                    credential=credential
                )

            # 设置endpoint
            config.endpoint = 'dysmsapi.aliyuncs.com'

            client = Dysmsapi20170525Client(config)
            logger.info("阿里云短信客户端创建成功")
            return client

        except Exception as e:
            logger.error(f"创建阿里云短信客户端失败: {str(e)}")
            raise

    def send_verification_code(self, phone_number: str, verification_code: str) -> bool:
        """
        发送验证码短信

        Args:
            phone_number: 手机号码
            verification_code: 验证码

        Returns:
            bool: 发送是否成功
        """
        api_name = "sms_send_verification"
        try:
            logger.info(f"开始发送验证码短信到手机号: {phone_number}")

            # 创建客户端
            client = self.create_client()

            # 构建短信请求
            send_sms_request = dysmsapi_20170525_models.SendSmsRequest(
                sign_name=self.sign_name,
                template_code=self.template_code,
                phone_numbers=phone_number,
                template_param=json.dumps({"code": verification_code})
            )

            # 运行时选项
            runtime = util_models.RuntimeOptions()

            # 发送短信
            response = client.send_sms_with_options(send_sms_request, runtime)

            # 检查响应
            if response and response.body:
                if response.body.code == 'OK':
                    logger.info(f"验证码短信发送成功，手机号: {phone_number}, 请求ID: {response.body.request_id}")
                    # 记录成功的API调用
                    APIMonitor.record_success(api_name)
                    record_api_request(api_name, "success")
                    return True
                else:
                    logger.warning(f"验证码短信发送失败，手机号: {phone_number}, "
                                 f"错误代码: {response.body.code}, "
                                 f"错误信息: {response.body.message}, "
                                 f"请求ID: {response.body.request_id}")
                    # 记录失败的API调用
                    APIMonitor.record_error(api_name)
                    record_api_request(api_name, "failed")
                    return False
            else:
                logger.warning(f"验证码短信发送失败，手机号: {phone_number}, 响应为空")
                # 记录失败的API调用
                APIMonitor.record_error(api_name)
                record_api_request(api_name, "failed")
                return False

        except Exception as error:
            logger.error(f"发送验证码短信异常，手机号: {phone_number}, 错误: {str(error)}")

            # 记录异常的API调用
            APIMonitor.record_error(api_name)
            record_api_request(api_name, "failed")

            # 尝试获取更详细的错误信息
            try:
                if hasattr(error, 'message'):
                    logger.error(f"错误详情: {error.message}")
                if hasattr(error, 'data') and error.data:
                    recommend = error.data.get("Recommend")
                    if recommend:
                        logger.error(f"建议解决方案: {recommend}")
            except Exception as e:
                logger.error(f"获取错误详情失败: {str(e)}")

            return False

    async def send_verification_code_async(self, phone_number: str, verification_code: str) -> bool:
        """
        异步发送验证码短信

        Args:
            phone_number: 手机号码
            verification_code: 验证码

        Returns:
            bool: 发送是否成功
        """
        api_name = "sms_send_verification"
        try:
            logger.info(f"开始异步发送验证码短信到手机号: {phone_number}")

            # 创建客户端
            client = self.create_client()

            # 构建短信请求
            send_sms_request = dysmsapi_20170525_models.SendSmsRequest(
                sign_name=self.sign_name,
                template_code=self.template_code,
                phone_numbers=phone_number,
                template_param=json.dumps({"code": verification_code})
            )

            # 运行时选项
            runtime = util_models.RuntimeOptions()

            # 异步发送短信
            response = await client.send_sms_with_options_async(send_sms_request, runtime)

            # 检查响应
            if response and response.body:
                if response.body.code == 'OK':
                    logger.info(f"验证码短信异步发送成功，手机号: {phone_number}, 请求ID: {response.body.request_id}")
                    # 记录成功的API调用
                    APIMonitor.record_success(api_name)
                    record_api_request(api_name, "success")
                    return True
                else:
                    logger.warning(f"验证码短信异步发送失败，手机号: {phone_number}, "
                                 f"错误代码: {response.body.code}, "
                                 f"错误信息: {response.body.message}, "
                                 f"请求ID: {response.body.request_id}")
                    # 记录失败的API调用
                    APIMonitor.record_error(api_name)
                    record_api_request(api_name, "failed")
                    return False
            else:
                logger.warning(f"验证码短信异步发送失败，手机号: {phone_number}, 响应为空")
                # 记录失败的API调用
                APIMonitor.record_error(api_name)
                record_api_request(api_name, "failed")
                return False

        except Exception as error:
            logger.error(f"异步发送验证码短信异常，手机号: {phone_number}, 错误: {str(error)}")

            # 记录异常的API调用
            APIMonitor.record_error(api_name)
            record_api_request(api_name, "failed")

            # 尝试获取更详细的错误信息
            try:
                if hasattr(error, 'message'):
                    logger.error(f"错误详情: {error.message}")
                if hasattr(error, 'data') and error.data:
                    recommend = error.data.get("Recommend")
                    if recommend:
                        logger.error(f"建议解决方案: {recommend}")
            except Exception as e:
                logger.error(f"获取错误详情失败: {str(e)}")

            return False


# 全局SMS客户端实例
_sms_client = None

def get_sms_client() -> AliSMSClient:
    """
    获取全局SMS客户端实例

    Returns:
        AliSMSClient: SMS客户端实例
    """
    global _sms_client
    if _sms_client is None:
        _sms_client = AliSMSClient()
    return _sms_client

def send_sms_verification_code(phone_number: str, verification_code: str) -> bool:
    """
    发送验证码短信的便捷函数

    Args:
        phone_number: 手机号码
        verification_code: 验证码

    Returns:
        bool: 发送是否成功
    """
    client = get_sms_client()
    return client.send_verification_code(phone_number, verification_code)

async def send_sms_verification_code_async(phone_number: str, verification_code: str) -> bool:
    """
    异步发送验证码短信的便捷函数

    Args:
        phone_number: 手机号码
        verification_code: 验证码

    Returns:
        bool: 发送是否成功
    """
    client = get_sms_client()
    return await client.send_verification_code_async(phone_number, verification_code)

import time
import json
import uuid
from urllib.parse import parse_qs
from flask import current_app

# 尝试导入支付宝SDK
try:
    from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
    from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
    from alipay.aop.api.domain.AlipayTradeAppPayModel import AlipayTradeAppPayModel
    from alipay.aop.api.request.AlipayTradeAppPayRequest import AlipayTradeAppPayRequest
    from alipay.aop.api.request.AlipayTradeQueryRequest import AlipayTradeQueryRequest
    from alipay.aop.api.domain.AlipayTradeQueryModel import AlipayTradeQueryModel
except ImportError:
    current_app.logger.error("Failed to import Alipay SDK. Please install it with: pip install alipay-sdk-python")

class AlipayConfig:
    """支付宝配置类"""
    def __init__(self, app=None):
        self.app_id = None
        self.private_key = None
        self.alipay_public_key = None
        self.gateway_url = None
        self.notify_url = None
        self.return_url = None
        self.client = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """从Flask应用配置中初始化支付宝配置"""
        self.app_id = app.config.get('ALIPAY_APP_ID')
        self.private_key = app.config.get('ALIPAY_PRIVATE_KEY')
        self.alipay_public_key = app.config.get('ALIPAY_PUBLIC_KEY')
        self.gateway_url = app.config.get('ALIPAY_GATEWAY_URL', 'https://openapi.alipay.com/gateway.do')

        # 是否是沙箱环境
        if app.config.get('ALIPAY_SANDBOX', False):
            self.gateway_url = 'https://openapi-sandbox.dl.alipaydev.com/gateway.do'

        # 支付结果通知回调地址
        self.notify_url = app.config.get('ALIPAY_NOTIFY_URL')
        self.return_url = app.config.get('ALIPAY_RETURN_URL')

        # 初始化支付宝客户端
        self._init_client()

    def _init_client(self):
        """初始化支付宝客户端"""
        try:
            # 配置客户端
            config = AlipayClientConfig()
            config.app_id = self.app_id
            config.app_private_key = self.private_key
            config.alipay_public_key = self.alipay_public_key
            config.sign_type = "RSA2"
            config.gateway_url = self.gateway_url

            # 创建客户端
            self.client = DefaultAlipayClient(alipay_client_config=config)
        except Exception as e:
            current_app.logger.error(f"Failed to initialize Alipay client: {str(e)}")
            self.client = None

# 全局支付宝配置对象
alipay_config = AlipayConfig()

class AlipayService:
    """支付宝服务类"""

    @staticmethod
    def generate_order_string(subject, out_trade_no, total_amount, body=None):
        """
        生成支付宝支付字符串

        Args:
            subject (str): 订单标题
            out_trade_no (str): 商户订单号
            total_amount (float): 订单总金额
            body (str, optional): 订单描述

        Returns:
            str: 支付宝支付字符串，用于唤起支付宝APP
        """
        try:
            # 检查客户端是否初始化
            if alipay_config.client is None:
                current_app.logger.error("Alipay client not initialized")
                return None

            current_app.logger.debug(f"Generating order string for: {out_trade_no}, amount: {total_amount}")

            # 创建支付模型
            model = AlipayTradeAppPayModel()
            model.subject = subject
            model.out_trade_no = out_trade_no
            model.total_amount = str(total_amount)  # 必须是字符串
            if body:
                model.body = body
            model.product_code = "QUICK_MSECURITY_PAY"  # 固定值

            current_app.logger.debug(f"Created payment model with subject: {subject}, body: {body}")

            # 创建请求对象
            request = AlipayTradeAppPayRequest(biz_model=model)
            request.notify_url = alipay_config.notify_url

            current_app.logger.debug(f"Using notify URL: {alipay_config.notify_url}")

            # 调用SDK获取支付字符串
            response = alipay_config.client.sdk_execute(request)
            current_app.logger.debug(f"SDK execute response received for order {out_trade_no}")
            return response
        except Exception as e:
            current_app.logger.error(f"Failed to generate Alipay order string: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def verify_payment(out_trade_no):
        """
        验证支付状态

        Args:
            out_trade_no (str): 商户订单号

        Returns:
            dict: 支付状态信息
        """
        try:
            # 检查客户端是否初始化
            if alipay_config.client is None:
                current_app.logger.error("Alipay client not initialized")
                return None

            current_app.logger.debug(f"Verifying payment for order: {out_trade_no}")

            # 创建查询模型
            model = AlipayTradeQueryModel()
            model.out_trade_no = out_trade_no

            # 创建请求对象
            request = AlipayTradeQueryRequest(biz_model=model)

            # 调用SDK查询交易状态
            response = alipay_config.client.execute(request)
            current_app.logger.debug(f"Alipay query response for order {out_trade_no}: {response}")

            response_dict = json.loads(response)

            # 从响应中提取结果
            result = response_dict.get('alipay_trade_query_response', {})
            current_app.logger.debug(f"Parsed query result: {result}")

            # 返回结果
            return {
                'success': result.get('code') == '10000',
                'trade_status': result.get('trade_status', ''),
                'total_amount': result.get('total_amount', ''),
                'trade_no': result.get('trade_no', ''),  # 支付宝交易号
                'message': result.get('msg', '')
            }
        except Exception as e:
            current_app.logger.error(f"Failed to verify Alipay payment for order {out_trade_no}: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def verify_async_notification(data):
        """
        验证异步通知数据的签名

        Args:
            data (dict): 支付宝异步通知的数据

        Returns:
            bool: 验证是否成功
        """
        try:
            current_app.logger.debug(f"Verifying notification with data keys: {list(data.keys())}")

            # 获取签名相关数据
            sign = data.get('sign')
            if not sign:
                current_app.logger.warning("No signature found in notification data")
                return False

            # 使用cryptography库替代Crypto
            # 这是一个更现代、更可靠的加密库
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.primitives.serialization import load_pem_public_key
            import base64

            # 将参数组装成字符串
            sign_content = ""
            for key in sorted(data.keys()):
                if key not in ['sign', 'sign_type'] and data[key]:
                    sign_content += f"{key}={data[key]}&"
            sign_content = sign_content[:-1]  # 移除最后的 &

            # 处理公钥格式
            public_key = alipay_config.alipay_public_key
            if '-----BEGIN PUBLIC KEY-----' not in public_key:
                public_key = f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"

            # 加载公钥
            key = load_pem_public_key(public_key.encode('utf-8'))

            # 验证签名
            try:
                key.verify(
                    base64.b64decode(sign),
                    sign_content.encode('utf-8'),
                    padding.PKCS1v15(),
                    hashes.SHA256() if data.get('sign_type') == 'RSA2' else hashes.SHA1()
                )
                # 验证成功不会抛出异常
                current_app.logger.debug("Signature verification successful")
                return True
            except Exception as e:
                current_app.logger.warning(f"Signature verification failed: {str(e)}")
                return False

        except Exception as e:
            current_app.logger.error(f"Failed to verify Alipay notification: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def parse_notification_data(request):
        """
        解析支付宝异步通知数据

        Args:
            request: Flask请求对象

        Returns:
            dict: 解析后的通知数据
        """
        try:
            if request.method == 'POST':
                # 处理表单数据
                data = request.form.to_dict()
            else:
                # 处理查询参数
                data = request.args.to_dict()

            return data
        except Exception as e:
            current_app.logger.error(f"Failed to parse Alipay notification data: {str(e)}")
            return {}

    @staticmethod
    def is_payment_successful(trade_status):
        """
        判断支付状态是否表示支付成功

        Args:
            trade_status (str): 支付宝返回的交易状态

        Returns:
            bool: 是否支付成功
        """
        # 支付成功的状态有：
        # TRADE_SUCCESS: 交易支付成功
        # TRADE_FINISHED: 交易结束，不可退款
        return trade_status in ['TRADE_SUCCESS', 'TRADE_FINISHED']

    @staticmethod
    def generate_out_trade_no(prefix=''):
        """
        生成商户订单号

        Args:
            prefix (str, optional): 订单号前缀

        Returns:
            str: 生成的订单号
        """
        # 生成唯一的订单号：时间戳 + UUID的前8位
        timestamp = int(time.time())
        random_part = str(uuid.uuid4()).replace('-', '')[:8]
        return f"{prefix}{timestamp}{random_part}"
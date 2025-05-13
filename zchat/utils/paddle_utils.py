import time
import json
import uuid
import hmac
import hashlib
import requests
from urllib.parse import parse_qs
from flask import current_app

class PaddleConfig:
    """Paddle配置类"""
    def __init__(self, app=None):
        self.vendor_id = None
        self.api_key = None
        self.public_key = None
        self.sandbox_mode = None
        self.api_base_url = None
        self.webhook_url = None
        self.checkout_url = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """从Flask应用配置中初始化Paddle配置"""
        self.vendor_id = app.config.get('PADDLE_VENDOR_ID')
        self.api_key = app.config.get('PADDLE_API_KEY')
        self.public_key = app.config.get('PADDLE_PUBLIC_KEY')
        self.sandbox_mode = app.config.get('PADDLE_SANDBOX_MODE', False)

        # API URL
        if self.sandbox_mode:
            self.api_base_url = "https://sandbox-vendors.paddle.com/api/2.0"
            self.checkout_url = "https://sandbox-checkout.paddle.com/checkout"
        else:
            self.api_base_url = "https://vendors.paddle.com/api/2.0"
            self.checkout_url = "https://checkout.paddle.com/checkout"

        # 支付结果通知回调地址
        self.webhook_url = app.config.get('PADDLE_WEBHOOK_URL')


# 全局Paddle配置对象
paddle_config = PaddleConfig()


class PaddleService:
    """Paddle服务类"""

    @staticmethod
    def generate_checkout_url(product_id, customer_email=None, customer_name=None, passthrough=None, title=None, custom_message=None):
        """
        生成Paddle结账URL

        Args:
            product_id (str/int): Paddle产品ID
            customer_email (str, optional): 客户电子邮件
            customer_name (str, optional): 客户姓名
            passthrough (str, optional): 传递给webhook的数据（通常是订单ID）
            title (str, optional): 结账页面标题
            custom_message (str, optional): 自定义消息

        Returns:
            str: Paddle结账URL
        """
        try:
            # 检查配置
            if not paddle_config.vendor_id or not paddle_config.api_key:
                current_app.logger.error("Paddle not properly configured")
                return None

            # 创建参数
            params = {
                'product_id': product_id,
                'vendor_id': paddle_config.vendor_id
            }

            # 添加可选参数
            if passthrough:
                params['passthrough'] = passthrough

            if customer_email:
                params['customer_email'] = customer_email

            if customer_name:
                params['customer_name'] = customer_name

            if title:
                params['title'] = title

            if custom_message:
                params['custom_message'] = custom_message

            # 生成结账URL
            checkout_url = f"{paddle_config.checkout_url}/{product_id}"
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])

            return f"{checkout_url}?{query_string}"
        except Exception as e:
            current_app.logger.error(f"Failed to generate Paddle checkout URL: {str(e)}")
            return None

    @staticmethod
    def generate_subscription_url(plan_id, customer_email=None, customer_name=None, passthrough=None, quantity=1):
        """
        生成Paddle订阅URL

        Args:
            plan_id (str/int): Paddle计划ID
            customer_email (str, optional): 客户电子邮件
            customer_name (str, optional): 客户姓名
            passthrough (str, optional): 传递给webhook的数据（通常是订单ID）
            quantity (int, optional): 数量

        Returns:
            str: Paddle订阅URL
        """
        try:
            # 检查配置
            if not paddle_config.vendor_id or not paddle_config.api_key:
                current_app.logger.error("Paddle not properly configured")
                return None

            # 创建参数
            params = {
                'plan_id': plan_id,
                'vendor_id': paddle_config.vendor_id,
                'quantity': quantity
            }

            # 添加可选参数
            if passthrough:
                params['passthrough'] = passthrough

            if customer_email:
                params['customer_email'] = customer_email

            if customer_name:
                params['customer_name'] = customer_name

            # 生成结账URL
            checkout_url = f"{paddle_config.checkout_url}/subscription"
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])

            return f"{checkout_url}?{query_string}"
        except Exception as e:
            current_app.logger.error(f"Failed to generate Paddle subscription URL: {str(e)}")
            return None

    @staticmethod
    def verify_webhook_signature(data, signature):
        """
        验证Paddle webhook签名

        Args:
            data (dict): Webhook数据
            signature (str): 签名

        Returns:
            bool: 验证是否成功
        """
        try:
            # 检查配置
            if not paddle_config.public_key:
                current_app.logger.error("Paddle public key not configured")
                return False

            # 按字母顺序排序数据
            sorted_data = sorted([f"{k}={v}" for k, v in data.items()])
            message = "\n".join(sorted_data)

            # 使用PHP serialize格式 (特定于Paddle使用的序列化格式)
            # For simplicity, we use the sorted string instead

            # 验证签名
            from cryptography.hazmat.primitives import serialization, hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.backends import default_backend
            import base64

            # 加载公钥
            public_key_str = paddle_config.public_key
            if '-----BEGIN PUBLIC KEY-----' not in public_key_str:
                public_key_str = f"-----BEGIN PUBLIC KEY-----\n{public_key_str}\n-----END PUBLIC KEY-----"

            public_key = serialization.load_pem_public_key(
                public_key_str.encode('utf-8'),
                backend=default_backend()
            )

            # 验证签名
            try:
                public_key.verify(
                    base64.b64decode(signature),
                    message.encode('utf-8'),
                    padding.PKCS1v15(),
                    hashes.SHA1()
                )
                current_app.logger.debug("Paddle webhook signature verification successful")
                return True
            except Exception as e:
                current_app.logger.warning(f"Paddle webhook signature verification failed: {str(e)}")
                return False
        except Exception as e:
            current_app.logger.error(f"Failed to verify Paddle webhook signature: {str(e)}")
            return False

    @staticmethod
    def parse_webhook_data(request):
        """
        解析Paddle webhook数据

        Args:
            request: Flask请求对象

        Returns:
            tuple: (data, signature)
        """
        try:
            if request.method == 'POST':
                # 获取签名
                signature = request.headers.get('Paddle-Signature')
                # 处理表单数据
                data = request.form.to_dict()
            else:
                # 获取签名
                signature = request.args.get('p_signature')
                # 处理查询参数
                data = request.args.to_dict()

            return data, signature
        except Exception as e:
            current_app.logger.error(f"Failed to parse Paddle webhook data: {str(e)}")
            return {}, None

    @staticmethod
    def verify_transaction(checkout_id):
        """
        验证交易状态

        Args:
            checkout_id (str): Paddle结账ID

        Returns:
            dict: 交易状态信息
        """
        try:
            # 检查配置
            if not paddle_config.vendor_id or not paddle_config.api_key:
                current_app.logger.error("Paddle not properly configured")
                return None

            # 构建API请求
            url = f"{paddle_config.api_base_url}/order"
            params = {
                'vendor_id': paddle_config.vendor_id,
                'vendor_auth_code': paddle_config.api_key,
                'checkout_id': checkout_id
            }

            # 发送请求
            response = requests.post(url, data=params)
            response_json = response.json()

            if response_json.get('success'):
                order = response_json.get('response', {}).get('order')
                if order:
                    return {
                        'success': True,
                        'status': order.get('status'),
                        'checkout_id': checkout_id,
                        'order': order
                    }

            return {
                'success': False,
                'status': 'error',
                'message': response_json.get('error', {}).get('message', 'Unknown error')
            }
        except Exception as e:
            current_app.logger.error(f"Failed to verify Paddle transaction: {str(e)}")
            return None

    @staticmethod
    def generate_order_id(prefix=''):
        """
        生成订单号

        Args:
            prefix (str, optional): 订单号前缀

        Returns:
            str: 生成的订单号
        """
        # 生成唯一的订单号：时间戳 + UUID的前8位
        timestamp = int(time.time())
        random_part = str(uuid.uuid4()).replace('-', '')[:8]
        return f"{prefix}{timestamp}{random_part}"
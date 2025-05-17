import time
import json
import uuid
import hmac
import hashlib
import requests
from urllib.parse import parse_qs
from flask import current_app
from paddle_billing.Notifications import Secret, Verifier

class PaddleConfig:
    """Paddle配置类"""
    def __init__(self, app=None):
        self.vendor_id = None
        self.api_key = None
        self.webhook_secret_key = None
        self.sandbox_mode = None
        self.api_base_url = None
        self.webhook_url = None
        self.checkout_url_prefix = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """从Flask应用配置中初始化Paddle配置"""
        self.vendor_id = app.config.get('PADDLE_VENDOR_ID')
        self.api_key = app.config.get('PADDLE_API_KEY')
        self.webhook_secret_key = app.config.get('PADDLE_WEBHOOK_SECRET_KEY')
        self.sandbox_mode = app.config.get('PADDLE_SANDBOX_MODE', False)

        # API URL
        if self.sandbox_mode:
            self.api_base_url = "https://sandbox-api.paddle.com"
            self.checkout_url_prefix = app.config.get('PADDLE_SANDBOX_CHECKOUT_PREFIX', "")
        else:
            self.api_base_url = "https://api.paddle.com"
            self.checkout_url_prefix = app.config.get('PADDLE_CHECKOUT_PREFIX', "")

        # 支付结果通知回调地址
        self.webhook_url = app.config.get('PADDLE_WEBHOOK_URL')


# 全局Paddle配置对象
paddle_config = PaddleConfig()


class PaddleService:
    """Paddle服务类"""

    @staticmethod
    def generate_checkout_url(price_id, app_user_id):
        """
        生成Paddle结账URL

        Args:
            price_id (str): Paddle价格ID
            app_user_id (str): 应用用户ID

        Returns:
            str: Paddle结账URL
        """
        try:
            # 检查配置
            if not paddle_config.vendor_id or not paddle_config.api_key:
                current_app.logger.error("Paddle not properly configured")
                return None

            # 生成结账URL，格式为：prefix?price_id=xxx
            checkout_url = f"{paddle_config.checkout_url_prefix}?price_id={price_id}&app_user_id={app_user_id}"

            return checkout_url
        except Exception as e:
            current_app.logger.error(f"Failed to generate Paddle checkout URL: {str(e)}")
            return None

    @staticmethod
    def generate_subscription_url(price_id, app_user_id):
        """
        生成Paddle订阅URL

        Args:
            price_id (str): Paddle价格ID
            app_user_id (str): 应用用户ID

        Returns:
            str: Paddle订阅URL
        """
        # 订阅URL现在与普通结账URL使用相同格式，只是使用不同的price_id
        return PaddleService.generate_checkout_url(
            price_id=price_id,
            app_user_id=app_user_id
        )

    @staticmethod
    def verify_webhook_with_sdk(request):
        """
        使用Paddle SDK验证webhook完整性

        Args:
            request: Flask请求对象

        Returns:
            bool: 验证是否成功
        """
        try:
            # 检查配置
            if not paddle_config.webhook_secret_key:
                current_app.logger.error("Paddle webhook secret key not configured")
                return False

            # 使用Paddle SDK验证
            integrity_check = Verifier().verify(request, Secret(paddle_config.webhook_secret_key))

            if integrity_check:
                current_app.logger.debug("Paddle webhook verification successful using SDK")
                return True
            else:
                current_app.logger.warning("Paddle webhook verification failed using SDK")
                return False
        except Exception as e:
            current_app.logger.error(f"Failed to verify Paddle webhook using SDK: {str(e)}")
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
            # 获取签名
            signature = request.headers.get('Paddle-Signature')

            # 处理JSON数据
            data = request.json if request.is_json else {}

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

    @staticmethod
    def get_prices_by_paddle_price_ids(paddle_price_ids: list[str], country_code: str):
        """
        根据Paddle价格ID获取价格ID
        """
        try:
            params = {
                "items": [
                    {"quantity": 1, "price_id": paddle_price_id}
                    for paddle_price_id in paddle_price_ids
                ],
                "address": {
                    "country_code": country_code
                }
            }

            url = f"{paddle_config.api_base_url}/pricing-preview"
            headers = {
                "Authorization": f"Bearer {paddle_config.api_key}"
            }

            response = requests.post(url, headers=headers, json=params)
            response_json = response.json()

            data = response_json.get('data', {})
            details = data.get('details', {})
            line_items = details.get('line_items', [{}])
            prices = [line_item.get('formatted_totals', {}).get('total') for line_item in line_items]
            return prices
        except Exception as e:
            current_app.logger.error(f"Failed to get prices by paddle price IDs: {str(e)}")
            return None

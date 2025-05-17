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
        根据Paddle价格ID获取价格信息

        Args:
            paddle_price_ids (list[str]): Paddle价格ID列表
            country_code (str): 国家代码，如 'CN' 或 'US'

        Returns:
            dict: 包含价格信息的字典，格式为 {price_id: {'formatted_price': '$9.99', 'amount': 999, 'currency_code': 'USD'}}
            如果出错，返回None
        """
        max_retries = 2
        retry_count = 0

        while retry_count <= max_retries:
            try:
                # 检查配置
                if not paddle_config.api_key:
                    current_app.logger.error("Paddle API key not configured")
                    return None

                # 确保country_code是有效的
                if not country_code or len(country_code) != 2:
                    current_app.logger.warning(f"Invalid country code: {country_code}, using 'US' as default")
                    country_code = "US"

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
                    "Authorization": f"Bearer {paddle_config.api_key}",
                    "Content-Type": "application/json"
                }

                # 设置超时，以防API响应慢
                timeout = 5.0  # 5秒超时
                response = requests.post(url, headers=headers, json=params, timeout=timeout)

                # 检查响应状态码
                if response.status_code != 200:
                    current_app.logger.error(f"Paddle API returned error status: {response.status_code}, response: {response.text}")
                    retry_count += 1
                    if retry_count <= max_retries:
                        current_app.logger.info(f"Retrying Paddle API request, attempt {retry_count}/{max_retries}")
                        continue
                    return None

                response_json = response.json()

                # 解析响应
                data = response_json.get('data', {})
                details = data.get('details', {})
                line_items = details.get('line_items', [])

                result = {}
                for i, item in enumerate(line_items):
                    if i < len(paddle_price_ids):
                        price_id = paddle_price_ids[i]
                        formatted_price = item.get('formatted_totals', {}).get('total')
                        unit_price = item.get('price', {}).get('unit_price', {})
                        amount = unit_price.get('amount')
                        currency_code = unit_price.get('currency_code')

                        result[price_id] = {
                            'formatted_price': formatted_price,
                            'amount': int(amount) if amount else 0,
                            'currency_code': currency_code
                        }

                # 验证结果是否包含所有请求的价格ID
                if len(result) != len(paddle_price_ids):
                    missing_ids = set(paddle_price_ids) - set(result.keys())
                    current_app.logger.warning(f"Some price IDs were not found in the Paddle response: {missing_ids}")

                return result
            except requests.Timeout:
                current_app.logger.error(f"Paddle API request timed out")
                retry_count += 1
                if retry_count <= max_retries:
                    current_app.logger.info(f"Retrying Paddle API request after timeout, attempt {retry_count}/{max_retries}")
                else:
                    current_app.logger.error("Max retries reached after timeout")
                    return None
            except Exception as e:
                current_app.logger.error(f"Failed to get prices by paddle price IDs: {str(e)}")
                retry_count += 1
                if retry_count <= max_retries:
                    current_app.logger.info(f"Retrying Paddle API request after error, attempt {retry_count}/{max_retries}")
                else:
                    return None

        return None

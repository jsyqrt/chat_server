import time
from enum import Enum
from flask import current_app
from sqlalchemy.orm import relationship
import json

from zchat.models.base import db

class OrderType(Enum):
    POINTS_PURCHASE = 'points_purchase'  # 积分购买
    SUBSCRIPTION = 'subscription'        # 会员订阅

class PaymentMethod(Enum):
    ALIPAY = 'alipay'    # 支付宝
    WECHAT = 'wechat'    # 微信支付
    PADDLE = 'paddle'    # Paddle支付
    OTHER = 'other'      # 其他支付方式

class OrderStatus(Enum):
    PENDING = 'pending'      # 待支付
    PAID = 'paid'            # 已支付
    FAILED = 'failed'        # 支付失败
    CANCELLED = 'cancelled'  # 已取消

class PaymentOrder(db.Model):
    """支付订单表"""
    __tablename__ = 'PAYMENT_ORDER'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.String(64), nullable=False, unique=True)  # 订单号
    user_id = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    order_type = db.Column(db.String(50), nullable=False)  # 订单类型: OrderType
    item_id = db.Column(db.Integer, nullable=True)  # 商品ID（积分包ID或订阅类型ID）
    amount = db.Column(db.REAL, nullable=False)  # 订单金额
    status = db.Column(db.String(50), nullable=False, default=OrderStatus.PENDING.value)  # 订单状态
    payment_method = db.Column(db.String(50), nullable=False)  # 支付方式
    transaction_id = db.Column(db.String(64), nullable=True)  # 支付交易号（支付宝流水号）
    payment_time = db.Column(db.REAL, nullable=True)  # 支付时间

    # Paddle-specific fields
    paddle_checkout_id = db.Column(db.String(64), nullable=True)  # Paddle checkout ID
    paddle_subscription_id = db.Column(db.String(64), nullable=True)  # Paddle subscription ID
    paddle_payment_id = db.Column(db.String(64), nullable=True)  # Paddle payment ID

    # 附加数据（JSON格式的字符串）
    # 积分购买：{"points": 积分数量}
    # 会员订阅：{"subscription_type": 订阅类型, "start_time": 开始时间, "end_time": 结束时间}
    extra_data = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.REAL, nullable=False, default=time.time)
    updated_at = db.Column(db.REAL, nullable=False, default=time.time, onupdate=time.time)

    # Indexes
    __table_args__ = (
        db.Index('index_PAYMENT_ORDER_order_id', 'order_id'),
        db.Index('index_PAYMENT_ORDER_user_id', 'user_id'),
        db.Index('index_PAYMENT_ORDER_status', 'status'),
        db.Index('index_PAYMENT_ORDER_created_at', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'user_id': self.user_id,
            'order_type': self.order_type,
            'item_id': self.item_id,
            'amount': self.amount,
            'status': self.status,
            'payment_method': self.payment_method,
            'transaction_id': self.transaction_id,
            'payment_time': self.payment_time,
            'paddle_checkout_id': self.paddle_checkout_id,
            'paddle_subscription_id': self.paddle_subscription_id,
            'paddle_payment_id': self.paddle_payment_id,
            'extra_data': self.extra_data,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class PaymentOrderOps:
    """支付订单操作类"""
    def __init__(self, session):
        self.session = session

    def create_order(self, user_id, order_type, item_id, amount, payment_method, extra_data=None):
        """
        创建支付订单

        Args:
            user_id (int): 用户ID
            order_type (str): 订单类型
            item_id (int): 商品ID
            amount (float): 订单金额
            payment_method (str): 支付方式
            extra_data (dict, optional): 附加数据

        Returns:
            PaymentOrder: 创建的订单对象
        """
        try:
            # 生成订单号
            from zchat.utils.alipay_utils import AlipayService
            prefix = 'P' if order_type == OrderType.POINTS_PURCHASE.value else 'S'
            order_id = AlipayService.generate_out_trade_no(prefix)

            # 将附加数据转换为JSON字符串
            extra_data_str = None
            if extra_data:
                extra_data_str = json.dumps(extra_data, ensure_ascii=False)

            # 创建订单
            order = PaymentOrder(
                order_id=order_id,
                user_id=user_id,
                order_type=order_type,
                item_id=item_id,
                amount=amount,
                status=OrderStatus.PENDING.value,
                payment_method=payment_method,
                extra_data=extra_data_str
            )

            self.session.add(order)
            self.session.commit()
            return order
        except Exception as e:
            self.session.rollback()
            current_app.logger.error(f"Failed to create payment order: {str(e)}")
            return None

    def get_order_by_id(self, order_id):
        """根据订单号获取订单"""
        try:
            return self.session.query(PaymentOrder).filter_by(order_id=order_id).first()
        except Exception as e:
            current_app.logger.error(f"Failed to get payment order by ID: {str(e)}")
            return None

    def update_order_status(self, order_id, status, transaction_id=None):
        """
        更新订单状态

        Args:
            order_id (str): 订单号
            status (str): 新状态
            transaction_id (str, optional): 支付交易号

        Returns:
            bool: 是否更新成功
        """
        try:
            order = self.get_order_by_id(order_id)
            if not order:
                return False

            order.status = status
            if status == OrderStatus.PAID.value:
                order.payment_time = time.time()
                if transaction_id:
                    order.transaction_id = transaction_id

            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.error(f"Failed to update payment order status: {str(e)}")
            return False

    def get_user_orders(self, user_id, order_type=None, status=None, limit=10, offset=0):
        """
        获取用户订单列表

        Args:
            user_id (int): 用户ID
            order_type (str, optional): 订单类型过滤
            status (str, optional): 状态过滤
            limit (int, optional): 限制结果数量
            offset (int, optional): 结果偏移量

        Returns:
            list: 订单列表
        """
        try:
            query = self.session.query(PaymentOrder).filter_by(user_id=user_id)

            if order_type:
                query = query.filter_by(order_type=order_type)

            if status:
                query = query.filter_by(status=status)

            orders = query.order_by(db.desc(PaymentOrder.created_at)).limit(limit).offset(offset).all()
            return [order.to_dict() for order in orders]
        except Exception as e:
            current_app.logger.error(f"Failed to get user orders: {str(e)}")
            return []

    def count_user_orders(self, user_id, order_type=None, status=None):
        """
        获取用户订单数量

        Args:
            user_id (int): 用户ID
            order_type (str, optional): 订单类型过滤
            status (str, optional): 状态过滤

        Returns:
            int: 订单数量
        """
        try:
            from sqlalchemy import func, Integer
            query = self.session.query(func.cast(func.count(PaymentOrder.id), Integer)).filter_by(user_id=user_id)

            if order_type:
                query = query.filter_by(order_type=order_type)

            if status:
                query = query.filter_by(status=status)

            return query.scalar()
        except Exception as e:
            current_app.logger.error(f"Failed to count user orders: {str(e)}")
            return 0

    def find_orders_by_paddle_info(self, transaction_id=None, checkout_id=None, subscription_id=None):
        """
        通过Paddle交易信息查找订单

        Args:
            transaction_id (str, optional): Paddle交易ID
            checkout_id (str, optional): Paddle结账ID
            subscription_id (str, optional): Paddle订阅ID

        Returns:
            list: 符合条件的订单列表
        """
        try:
            query = self.session.query(PaymentOrder).filter_by(payment_method=PaymentMethod.PADDLE.value)

            if transaction_id:
                # 可以通过paddle_payment_id或transaction_id查询
                query = query.filter(
                    (PaymentOrder.paddle_payment_id == transaction_id) |
                    (PaymentOrder.transaction_id == transaction_id)
                )

            if checkout_id:
                query = query.filter(PaymentOrder.paddle_checkout_id == checkout_id)

            if subscription_id:
                query = query.filter(PaymentOrder.paddle_subscription_id == subscription_id)

            return query.all()
        except Exception as e:
            current_app.logger.error(f"Failed to find orders by Paddle info: {str(e)}")
            return []
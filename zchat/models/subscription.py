import time
from enum import Enum
from flask import current_app
from sqlalchemy.orm import relationship

from zchat.models.base import db

class AccountType(Enum):
    FREE = 'free'
    BASIC = 'basic'
    PRO = 'pro'

class SubscriptionType(Enum):
    BASIC = 'basic'
    PRO = 'pro'

class Subscription(db.Model):
    """用户订阅记录表"""
    __tablename__ = 'SUBSCRIPTION'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    subscription_type = db.Column(db.String(50), nullable=False)  # 'basic' or 'pro'
    start_time = db.Column(db.REAL, nullable=False, default=time.time())
    end_time = db.Column(db.REAL, nullable=False)
    payment_amount = db.Column(db.REAL, nullable=False)
    payment_method = db.Column(db.String(100), nullable=True)
    payment_order_id = db.Column(db.String(255), nullable=True)  # 新增支付订单号字段
    created_at = db.Column(db.REAL, nullable=False, default=time.time())

    # Indexes
    __table_args__ = (
        db.Index('index_SUBSCRIPTION_user_id', 'user_id'),
        db.Index('index_SUBSCRIPTION_end_time', 'end_time'),
        db.Index('index_SUBSCRIPTION_payment_order_id', 'payment_order_id'),  # 添加订单号索引
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'subscription_type': self.subscription_type,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'payment_amount': self.payment_amount,
            'payment_method': self.payment_method,
            'payment_order_id': self.payment_order_id,
            'created_at': self.created_at
        }

class SubscriptionOps:
    def __init__(self, session):
        self.session = session

    def create_subscription(self, user_id, subscription_type, payment_amount, payment_method=None, payment_order_id=None):
        """创建用户订阅"""
        try:
            # 计算订阅结束时间
            start_time = time.time()
            if subscription_type == SubscriptionType.BASIC.value:
                # Basic: 按月付费
                end_time = start_time + 30 * 24 * 60 * 60  # 30天
            elif subscription_type == SubscriptionType.PRO.value:
                # Pro: 按年付费
                end_time = start_time + 365 * 24 * 60 * 60  # 365天
            else:
                return None

            subscription = Subscription(
                user_id=user_id,
                subscription_type=subscription_type,
                start_time=start_time,
                end_time=end_time,
                payment_amount=payment_amount,
                payment_method=payment_method,
                payment_order_id=payment_order_id
            )
            self.session.add(subscription)
            self.session.commit()
            current_app.logger.debug(f"Created subscription for user {user_id}: {subscription_type}")
            return subscription
        except Exception as e:
            self.session.rollback()
            current_app.logger.error(f"Failed to create subscription for user {user_id}: {str(e)}")
            return None

    def get_active_subscription(self, user_id):
        """获取用户当前有效的订阅"""
        try:
            current_time = time.time()
            subscription = self.session.query(Subscription)\
                .filter(Subscription.user_id == user_id)\
                .filter(Subscription.end_time > current_time)\
                .order_by(db.desc(Subscription.end_time))\
                .first()
            return subscription
        except Exception as e:
            current_app.logger.error(f"Failed to get active subscription for user {user_id}: {str(e)}")
            return None

    def get_subscriptions(self, user_id, limit=10, offset=0):
        """获取用户的订阅历史"""
        try:
            subscriptions = self.session.query(Subscription)\
                .filter(Subscription.user_id == user_id)\
                .order_by(db.desc(Subscription.created_at))\
                .limit(limit).offset(offset).all()
            return [sub.to_dict() for sub in subscriptions]
        except Exception as e:
            current_app.logger.error(f"Failed to get subscriptions for user {user_id}: {str(e)}")
            return []

    def cancel_subscription(self, subscription_id):
        """取消用户订阅（将结束时间设为当前时间）"""
        try:
            subscription = self.session.query(Subscription)\
                .filter(Subscription.id == subscription_id).first()

            if subscription:
                subscription.end_time = time.time()
                self.session.commit()
                current_app.logger.debug(f"Cancelled subscription {subscription_id} for user {subscription.user_id}")
                return True
            return False
        except Exception as e:
            self.session.rollback()
            current_app.logger.error(f"Failed to cancel subscription {subscription_id}: {str(e)}")
            return False

    def get_subscription_by_order(self, payment_order_id):
        """根据支付订单ID获取订阅信息"""
        try:
            subscription = self.session.query(Subscription)\
                .filter(Subscription.payment_order_id == payment_order_id)\
                .first()
            return subscription
        except Exception as e:
            current_app.logger.error(f"Failed to get subscription by order ID {payment_order_id}: {str(e)}")
            return None
import time
from enum import Enum
from flask import current_app
from sqlalchemy.orm import relationship
import uuid

from zchat.db import db
from zchat.models.subscription import AccountType

class PointsTransactionType(Enum):
    CONSUMPTION = 'consumption'    # 积分消费
    PURCHASE = 'purchase'          # 购买积分
    DAILY_RESET = 'daily_reset'    # 每日刷新
    INVITATION = 'invitation'      # 邀请奖励
    REWARD = 'reward'              # 其他奖励
    EXPIRATION = 'expiration'      # 积分过期

class PointsSourceType(Enum):
    ACCOUNT = 'account'        # 账户内积分
    PURCHASE = 'purchase'      # 购买的积分
    INVITATION = 'invitation'  # 邀请获得的积分

class ServiceType(Enum):
    CAREER_ASSESSMENT = 'career_assessment'      # 职业评估
    JOB_ANALYSIS = 'job_analysis'                # 岗位分析
    OPTIMIZE_RESUME = 'optimize_resume'          # 优化简历
    CREATE_ROADMAP = 'create_roadmap'            # 创建学习路径
    UNLOCK_ROADMAP = 'unlock_roadmap'            # 解锁学习路径
    GET_DESCRIPTION = 'get_description'          # 获取描述
    AI_CHAT = 'ai_chat'                          # AI聊天

class RewardType(Enum):
    INVITATION = 'invitation'  # 邀请奖励

class PointsTransaction(db.Model):
    """积分交易记录表"""
    __tablename__ = 'POINTS_TRANSACTION'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    transaction_type = db.Column(db.String, nullable=False)  # 交易类型: PointsTransactionType
    points_amount = db.Column(db.Integer, nullable=False)    # 积分数量 (正值为获得，负值为消费)
    service_type = db.Column(db.String, nullable=True)       # 服务类型
    expires_at = db.Column(db.REAL, nullable=True)          # 有效期
    created_at = db.Column(db.REAL, nullable=False, default=time.time())
    description = db.Column(db.String, nullable=True)

    # Indexes
    __table_args__ = (
        db.Index('index_POINTS_TRANSACTION_user_id', 'user_id'),
        db.Index('index_POINTS_TRANSACTION_transaction_type', 'transaction_type'),
        db.Index('index_POINTS_TRANSACTION_created_at', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'transaction_type': self.transaction_type,
            'points_amount': self.points_amount,
            'service_type': self.service_type,
            'expires_at': self.expires_at,
            'created_at': self.created_at,
            'description': self.description
        }

class PointsBalance(db.Model):
    """积分余额表"""
    __tablename__ = 'POINTS_BALANCE'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    points_amount = db.Column(db.Integer, nullable=False)    # 积分数量
    source_type = db.Column(db.String, nullable=False)       # 积分来源: PointsSourceType
    expires_at = db.Column(db.REAL, nullable=True)          # 有效期
    created_at = db.Column(db.REAL, nullable=False, default=time.time())

    # Indexes
    __table_args__ = (
        db.Index('index_POINTS_BALANCE_user_id', 'user_id'),
        db.Index('index_POINTS_BALANCE_source_type', 'source_type'),
        db.Index('index_POINTS_BALANCE_expires_at', 'expires_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'points_amount': self.points_amount,
            'source_type': self.source_type,
            'expires_at': self.expires_at,
            'created_at': self.created_at
        }

class PointsOps:
    def __init__(self, session):
        self.session = session

    # 常量定义
    POINTS_COST = {
        ServiceType.CAREER_ASSESSMENT.value: 30,
        ServiceType.JOB_ANALYSIS.value: 20,
        ServiceType.OPTIMIZE_RESUME.value: 60,
        ServiceType.UNLOCK_ROADMAP.value: 5,
        ServiceType.CREATE_ROADMAP.value: 30,
        ServiceType.GET_DESCRIPTION.value: 2,
        ServiceType.AI_CHAT.value: 2,
    }

    DAILY_POINTS = {
        AccountType.FREE.value: 80,
        AccountType.BASIC.value: 1000,
        AccountType.PRO.value: 2000,
    }

    REWARDS = {
        RewardType.INVITATION.value: 80  # 邀请奖励积分
    }

    INVITATION_EXPIRE_DAYS = 30  # 邀请积分有效期(天)
    PURCHASED_POINTS_EXPIRE_DAYS = 30  # 购买积分有效期(天)

    # 新增：一天的秒数
    SECONDS_PER_DAY = 86400

    def get_costs_and_rewards(self):
        """获取积分成本和奖励"""
        return {
            'costs': self.POINTS_COST,
            'rewards': self.REWARDS
        }

    def get_service_cost(self, service_type):
        """获取服务所需的积分"""
        return self.POINTS_COST.get(service_type, 0)

    def get_daily_points(self, account_type):
        """获取账户类型对应的每日积分额度"""
        return self.DAILY_POINTS.get(account_type, self.DAILY_POINTS[AccountType.FREE.value])

    def add_transaction(self, user_id, transaction_type, points_amount, service_type=None, expires_at=None, description=None):
        """添加积分交易记录"""
        try:
            transaction = PointsTransaction(
                user_id=user_id,
                transaction_type=transaction_type,
                points_amount=points_amount,
                service_type=service_type,
                expires_at=expires_at,
                description=description
            )
            self.session.add(transaction)
            self.session.commit()
            return transaction
        except Exception as e:
            self.session.rollback()
            current_app.logger.error(f"Failed to add points transaction: {str(e)}")
            return None

    def add_points_balance(self, user_id, points_amount, source_type, expires_at=None):
        """增加积分余额"""
        try:
            balance = PointsBalance(
                user_id=user_id,
                points_amount=points_amount,
                source_type=source_type,
                expires_at=expires_at
            )
            self.session.add(balance)
            self.session.commit()
            return balance
        except Exception as e:
            self.session.rollback()
            current_app.logger.error(f"Failed to add points balance: {str(e)}")
            return None

    def get_total_available_points(self, user_id):
        """获取用户所有可用积分（检查并处理过期积分）"""
        # 先检查过期积分
        self.check_and_expire_points()

        # 获取当前时间
        current_time = time.time()

        # 查询未过期的积分
        try:
            balances = self.session.query(PointsBalance)\
                .filter(PointsBalance.user_id == user_id)\
                .filter((PointsBalance.expires_at.is_(None)) | (PointsBalance.expires_at > current_time))\
                .all()

            # 计算总可用积分
            total_points = sum([balance.points_amount for balance in balances])
            return total_points
        except Exception as e:
            current_app.logger.error(f"Failed to get total available points: {str(e)}")
            return 0

    def get_daily_available_points(self, user_id, account_type):
        """获取用户每日可用积分（懒更新机制）"""
        try:
            # 获取用户信息
            from zchat.models.user import User, UserOps
            user = self.session.query(User).filter_by(id=user_id).first()
            if not user:
                return 0

            # 获取用户的积分重置时间和每日积分额度
            reset_time = user.points_reset_time or 0
            current_time = time.time()
            daily_quota = self.get_daily_points(account_type)

            # 计算上次重置积分的日期（转换为天数）
            last_reset_day = reset_time // self.SECONDS_PER_DAY
            current_day = current_time // self.SECONDS_PER_DAY

            # 如果是新的一天，重置每日积分
            if current_day > last_reset_day:
                # 执行积分重置
                self._perform_points_reset(user_id, account_type)

                # 更新用户的积分重置时间
                user.points_reset_time = current_time
                self.session.commit()

                # 返回重置后的积分额度
                return daily_quota

            # 查询今日已消费的积分
            today_start = current_day * self.SECONDS_PER_DAY  # 今天0点的时间戳

            consumed_points = self.session.query(db.func.sum(PointsTransaction.points_amount))\
                .filter(
                    PointsTransaction.user_id == user_id,
                    PointsTransaction.transaction_type == PointsTransactionType.CONSUMPTION.value,
                    PointsTransaction.created_at >= today_start
                )\
                .scalar() or 0

            # 计算剩余可用积分（每日额度 - 今日已消费）
            available_points = daily_quota + consumed_points  # consumed_points是负值
            return max(0, available_points)
        except Exception as e:
            current_app.logger.error(f"Failed to get daily available points: {str(e)}")
            return 0

    def _perform_points_reset(self, user_id, account_type):
        """执行积分重置，添加每日积分（私有方法）"""
        try:
            # 获取用户当前账户类型的每日积分额度
            daily_points = self.get_daily_points(account_type)

            # 记录积分重置交易
            self.add_transaction(
                user_id=user_id,
                transaction_type=PointsTransactionType.DAILY_RESET.value,
                points_amount=daily_points,
                description=f"每日积分重置: {daily_points}积分"
            )

            current_app.logger.debug(f"Daily points reset for user {user_id}: {daily_points} points")
            return True
        except Exception as e:
            current_app.logger.error(f"Failed to perform points reset: {str(e)}")
            return False

    def get_purchased_points(self, user_id):
        """获取购买的积分"""
        try:
            # 获取当前时间
            current_time = time.time()

            # 查询未过期的购买积分
            balances = self.session.query(PointsBalance)\
                .filter(PointsBalance.user_id == user_id)\
                .filter(PointsBalance.source_type == PointsSourceType.PURCHASE.value)\
                .filter((PointsBalance.expires_at.is_(None)) | (PointsBalance.expires_at > current_time))\
                .all()

            return [balance.to_dict() for balance in balances]
        except Exception as e:
            current_app.logger.error(f"Failed to get purchased points: {str(e)}")
            return []

    def get_invitation_points(self, user_id):
        """获取邀请奖励积分"""
        try:
            # 获取当前时间
            current_time = time.time()

            # 查询未过期的邀请积分
            balances = self.session.query(PointsBalance)\
                .filter(PointsBalance.user_id == user_id)\
                .filter(PointsBalance.source_type == PointsSourceType.INVITATION.value)\
                .filter((PointsBalance.expires_at.is_(None)) | (PointsBalance.expires_at > current_time))\
                .all()

            return [balance.to_dict() for balance in balances]
        except Exception as e:
            current_app.logger.error(f"Failed to get invitation points: {str(e)}")
            return []

    def consume_points(self, user_id, points_amount, service_type, description=None):
        """消费积分，优先消费每日积分"""
        try:
            if points_amount <= 0:
                return False

            # 获取用户账户类型
            account_type = self._get_user_account_type(user_id)

            # 检查并更新每日积分（懒更新机制）
            daily_available = self.get_daily_available_points(user_id, account_type)

            # 获取购买的积分和邀请积分
            purchased_points = self.get_purchased_points(user_id)
            invitation_points = self.get_invitation_points(user_id)

            # 计算总可用积分
            purchased_total = sum([p['points_amount'] for p in purchased_points])
            invitation_total = sum([p['points_amount'] for p in invitation_points])
            total_available = daily_available + purchased_total + invitation_total

            # 检查是否有足够积分
            if total_available < points_amount:
                return False

            # 记录积分消费交易
            self.add_transaction(
                user_id=user_id,
                transaction_type=PointsTransactionType.CONSUMPTION.value,
                points_amount=-points_amount,
                service_type=service_type,
                description=description
            )

            # 优先消费每日积分，不足则消费购买积分和邀请积分
            remaining = points_amount

            # 1. 消费每日积分
            if daily_available > 0:
                daily_consume = min(daily_available, remaining)
                remaining -= daily_consume

            # 如果每日积分不足，继续消费其他来源的积分
            if remaining > 0:
                # 2. 消费邀请积分（优先消费快过期的）
                invitation_points.sort(key=lambda x: x['expires_at'] or float('inf'))
                for point in invitation_points:
                    if remaining <= 0:
                        break

                    balance_id = point['id']
                    balance = self.session.query(PointsBalance).get(balance_id)

                    if balance:
                        consume_amount = min(balance.points_amount, remaining)
                        balance.points_amount -= consume_amount
                        remaining -= consume_amount

                        if balance.points_amount <= 0:
                            self.session.delete(balance)

                # 3. 消费购买积分（优先消费快过期的）
                purchased_points.sort(key=lambda x: x['expires_at'] or float('inf'))
                for point in purchased_points:
                    if remaining <= 0:
                        break

                    balance_id = point['id']
                    balance = self.session.query(PointsBalance).get(balance_id)

                    if balance:
                        consume_amount = min(balance.points_amount, remaining)
                        balance.points_amount -= consume_amount
                        remaining -= consume_amount

                        if balance.points_amount <= 0:
                            self.session.delete(balance)

            # 提交更改
            self.session.commit()
            current_app.logger.debug(f"User {user_id} consumed {points_amount} points for {service_type}")
            return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.error(f"Failed to consume points: {str(e)}")
            return False

    def add_daily_points(self, user_id, account_type):
        """手动添加每日积分（仅在用户首次登录或手动调用时使用）"""
        try:
            # 获取账户类型对应的每日积分额度
            daily_points = self.get_daily_points(account_type)

            # 记录积分交易
            transaction = self.add_transaction(
                user_id=user_id,
                transaction_type=PointsTransactionType.DAILY_RESET.value,
                points_amount=daily_points,
                description=f"每日积分重置: {daily_points}积分"
            )

            current_app.logger.debug(f"Added daily points for user {user_id}: {daily_points} points")
            return transaction is not None
        except Exception as e:
            current_app.logger.error(f"Failed to add daily points: {str(e)}")
            return False

    def purchase_points(self, user_id, points_amount, payment_amount, payment_order_id=None, payment_method=None):
        """购买积分"""
        try:
            # 计算积分过期时间
            expire_time = time.time() + self.PURCHASED_POINTS_EXPIRE_DAYS * 24 * 60 * 60

            # 记录积分交易
            transaction = self.add_transaction(
                user_id=user_id,
                transaction_type=PointsTransactionType.PURCHASE.value,
                points_amount=points_amount,
                expires_at=expire_time,
                description=f"购买积分: {points_amount}积分, 支付金额: {payment_amount}元, 订单号: {payment_order_id or '未知'}, 支付方式: {payment_method or '未知'}"
            )

            if transaction:
                # 增加积分余额
                balance = self.add_points_balance(
                    user_id=user_id,
                    points_amount=points_amount,
                    source_type=PointsSourceType.PURCHASE.value,
                    expires_at=expire_time
                )

                current_app.logger.debug(f"User {user_id} purchased {points_amount} points")
                return balance is not None

            return False
        except Exception as e:
            current_app.logger.error(f"Failed to purchase points: {str(e)}")
            return False

    def add_invitation_points(self, user_id):
        """添加邀请奖励积分"""
        try:
            # 计算积分过期时间
            expire_time = time.time() + self.INVITATION_EXPIRE_DAYS * 24 * 60 * 60

            # 记录积分交易
            transaction = self.add_transaction(
                user_id=user_id,
                transaction_type=PointsTransactionType.INVITATION.value,
                points_amount=self.REWARDS[RewardType.INVITATION.value],
                expires_at=expire_time,
                description=f"邀请奖励: {self.REWARDS[RewardType.INVITATION.value]}积分"
            )

            if transaction:
                # 增加积分余额
                balance = self.add_points_balance(
                    user_id=user_id,
                    points_amount=self.REWARDS[RewardType.INVITATION.value],
                    source_type=PointsSourceType.INVITATION.value,
                    expires_at=expire_time
                )

                current_app.logger.debug(f"User {user_id} received invitation reward: {self.REWARDS[RewardType.INVITATION.value]} points")
                return balance is not None

            return False
        except Exception as e:
            current_app.logger.error(f"Failed to add invitation points: {str(e)}")
            return False

    def get_points_transactions(self, user_id, limit=10, offset=0):
        """获取用户积分交易记录"""
        try:
            transactions = self.session.query(PointsTransaction)\
                .filter(PointsTransaction.user_id == user_id)\
                .order_by(db.desc(PointsTransaction.created_at))\
                .limit(limit).offset(offset).all()

            return [transaction.to_dict() for transaction in transactions]
        except Exception as e:
            current_app.logger.error(f"Failed to get points transactions: {str(e)}")
            return []

    def get_points_transactions_count(self, user_id):
        """获取用户积分交易记录总数"""
        try:
            count = self.session.query(db.func.count(PointsTransaction.id))\
                .filter(PointsTransaction.user_id == user_id)\
                .scalar()

            return count
        except Exception as e:
            current_app.logger.error(f"Failed to get points transactions count: {str(e)}")
            return 0

    def check_and_expire_points(self):
        """检查并过期积分"""
        try:
            # 获取当前时间
            current_time = time.time()

            # 查询已过期的积分
            expired_balances = self.session.query(PointsBalance)\
                .filter(PointsBalance.expires_at <= current_time)\
                .all()

            # 处理过期积分
            for balance in expired_balances:
                # 记录积分过期交易
                self.add_transaction(
                    user_id=balance.user_id,
                    transaction_type=PointsTransactionType.EXPIRATION.value,
                    points_amount=-balance.points_amount,
                    description=f"积分过期: {balance.points_amount}积分"
                )

                # 删除过期积分
                self.session.delete(balance)

            # 提交更改
            self.session.commit()
            current_app.logger.debug(f"Expired points check complete, processed {len(expired_balances)} records")
            return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.error(f"Failed to check and expire points: {str(e)}")
            return False

    def _get_user_account_type(self, user_id):
        """获取用户账户类型"""
        try:
            from zchat.models.user import User
            user = self.session.query(User).filter_by(id=user_id).first()
            if user:
                return user.account_type
            return AccountType.FREE.value
        except Exception as e:
            current_app.logger.error(f"Failed to get user account type: {str(e)}")
            return AccountType.FREE.value
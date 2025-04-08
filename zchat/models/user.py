import json
import uuid
import time
from enum import Enum

from flask import current_app, url_for
from flask_login import UserMixin

from zchat.db import db
# from zchat.rand import *

from sqlalchemy.orm import relationship
from zchat.models.subscription import AccountType, SubscriptionType

class User(UserMixin, db.Model):
    __tablename__ = 'USER'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    phone_number = db.Column(db.String, nullable=False, default='13800001111')

    avatar_name = db.Column(db.String, nullable=False, default='/static/images/default.jpg')
    nickname = db.Column(db.String, nullable=False, default='专家785') # TODO use random name
    signature_text = db.Column(db.String, nullable=False, default='Hello World!')

    gender = db.Column(db.String, nullable=False, default='未知')
    edubg = db.Column(db.String, nullable=False, default='未知')
    yearofwork = db.Column(db.String, nullable=False, default='未知')

    interested_industries = db.Column(db.String, nullable=True)
    interested_roles = db.Column(db.String, nullable=True)
    interested_skills = db.Column(db.String, nullable=True)

    # 新增字段 - 会员订阅和积分系统
    account_type = db.Column(db.String, nullable=False, default=AccountType.FREE.value)
    daily_points = db.Column(db.Integer, nullable=False, default=80)
    points_reset_time = db.Column(db.REAL, nullable=True)
    subscription_start_time = db.Column(db.REAL, nullable=True)
    subscription_end_time = db.Column(db.REAL, nullable=True)
    invite_code = db.Column(db.String, nullable=True)
    invited_by = db.Column(db.Integer, nullable=True)

    create_timestamp = db.Column(db.REAL, nullable=True, default=time.time())

    # 添加这一行关系定义
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        db.Index('index_USER_phone_number', 'phone_number', unique=True),

        db.Index('index_USER_name', 'nickname', unique=False),
        db.Index('index_USER_signature_text', 'signature_text', unique=False),

        db.Index('index_USER_gender', 'gender', unique=False),
        db.Index('index_USER_edubg', 'edubg', unique=False),
        db.Index('index_USER_yearofwork', 'yearofwork', unique=False),

        db.Index('index_USER_account_type', 'account_type', unique=False),
        db.Index('index_USER_invite_code', 'invite_code', unique=True),
        db.Index('index_USER_invited_by', 'invited_by', unique=False),

        db.Index('index_USER_create_timestamp', 'create_timestamp', unique=False),
    )

    def to_dict(self):
        return {
            'id' : self.id,
            'phone_number' : self.phone_number,

            'avatar': self.avatar_name,
            'nickname' : self.nickname,
            'signature_text': self.signature_text,

            'gender' : self.gender,
            'edubg' : self.edubg,
            'yearofwork' : self.yearofwork,

            'interested_industries' : self.interested_industries,
            'interested_roles' : self.interested_roles,
            'interested_skills' : self.interested_skills,

            'account_type': self.account_type,
            'daily_points': self.daily_points,
            'points_reset_time': self.points_reset_time,
            'subscription_start_time': self.subscription_start_time,
            'subscription_end_time': self.subscription_end_time,
            'invite_code': self.invite_code,

            'create_timestamp': self.create_timestamp,
        }

class UserOps:
    def __init__(self, session):
        self.session = session

    def username_with_phone_number_suffix(self, phone_number)->str:
        return f"用户{phone_number[-4:]}"

    def get_or_create_user(self, phone_number, invited_by=None)->int:
        current_app.logger.debug(f"get_or_create_user, {phone_number}")
        try:
            user = self.session.query(User).filter_by(phone_number=phone_number).first()
            if user:
                return user.id

            from zchat.models.invitation import InvitationOps
            invitation_ops = InvitationOps(self.session)

            # TODO with better random name
            user = User(
                phone_number=phone_number,
                nickname=self.username_with_phone_number_suffix(phone_number),
                account_type=AccountType.FREE.value,
                daily_points=80,
                invited_by=invited_by
            )

            self.session.add(user)
            self.session.commit()

            # 生成并保存邀请码
            invite_code = invitation_ops.generate_invite_code(user.id)
            user.invite_code = invite_code
            self.session.commit()

            current_app.logger.debug(f"added user, id: {user.id}, phone_number: {phone_number}")

            # 如果是通过邀请注册的，处理邀请奖励
            if invited_by:
                invitation_ops.process_invitation(invited_by, user.id)

            return user.id
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to add user {phone_number}, error {str(e)}")
        return None

    def update_account_type(self, id, account_type, subscription_start_time=None, subscription_end_time=None)->bool:
        """更新用户账户类型"""
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.account_type = account_type

                # 更新每日积分额度
                if account_type == AccountType.FREE.value:
                    user.daily_points = 80
                elif account_type == AccountType.BASIC.value:
                    user.daily_points = 1000
                elif account_type == AccountType.PRO.value:
                    user.daily_points = 2000

                # 更新订阅时间
                if subscription_start_time:
                    user.subscription_start_time = subscription_start_time
                if subscription_end_time:
                    user.subscription_end_time = subscription_end_time

                self.session.commit()
                current_app.logger.debug(f"updated user account type {id} to {account_type}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user account type {id}, error {str(e)}")
        return False

    def check_and_update_subscription_status(self, id):
        """检查并更新用户订阅状态（如果过期则降级为免费账户）"""
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                current_time = time.time()
                # 如果用户有订阅且已过期
                if user.subscription_end_time and user.subscription_end_time < current_time:
                    if user.account_type != AccountType.FREE.value:
                        user.account_type = AccountType.FREE.value
                        user.daily_points = 80
                        self.session.commit()
                        current_app.logger.debug(f"User {id} subscription expired, downgraded to free account")
                return True
            return False
        except Exception as e:
            current_app.logger.warn(f"Failed to check subscription status for user {id}, error {str(e)}")
            return False

    def get_invite_code(self, id):
        """获取用户邀请码，如果没有则生成一个"""
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                if not user.invite_code:
                    from zchat.models.invitation import InvitationOps
                    invitation_ops = InvitationOps(self.session)
                    invite_code = invitation_ops.generate_invite_code(id)
                    user.invite_code = invite_code
                    self.session.commit()
                return user.invite_code
            return None
        except Exception as e:
            current_app.logger.warn(f"Failed to get invite code for user {id}, error {str(e)}")
            return None

    def update_avatar(self, id, avatar_name)->bool:
        current_app.logger.debug(f"update_avatar, {id}, {avatar_name}")
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.avatar_name = avatar_name

                self.session.commit()
                current_app.logger.debug(f"updated user avatar {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user avatar {id}, error {str(e)}")
        return False

    def update_nickname(self, id, nickname)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.nickname = nickname

                self.session.commit()
                current_app.logger.debug(f"updated user nickname {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user nickname {id}, error {str(e)}")
        return False

    def update_gender(self, id, gender)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.gender = gender

                self.session.commit()
                current_app.logger.debug(f"updated user gender {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user gender {id}, error {str(e)}")
        return False

    def update_edubg(self, id, edubg)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.edubg = edubg

                self.session.commit()
                current_app.logger.debug(f"updated user edubg {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user edubg {id}, error {str(e)}")
        return False

    def update_yearofwork(self, id, yearofwork)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.yearofwork = yearofwork

                self.session.commit()
                current_app.logger.debug(f"updated user yearofwork {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user yearofwork {id}, error {str(e)}")
        return False

    def update_signature(self, id, signature)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.signature_text = signature

                self.session.commit()
                current_app.logger.debug(f"updated user signature {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user signature {id}, error {str(e)}")
        return False

    def update_interested_tags(self, id, interested_industries, interested_roles, interested_skills)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.interested_industries = interested_industries
                user.interested_roles = interested_roles
                user.interested_skills = interested_skills

                self.session.commit()
                current_app.logger.debug(f"updated user interested tags {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user interested tags {id}, error {str(e)}")
        return False

    def update_info(self, id, phone_number, nickname, gender, edubg, yearofwork, signature_text, interested_industries, interested_roles, interested_skills)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.phone_number = phone_number

                user.nickname = nickname
                user.signature_text = signature_text

                user.gender = gender
                user.edubg = edubg
                user.yearofwork = yearofwork

                user.interested_industries = interested_industries
                user.interested_roles = interested_roles
                user.interested_skills = interested_skills

                self.session.commit()
                current_app.logger.debug(f"updated user {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user {id}, error {str(e)}")
        return False

    def get_one(self, id)->User:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            return user
        except Exception as e:
            current_app.logger.debug(f'failed to get user, error {str(e)}')
            return None

    def get_all(self)->list:
        try:
            users = self.session.query(User).all()
            current_app.logger.debug(f'len of all users {len(users)}')
            return [user.to_dict() for user in users]
        except Exception as e:
            current_app.logger.debug(f'failed to get all users, error {str(e)}')
            return []

    def get_stats(self)->dict:
        try:
            total = self.session.query(User).count()
            create_today = self.session.query(User).filter(User.create_timestamp >= time.time() - 24 * 60 * 60).count()
            create_this_week = self.session.query(User).filter(User.create_timestamp >= time.time() - 7 * 24 * 60 * 60).count()
            create_this_month = self.session.query(User).filter(User.create_timestamp >= time.time() - 30 * 24 * 60 * 60).count()

            return {
                'total': total,
                'create_today': create_today,
                'create_this_week': create_this_week,
                'create_this_month': create_this_month,
            }
        except Exception as e:
            current_app.logger.debug(f'failed to get user stats, error {str(e)}')
            return {}

class AdminUser(db.Model):
    __tablename__ = 'ADMIN_USER'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)

    def to_dict(self):
        return {
            'id' : self.id,
            'user_id' : self.user_id,
        }

class AdminUserOps:
    def __init__(self, session):
        self.session = session

    def add_as_admin(self, user_id)->int:
        current_app.logger.debug(f"add_as_admin, {user_id}")
        try:
            admin_user = AdminUser(user_id=user_id)
            self.session.add(admin_user)
            self.session.commit()
            current_app.logger.debug(f"added admin user, id: {user_id}")
            return user_id
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to add admin user {user_id}, error {str(e)}")
        return None

    def is_admin(self, user_id)->bool:
        try:
            user = self.session.query(AdminUser).filter_by(user_id=user_id).first()
            return user is not None
        except Exception as e:
            current_app.logger.debug(f'failed to get admin, error {str(e)}')
            return False

    def get_all(self)->list:
        try:
            users = self.session.query(AdminUser).all()
            current_app.logger.debug(f'len of all admin users {len(users)}')
            return [user.to_dict() for user in users]
        except Exception as e:
            current_app.logger.debug(f'failed to get all admin users, error {str(e)}')
            return []

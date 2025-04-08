import time
import uuid
import hashlib
import random
import string
from flask import current_app

from zchat.db import db
from zchat.models.points import PointsOps

class Invitation(db.Model):
    """邀请记录表"""
    __tablename__ = 'INVITATION'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    inviter_id = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    invitee_id = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    points_rewarded = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.REAL, nullable=False, default=time.time())

    # Indexes
    __table_args__ = (
        db.Index('index_INVITATION_inviter_id', 'inviter_id'),
        db.Index('index_INVITATION_invitee_id', 'invitee_id'),
        db.Index('index_INVITATION_created_at', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'inviter_id': self.inviter_id,
            'invitee_id': self.invitee_id,
            'points_rewarded': self.points_rewarded,
            'created_at': self.created_at
        }

class InvitationOps:
    def __init__(self, session):
        self.session = session

    def generate_invite_code(self, user_id):
        """生成邀请码"""
        # 使用用户ID、当前时间和随机字符串生成唯一邀请码
        now = str(time.time())
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        raw = f"{user_id}:{now}:{random_str}"

        # 使用MD5生成邀请码
        h = hashlib.md5(raw.encode())
        invite_code = h.hexdigest()[:8].upper()

        return invite_code

    def record_invitation(self, inviter_id, invitee_id, points_rewarded):
        """记录邀请关系"""
        try:
            invitation = Invitation(
                inviter_id=inviter_id,
                invitee_id=invitee_id,
                points_rewarded=points_rewarded
            )
            self.session.add(invitation)
            self.session.commit()
            current_app.logger.debug(f"Recorded invitation: inviter={inviter_id}, invitee={invitee_id}")
            return invitation
        except Exception as e:
            self.session.rollback()
            current_app.logger.error(f"Failed to record invitation: {str(e)}")
            return None

    def process_invitation(self, inviter_id, invitee_id):
        """处理邀请奖励（为邀请人和被邀请人添加积分）"""
        try:
            points_ops = PointsOps(self.session)
            reward_points = points_ops.INVITATION_POINTS

            # 为邀请人添加积分
            inviter_success = points_ops.add_invitation_points(inviter_id)

            # 为被邀请人添加积分
            invitee_success = points_ops.add_invitation_points(invitee_id)

            if inviter_success and invitee_success:
                # 记录邀请关系
                invitation = self.record_invitation(inviter_id, invitee_id, reward_points)
                return invitation is not None

            return False
        except Exception as e:
            self.session.rollback()
            current_app.logger.error(f"Failed to process invitation: {str(e)}")
            return False

    def get_invitations_by_inviter(self, inviter_id, limit=10, offset=0):
        """获取用户的邀请记录"""
        try:
            invitations = self.session.query(Invitation)\
                .filter(Invitation.inviter_id == inviter_id)\
                .order_by(db.desc(Invitation.created_at))\
                .limit(limit).offset(offset).all()

            return [inv.to_dict() for inv in invitations]
        except Exception as e:
            current_app.logger.error(f"Failed to get invitations for inviter {inviter_id}: {str(e)}")
            return []

    def get_invitations_count_by_inviter(self, inviter_id):
        """获取用户的邀请数量"""
        try:
            count = self.session.query(db.func.count(Invitation.id))\
                .filter(Invitation.inviter_id == inviter_id)\
                .scalar()

            return count
        except Exception as e:
            current_app.logger.error(f"Failed to get invitation count for inviter {inviter_id}: {str(e)}")
            return 0

    def get_total_points_rewarded(self, inviter_id):
        """获取用户通过邀请获得的总积分"""
        try:
            total_points = self.session.query(db.func.sum(Invitation.points_rewarded))\
                .filter(Invitation.inviter_id == inviter_id)\
                .scalar() or 0

            return total_points
        except Exception as e:
            current_app.logger.error(f"Failed to get total points rewarded for inviter {inviter_id}: {str(e)}")
            return 0
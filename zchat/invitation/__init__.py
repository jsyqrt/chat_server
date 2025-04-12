import time
from flask import Blueprint, request, jsonify, current_app, g, redirect, url_for
from flask_login import login_required, current_user, login_user

from zchat.models.base import db
from zchat.models.user import UserOps
from zchat.models.invitation import InvitationOps
from zchat.models.points import PointsOps

bp = Blueprint('invitation', __name__, url_prefix='/invitation')

@bp.route('/share', methods=['GET'])
@login_required
def get_share_link():
    """获取分享链接和分享码"""
    user_id = current_user.get_id_int()

    user_ops = UserOps(db.session)
    invite_code = user_ops.get_invite_code(user_id)

    if not invite_code:
        return jsonify({"error": "Failed to get invitation code"}), 500

    # 构建分享文本
    user = user_ops.get_one(user_id)
    share_text = f"我正在使用「职路」APP，邀请你一起加入！注册时使用我的邀请码「 {invite_code}」 获得额外积分奖励！"

    return jsonify({
        "invite_code": invite_code,
        "share_text": share_text,
    })

@bp.route('/statistics', methods=['GET'])
@login_required
def get_invitation_statistics():
    """获取邀请统计信息"""
    user_id = current_user.get_id_int()

    invitation_ops = InvitationOps(db.session)
    points_ops = PointsOps(db.session)

    # 获取邀请数量
    total_invited = invitation_ops.get_invitations_count_by_inviter(user_id)

    # 获取邀请奖励总积分
    total_points = invitation_ops.get_total_points_rewarded(user_id)

    # 获取当前可用的邀请积分
    invitation_points = points_ops.get_invitation_points(user_id)
    available_points = sum([p['points_amount'] for p in invitation_points])

    return jsonify({
        "total_invited": total_invited,
        "total_points": total_points,
        "available_points": available_points
    })

# 注册Blueprint
def init_app(app):
    app.register_blueprint(bp)
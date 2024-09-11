from flask import request, current_app, Blueprint
from zchat.auth import login_required, admin_required, current_user
from zchat.db import db
from zchat.user import UserOps, ExpertOps

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/notify_upgrade_app', methods=['GET'])
@login_required
@admin_required
def notify_upgrade_app():
    version = request.args.get('version')
    msg = request.args.get('msg')

    all_users = UserOps(session=db.session).get_all()
    for user in all_users:
        sid = current_app.get_user_session(user['id'])
        if sid:
            current_app.socketio.emit('upgrade_app', {'version': version, 'msg': msg}, to=sid)
        else:
            current_app.logger.debug(f"user {user['id']} is not online")
    return 'ok'

@bp.route('/stats', methods=['GET'])
@login_required
@admin_required
def get_user_stats():
    stats = UserOps(session=db.session).get_stats()
    return stats


@bp.route('/experts_waiting_for_email_verified', methods=['GET'])
@login_required
@admin_required
def experts_waiting_for_email_verified():
    user_ops = UserOps(session=db.session)
    experts = ExpertOps(session=db.session).get_waiting_for_email_verified()
    for expert in experts:
        user_id = expert.get('user_id', 0)
        user = user_ops.get_one(id=user_id)
        if user is not None:
            expert.update(user.to_dict())
    return experts

@bp.route('/experts_waiting_for_human_verified', methods=['GET'])
@login_required
@admin_required
def experts_waiting_for_human_verified():
    user_ops = UserOps(session=db.session)
    experts = ExpertOps(session=db.session).get_waiting_for_human_verified()
    for expert in experts:
        user_id = expert.get('user_id', 0)
        user = user_ops.get_one(id=user_id)
        if user is not None:
            expert.update(user.to_dict())
    return experts

@bp.route('/experts_set_human_verified', methods=['POST'])
@login_required
@admin_required
def experts_set_human_verified():
    user_id = request.form['user_id']
    ExpertOps(session=db.session).set_human_verified(user_id)
    return 'ok'

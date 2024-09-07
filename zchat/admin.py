from flask import request, current_app, Blueprint
from zchat.auth import login_required, admin_required, current_user
from zchat.db import db
from zchat.user import UserOps

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


import time

from flask import render_template, request, current_app, Blueprint

from zchat.auth import login_required, current_user
from zchat.db import db
from zchat.models import *

bp = Blueprint('chat', __name__, url_prefix='/chat')

@bp.route('/test', methods=['GET'])
@login_required
def test_chat():
    return render_template('chat.html')

user_to_session = None
unsent_msgs = None

def init_app(app):
    user_to_session = app.multi_processing_manager.dict()
    unsent_msgs = app.multi_processing_manager.dict()

    @app.socketio.on('connect')
    @login_required
    def handle_connect():
        # Save session id
        uid = current_user.get_id_int()
        sid = request.sid
        user_to_session[uid] = sid

        # Notify user there are n msgs to receive
        msgs = unsent_msgs.get(uid, [])
        app.socketio.emit('notice', {'type': 'msg_to_get', 'count': len(msgs)}, to=sid)

        app.logger.debug(f'Client connected {uid}, {sid}')

    @app.socketio.on('disconnect')
    @login_required
    def handle_disconnect():
        # Remove session id from session map
        uid = current_user.get_id_int()
        user_to_session.pop(uid)

        app.logger.debug(f'Client disconnected {uid}, {request.sid}')

    @app.socketio.on('send_message')
    @login_required
    def handle_send_message(data):
        sid = request.sid
        data_json = data
        app.logger.debug(f'Received JSON data: {data_json}')

        from_id = current_user.get_id_int()
        to_id = data_json.get('receiver', 0)
        msg = data_json.get('msg', 'None')
        msg_type = data_json.get('msg_type', 0)

        # TODO what if from_id == to_id?

        # Send msg to dest
        msg_dict = {'sender': from_id, 'receiver': to_id, 'msg': msg, 'msg_type': msg_type, 'timestamp': time.time()}

        chatmsg_ops = ChatMsgOps(session=db.session)
        chatmsg_ops.add_msg(sender=from_id, receiver=to_id, msg=msg, msg_type=msg_type, timestamp=time.time())

        to_sid = user_to_session.get(to_id, None)
        if to_sid is not None:
            # If the user is online
            app.logger.debug(f'user is online: {to_id}')

            app.socketio.emit('msg', msg_dict, to=to_sid)
        else:
            # Save to a map, waiting the user online again
            # TODO change the map to a db table, in case server is down
            app.logger.debug(f'user is offline: {to_id}')

            msgs = unsent_msgs.get(to_id, [])
            msgs.append(msg_dict)

            unsent_msgs[to_id] = msgs

    @app.socketio.on('get_messages')
    @login_required
    def handle_all_messages(data):
        app.logger.debug(f'get_messages: {data}')
        sid = request.sid
        data_json = data
        app.logger.debug(f'Received JSON data: {data_json}')

        p1_id = data_json.get('p1', 0)
        p2_id = data_json.get('p2', 0)
        before_timestamp = data_json.get('before_timestamp', time.time())
        latest_n = data_json.get('latest_n', 100)

        chatmsg_ops = ChatMsgOps(session=db.session)
        msgs = chatmsg_ops.get_msgs(p1=p1_id, p2=p2_id, before_timestamp=before_timestamp, latest_n=latest_n)

        for msg in msgs:
            app.socketio.emit('msg_response', msg, to=sid)

import json
import time
from multiprocessing import Manager

from flask import render_template, request, current_app
from flask_socketio import SocketIO, join_room, leave_room

from zchat.auth import login_required, current_user
from zchat.db import db
from zchat.models import *

def init_app(app):
    socketio = SocketIO(app)

    manager = Manager()
    user_to_session = manager.dict()
    unsent_msgs = manager.dict()

    @app.route('/test/chat')
    @login_required
    def test_chat():
        return render_template('chat.html')

    @socketio.on('connect')
    @login_required
    def handle_connect():
        # Save session id
        uid = current_user.get_id()
        sid = request.sid
        user_to_session[uid] = sid

        # Notify user there are n msgs to receive
        msgs = unsent_msgs.get(uid, [])
        socketio.emit('response', f'There are {len(msgs)} msgs to receive', to=sid)

        current_app.logger.debug(f'Client connected {uid}, {sid}')

    @socketio.on('disconnect')
    @login_required
    def handle_disconnect():
        # Remove session id from session map
        uid = current_user.get_id()
        user_to_session.pop(uid)

        current_app.logger.debug(f'Client disconnected {uid}, {request.sid}')

    @socketio.on('send_message')
    @login_required
    def handle_send_message(data):
        sid = request.sid
        try:
            data_json = json.loads(data)
            current_app.logger.debug(f'Received JSON data: {data_json}')

            from_id = current_user.get_id()
            to_id = data_json.get('to', '0')
            msg = data_json.get('msg', 'None')

            # Send msg to dest
            blob = json.dumps({'from': from_id, 'msg': msg, 'timestamp': time.time()})

            chatmsg_ops = ChatMsgOps(session=db.session)
            chatmsg_ops.add_msg(sender=int(from_id), receiver=int(to_id), msg=msg, timestamp=time.time())

            to_sid = user_to_session.get(to_id, None)
            if to_sid:
                # If the user is online
                socketio.emit('response', blob, to=to_sid)
            else:
                # Save to a map, waiting the user online again
                # TODO change the map to a db table, in case server is down
                msgs = unsent_msgs.get(to_id, [])
                msgs.append(blob)

                unsent_msgs[to_id] = msgs

        except json.JSONDecodeError:
            current_app.logger.debug(f'Received non-JSON data: {data}')
            socketio.emit('response', f'Invalid json data {data}', to=sid)

    @socketio.on('get_messages')
    @login_required
    def handle_all_messages(data):
        sid = request.sid
        try:
            data_json = json.loads(data)
            current_app.logger.debug(f'Received JSON data: {data_json}')

            p1_id = data_json.get('p1', '0')
            p2_id = data_json.get('p2', '0')
            before_timestamp = data_json.get('before_timestamp', time.time())
            latest_n = data_json.get('latest_n', 100)

            chatmsg_ops = ChatMsgOps(session=db.session)
            msgs = chatmsg_ops.get_msgs(p1=int(p1_id), p2=int(p2_id), before_timestamp=before_timestamp, latest_n=latest_n)

            for msg in msgs:
                socketio.emit('response', msg, to=sid)

        except json.JSONDecodeError:
            current_app.logger.debug(f'Received non-JSON data: {data}')
            socketio.emit('response', f'Invalid json data {data}', to=sid)

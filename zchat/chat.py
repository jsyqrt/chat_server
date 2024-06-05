import json
import time
from multiprocessing import Manager

from flask import render_template, request, current_app
from flask_socketio import SocketIO, join_room, leave_room

from zchat.auth import login_required, current_user

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

    @socketio.on('get_message')
    @login_required
    def handle_get_message(data):
        sid = request.sid
        try:
            data_json = json.loads(data)
            current_app.logger.debug(f'Received JSON data: {data_json}')

            latest_n = data_json.get('latest_n', 100)
            after_timestamp = data_json.get('after_timestamp', time.time()-24*60*60)
            # TODO handle after_timestamp or latest_n, for now, return all

            # Send unsent msgs to user
            uid = current_user.get_id()
            msgs = unsent_msgs.get(uid, [])
            for msg in msgs:
                socketio.emit('response', msg, to=sid)

            # Remove unsent msgs from map
            if len(msgs) != 0:
                unsent_msgs.pop(uid)

        except json.JSONDecodeError:
            current_app.logger.debug(f'Received non-JSON data: {data}')
            socketio.emit('response', f'Invalid json data {data}', to=sid)

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

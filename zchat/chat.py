import json

from flask import render_template
from flask_socketio import SocketIO, join_room, leave_room

from zchat.auth import login_required, current_user

def init_app(app):
    socketio = SocketIO(app)

    @app.route('/test/chat')
    @login_required
    def test_chat():
        return render_template('chat.html')

    @socketio.on('connect')
    @login_required
    def handle_connect():
        print('Client connected')

    @socketio.on('disconnect')
    @login_required
    def handle_disconnect():
        print('Client disconnected')

    # @socketio.on('message')
    # @login_required
    # def handle_message(data):
    #     print(f'Received message: {data}')
    #     socketio.emit('response', data[::-1])

    @socketio.on('send_message')
    @login_required
    def handle_send_message(data):
        try:
            data_json = json.loads(data)
            print(f'Received JSON data: {data_json}')

            from_user = current_user

            # 在这里处理JSON数据
            socketio.emit('response', json.dumps(data_json))
        except json.JSONDecodeError:
            print(f'Received non-JSON data: {data}')
            # 在这里处理非JSON数据
            socketio.emit('response', data[::-1])

    @socketio.on('join')
    def on_join(data):
        username = data['username']
        room = data['room']
        join_room(room)
        # 通知其他用户有新用户加入
        socketio.emit('user_joined', {'username': username}, room=room)

    @socketio.on('message')
    def handle_message(data):
        room = data['room']
        message = data['message']
        username = data['username']
        # 将消息发送给同一个房间的所有用户
        socketio.emit('new_message', {'message': message, 'username': username}, room=room, include_self=False)

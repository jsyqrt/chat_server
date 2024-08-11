from multiprocessing import Manager
from functools import wraps

import jwt
from flask import render_template, request, current_app, Blueprint
from flask_socketio import SocketIO
socketio = SocketIO()

def init_app(app):
    socketio.init_app(app)
    app.socketio = socketio

    app.multi_processing_manager = Manager()

    app.user_to_session = app.multi_processing_manager.dict()
    app.unsent_msgs = app.multi_processing_manager.dict()

    app.add_user_session = lambda user_id, session_id: app.user_to_session.__setitem__(user_id, session_id)
    app.get_user_session = lambda user_id: app.user_to_session.get(user_id, None)
    app.remove_user_session = lambda user_id: app.user_to_session.pop(user_id)

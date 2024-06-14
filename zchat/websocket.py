from multiprocessing import Manager

from flask_socketio import SocketIO

def init_app(app):
    app.socketio = SocketIO(app)
    app.multi_processing_manager = Manager()
    app.user_to_session = app.multi_processing_manager.dict()

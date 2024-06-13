from multiprocessing import Manager

from flask_socketio import SocketIO

def init_app(app):
    app.socketio = SocketIO(app)
    app.multi_processing_manager = Manager()


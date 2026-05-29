"""
Pytest fixtures for the zchat Flask + SocketIO application.

Provides a test app factory with an in-memory SQLite database,
Flask test client, and SocketIO test client.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure the application root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def app():
    """Create the Flask application ONCE per test session.

    This is necessary because ``zchat.websocket.socketio`` is a
    module-level singleton whose event handlers (``@socketio.on``
    in ``zchat/chat.py``) are registered at import time.  Creating
    a new Flask app per test would not create a fresh SocketIO
    instance nor re-register the handlers.
    """
    from zchat import create_app

    test_config = {
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "JWT_SECRET_KEY": "test-jwt-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "MEILISEARCH_HOST": "http://localhost:7700",
        "MEILISEARCH_KEY": "test-master-key",
        "LIVEKIT_HOST": "http://localhost:7880",
        "LIVEKIT_API_KEY": "test-devkey",
        "LIVEKIT_API_SECRET": "test-secret",
        "LIVEKIT_RECORDS_PATH": "livekit/records/",
        "WTF_CSRF_ENABLED": False,
    }

    with patch("meilisearch.Client") as mock_meili_client:
        mock_client_instance = MagicMock()
        mock_client_instance.get_indexes.return_value = {"results": []}
        mock_meili_client.return_value = mock_client_instance
        _app = create_app(test_config=test_config)

    _app.user_to_session = {}
    _app.unsent_msgs = {}
    _app.add_user_session = lambda uid, sid: _app.user_to_session.__setitem__(uid, sid)
    _app.get_user_session = lambda uid: _app.user_to_session.get(uid, None)
    _app.remove_user_session = lambda uid: _app.user_to_session.pop(uid, None)

    with _app.app_context():
        from zchat.db import db
        db.create_all()

    yield _app

    with _app.app_context():
        from zchat.db import db
        db.drop_all()


@pytest.fixture(scope="function", autouse=True)
def _reset_db(app):
    """Re-create all tables and reset in-memory state before every test
    so that tests are isolated from each other despite sharing a
    session-scoped app."""
    # Clear in-memory verification-code dict
    if hasattr(app, "vcode_dict"):
        app.vcode_dict.clear()
    with app.app_context():
        from zchat.db import db
        db.drop_all()
        db.create_all()
    yield
    # No explicit cleanup needed — next test will recreate tables.


@pytest.fixture(scope="function")
def client(app):
    """Flask test client for making HTTP requests."""
    return app.test_client()


@pytest.fixture(scope="function")
def runner(app):
    """Click CLI test runner."""
    return app.test_cli_runner()

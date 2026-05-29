"""
Tests for WebSocket chat message handling via Flask-SocketIO.

Uses the SocketIO ``test_client`` to simulate real-time messaging
between connected clients. Small ``time.sleep()`` calls are used
after ``emit()`` to let the async test client process events.

IMPORTANT: Because the SocketIO event handlers (``@socketio.on``)
are registered at import time on a module-level singleton, ALL
WebSocket chat scenarios must run within a single test function.
Splitting them across separate test functions causes cross-test
leakage of the SocketIO server state.
"""

import time

import jwt

from zchat.db import db
from zchat.models import ChatMsgOps, UserOps, CallRecordOps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jwt_token(app, user_id):
    """Generate a JWT for a given user_id using the app's secret."""
    return jwt.encode(
        {"user_id": user_id},
        app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )


def _create_user(app, phone):
    """Create a user and return user_id."""
    with app.app_context():
        ops = UserOps(session=db.session)
        return ops.get_or_create_user(phone_number=phone)


def _make_socketio_client(app, user_id):
    """Create a SocketIO test client authenticated with a JWT token."""
    token = _jwt_token(app, user_id)
    return app.socketio.test_client(
        app,
        headers={"token": token},
    )


# ---------------------------------------------------------------------------
# Tests — all in a single function per class
# ---------------------------------------------------------------------------

class TestWebSocket:
    """All WebSocket / SocketIO tests run sequentially in one function."""

    def _test_connect_with_valid_token(self, app):
        """A client can connect with a valid JWT token in the header."""
        uid = _create_user(app, "13800001000")
        client = _make_socketio_client(app, uid)
        assert client.is_connected()

        with app.app_context():
            sid = app.get_user_session(uid)
            assert sid is not None, "User session should be stored"
        client.disconnect()

    def _test_disconnect_removes_session(self, app):
        """Disconnecting cleans up the user session."""
        uid = _create_user(app, "13800001001")
        client = _make_socketio_client(app, uid)
        assert client.is_connected()
        client.disconnect()
        assert not client.is_connected()

    def _test_send_message_between_users(self, app):
        """A message sent from user A reaches user B (if online)."""
        uid_a = _create_user(app, "13800002000")
        uid_b = _create_user(app, "13800002001")

        client_a = _make_socketio_client(app, uid_a)
        client_b = _make_socketio_client(app, uid_b)
        assert client_a.is_connected()
        assert client_b.is_connected()

        # Clear initial events
        client_a.get_received()
        client_b.get_received()

        token_a = _jwt_token(app, uid_a)
        client_a.emit("send_message", {
            "token": token_a,
            "receiver": uid_b,
            "msg": "Hello from A!",
            "msg_type": 0,
            "timestamp": time.time(),
        })
        time.sleep(0.1)

        received = client_b.get_received()
        msg_events = [e for e in received if e["name"] == "msg"]
        assert len(msg_events) >= 1, f"No msg events found in {received}"
        assert msg_events[0]["args"][0]["msg"] == "Hello from A!"
        assert msg_events[0]["args"][0]["sender"] == uid_a

    def _test_send_message_to_offline_user(self, app):
        """Messages to offline users are queued in unsent_msgs."""
        uid_a = _create_user(app, "13800003000")
        uid_b = _create_user(app, "13800003001")

        client_a = _make_socketio_client(app, uid_a)
        client_a.get_received()

        token_a = _jwt_token(app, uid_a)
        client_a.emit("send_message", {
            "token": token_a,
            "receiver": uid_b,
            "msg": "You'll get this later",
            "msg_type": 0,
            "timestamp": time.time(),
        })
        time.sleep(0.1)

        with app.app_context():
            chatmsg_ops = ChatMsgOps(session=db.session)
            msgs = chatmsg_ops.get_msgs(
                p1=uid_a, p2=uid_b,
                before_timestamp=time.time() + 10,
                latest_n=10,
            )
            assert len(msgs) >= 1
            assert msgs[0]["msg"] == "You'll get this later"

            queued = app.unsent_msgs.get(uid_b, [])
            assert len(queued) >= 1
            assert queued[0]["msg"] == "You'll get this later"

    def _test_mark_as_read(self, app):
        """Marking a message as read notifies the sender."""
        uid_a = _create_user(app, "13800004000")
        uid_b = _create_user(app, "13800004001")

        client_a = _make_socketio_client(app, uid_a)
        client_b = _make_socketio_client(app, uid_b)
        client_a.get_received()
        client_b.get_received()

        token_a = _jwt_token(app, uid_a)
        ts = time.time()
        client_a.emit("send_message", {
            "token": token_a,
            "receiver": uid_b,
            "msg": "Read this",
            "msg_type": 0,
            "timestamp": ts,
        })
        time.sleep(0.1)

        # Clear B's received (they got the msg)
        client_b.get_received()

        token_b = _jwt_token(app, uid_b)
        client_b.emit("mark_as_read", {
            "token": token_b,
            "sender": uid_a,
            "receiver": uid_b,
            "timestamp": ts,
        })
        time.sleep(0.1)

        received = client_a.get_received()
        read_events = [e for e in received if e["name"] == "latest_read_time"]
        assert len(read_events) >= 1, f"No latest_read_time events found in {received}"
        assert read_events[0]["args"][0]["timestamp"] == ts

    def _test_get_messages_history(self, app):
        """A user can retrieve message history between two parties."""
        uid_a = _create_user(app, "13800005000")
        uid_b = _create_user(app, "13800005001")

        with app.app_context():
            chatmsg_ops = ChatMsgOps(session=db.session)
            ts = time.time()
            for i in range(3):
                chatmsg_ops.add_msg(
                    sender=uid_a, receiver=uid_b,
                    msg=f"msg-{i}", msg_type=0, timestamp=ts + i,
                )

        client_a = _make_socketio_client(app, uid_a)
        client_a.get_received()

        token_a = _jwt_token(app, uid_a)
        client_a.emit("get_messages", {
            "token": token_a,
            "p1": uid_a,
            "p2": uid_b,
            "before_timestamp": time.time() + 10,
            "latest_n": 100,
        })
        time.sleep(0.1)

        received = client_a.get_received()
        msg_responses = [e for e in received if e["name"] == "msg_response"]
        assert len(msg_responses) >= 1, f"No msg_response events found in {received}"

        response_data = msg_responses[0]["args"][0]
        assert "msgs" in response_data
        assert len(response_data["msgs"]) >= 3

    def _test_make_call_to_online_user(self, app):
        """makeCall signals the callee when they are online."""
        uid_a = _create_user(app, "13800006000")
        uid_b = _create_user(app, "13800006001")

        client_a = _make_socketio_client(app, uid_a)
        client_b = _make_socketio_client(app, uid_b)
        client_a.get_received()
        client_b.get_received()

        client_a.emit("makeCall", {
            "callerId": uid_a, "calleeId": uid_b,
            "isVideo": True, "sdpOffer": "sdp-offer-abc",
            "appid": "appt-001",
        })
        time.sleep(0.1)

        received = client_b.get_received()
        call_events = [e for e in received if e["name"] == "newCall"]
        assert len(call_events) >= 1, f"No newCall events found in {received}"
        assert call_events[0]["args"][0]["callerId"] == uid_a
        assert call_events[0]["args"][0]["isVideo"] is True

    def _test_make_call_to_offline_user(self, app):
        """makeCall notifies the caller that callee is offline."""
        uid_a = _create_user(app, "13800007000")
        uid_b = _create_user(app, "13800007001")

        client_a = _make_socketio_client(app, uid_a)
        client_a.get_received()

        client_a.emit("makeCall", {
            "callerId": uid_a, "calleeId": uid_b,
            "isVideo": False, "sdpOffer": "sdp-offer-xyz",
            "appid": "appt-002",
        })
        time.sleep(0.1)

        received = client_a.get_received()
        leave_events = [e for e in received if e["name"] == "callLeaved"]
        assert len(leave_events) >= 1, f"No callLeaved events found in {received}"
        assert leave_events[0]["args"][0]["calleeOnline"] is False

    def _test_accept_call(self, app):
        """acceptCall updates the call record."""
        uid_a = _create_user(app, "13800008000")
        uid_b = _create_user(app, "13800008001")

        client_a = _make_socketio_client(app, uid_a)
        client_b = _make_socketio_client(app, uid_b)
        client_a.get_received()
        client_b.get_received()

        client_a.emit("makeCall", {
            "callerId": uid_a, "calleeId": uid_b,
            "isVideo": True, "sdpOffer": "offer-123",
            "appid": "appt-accept-001",
        })
        time.sleep(0.1)

        # Clear B's received (they got the newCall event)
        client_b.get_received()

        client_b.emit("acceptCall", {
            "calleeId": uid_b, "appid": "appt-accept-001",
        })
        time.sleep(0.1)

        with app.app_context():
            ops = CallRecordOps(session=db.session)
            records = ops.get_records(appointment_id="appt-accept-001")
            assert len(records) >= 1
            assert records[0]["accept_timestamp"] is not None

    # ------------------------------------------------------------------
    # Single test method that runs ALL scenarios sequentially
    # ------------------------------------------------------------------

    def test_all_websocket_scenarios(self, app):
        """Run all WebSocket scenarios sequentially within a single test
        to avoid cross-test interference from the SocketIO singleton."""
        self._test_connect_with_valid_token(app)
        self._test_disconnect_removes_session(app)
        self._test_send_message_between_users(app)
        self._test_send_message_to_offline_user(app)
        self._test_mark_as_read(app)
        self._test_get_messages_history(app)
        self._test_make_call_to_online_user(app)
        self._test_make_call_to_offline_user(app)
        self._test_accept_call(app)

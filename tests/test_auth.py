"""
Tests for the phone-based authentication flow.

Covers:
- Requesting a verification code
- Logging in with a valid verification code
- Handling invalid / expired codes
- Accessing a protected endpoint after login
"""

import pytest


class TestAuthFlow:
    """Phone number verification and login."""

    def test_request_verification_code(self, client, app):
        """A valid phone number returns a 6-digit verification code."""
        resp = client.get("/auth/verification_code?phone_number=13800001111")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["error"] == "succeed"
        assert "code" in data
        assert len(data["code"]) == 6
        assert data["code"].isdigit()

    def test_request_code_invalid_phone(self, client):
        """Missing phone number returns 400."""
        resp = client.get("/auth/verification_code")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid Phone Number!"

    def test_request_code_retry_too_soon(self, client):
        """Requesting a second code before the first expires returns 400."""
        # First request — should succeed
        resp1 = client.get("/auth/verification_code?phone_number=13800001111")
        assert resp1.status_code == 200

        # Second request — should be rate-limited
        resp2 = client.get("/auth/verification_code?phone_number=13800001111")
        assert resp2.status_code == 400
        data = resp2.get_json()
        assert data["error"] == "Retry Later!"

    def test_login_success(self, client):
        """Login with the correct phone + verification code succeeds."""
        # 1. Get a code
        resp = client.get("/auth/verification_code?phone_number=13800001111")
        assert resp.status_code == 200
        code = resp.get_json()["code"]

        # 2. Log in with that code
        resp = client.get(
            f"/auth/login?phone_number=13800001111&verification_code={code}"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["error"] == "login succeed"
        assert "jwt" in data
        assert "user_id" in data

    def test_login_wrong_code(self, client):
        """Login with a wrong code returns 400."""
        # Get a code first so the phone number is registered in vcode_dict
        client.get("/auth/verification_code?phone_number=13800001111")

        resp = client.get(
            "/auth/login?phone_number=13800001111&verification_code=000000"
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "Wrong Verification Code" in data["error"]

    def test_login_no_code_requested(self, client):
        """Login without having requested a code returns 400."""
        resp = client.get(
            "/auth/login?phone_number=13900000000&verification_code=123456"
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "Wrong Verification Code" in data["error"]

    def test_login_no_phone(self, client):
        """Login without phone number returns 400."""
        resp = client.get("/auth/login?verification_code=123456")
        assert resp.status_code == 400

    def test_protected_endpoint_without_auth(self, client):
        """Accessing a protected endpoint without login returns 401."""
        resp = client.get("/auth/protected")
        assert resp.status_code == 401

    def test_protected_endpoint_with_auth(self, client, app):
        """Accessing a protected endpoint after login succeeds."""
        # Inject a verification code directly (avoids rate-limiting issues)
        with app.app_context():
            app.vcode_dict["13800001111"] = "654321"

        # Login
        resp = client.get(
            "/auth/login?phone_number=13800001111&verification_code=654321"
        )
        assert resp.status_code == 200
        assert resp.get_json()["error"] == "login succeed"

        # Now access protected endpoint (Flask-Login session cookie is preserved)
        resp = client.get("/auth/protected")
        assert resp.status_code == 200
        assert "Logged in as:" in resp.get_data(as_text=True)

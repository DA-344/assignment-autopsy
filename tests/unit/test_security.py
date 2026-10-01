from datetime import UTC, datetime

from assignment_autopsy.database.models.user import User
from assignment_autopsy.security.passwords import hash_password, verify_password
from assignment_autopsy.security.sessions import (
    hash_session_token,
    new_session_token,
    session_expiry,
)
from assignment_autopsy.security.two_factor import (
    encrypt_totp,
    new_totp_secret,
    verify_totp,
)


def test_password_hash_and_verify() -> None:
    hashed = hash_password("safe password")
    assert verify_password(hashed, "safe password")
    assert not verify_password(hashed, "wrong password")


def test_session_token_is_hashed_and_expires() -> None:
    token = new_session_token()
    assert token != hash_session_token(token)
    assert len(hash_session_token(token)) == 64
    assert session_expiry(10) > datetime.now(UTC)


def test_totp_round_trip() -> None:
    secret = new_totp_secret()
    encrypted = encrypt_totp(secret, "test-secret")
    code = __import__("pyotp").TOTP(secret).now()
    assert verify_totp(encrypted, code, "test-secret") is True


def test_user_model_exposes_username() -> None:
    assert "username" in User.__table__.columns

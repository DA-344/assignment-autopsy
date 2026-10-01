"""
The MIT License (MIT)

Copyright (c) 2026-present DA-344 (aka Developer Anonymous)

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

import base64
import hashlib
import secrets

import pyotp
from cryptography.fernet import Fernet, InvalidToken


def _cipher(secret_key: str) -> Fernet:
    return Fernet(
        base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode()).digest())
    )


def new_totp_secret() -> str:
    return pyotp.random_base32()


def encrypt_totp(secret: str, app_secret: str) -> str:
    return _cipher(app_secret).encrypt(secret.encode()).decode()


def verify_totp(encrypted: str, code: str, app_secret: str) -> bool:
    try:
        secret = _cipher(app_secret).decrypt(encrypted.encode()).decode()
    except InvalidToken:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=email, issuer_name="Assignment Autopsy"
    )


def new_recovery_codes(amount: int = 10) -> list[str]:
    return [secrets.token_urlsafe(9).upper() for _ in range(amount)]


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()

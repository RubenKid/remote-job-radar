"""Symmetric encryption for per-user secrets (their AI provider API key).

Keys are encrypted at rest with a Fernet key derived from APP_SECRET_KEY, so a
leaked database dump does not expose users' API keys.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def _fernet(secret: str) -> Fernet:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str, secret: str) -> str:
    if not plaintext:
        return ""
    return _fernet(secret).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str, secret: str) -> str:
    if not token:
        return ""
    try:
        return _fernet(secret).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""

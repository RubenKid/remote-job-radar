"""Upwork OAuth2 (authorization-code) helpers for the per-user connect flow."""

from __future__ import annotations

from urllib.parse import urlencode

import requests

_AUTHORIZE = "https://www.upwork.com/ab/account-security/oauth2/authorize"
_TOKEN = "https://www.upwork.com/api/v3/oauth2/token"


def authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Build the Upwork consent URL the user is sent to."""
    q = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"{_AUTHORIZE}?{q}"


def exchange_code(
    client_id: str, client_secret: str, code: str, redirect_uri: str, timeout: int = 30
) -> str:
    """Exchange an authorization code for a refresh token. Returns '' on failure."""
    resp = requests.post(
        _TOKEN,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Accept": "application/json"},
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"token exchange failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json().get("refresh_token", "")

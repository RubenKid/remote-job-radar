#!/usr/bin/env python
"""One-time Upwork OAuth2 authorization helper.

Upwork uses the authorization-code grant. This walks you through it once and
prints the long-lived refresh token to put in .env (UPWORK_REFRESH_TOKEN).

Run:  .venv/bin/python scripts/upwork_auth.py

Needs UPWORK_CLIENT_ID / UPWORK_CLIENT_SECRET / UPWORK_REDIRECT_URI in .env.
The redirect URI must exactly match the one configured in your Upwork app.
"""

from __future__ import annotations

import os
import sys
from urllib.parse import parse_qs, urlparse

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

AUTHORIZE_URL = "https://www.upwork.com/ab/account-security/oauth2/authorize"
TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"


def main() -> int:
    client_id = os.environ.get("UPWORK_CLIENT_ID", "").strip()
    client_secret = os.environ.get("UPWORK_CLIENT_SECRET", "").strip()
    redirect_uri = os.environ.get("UPWORK_REDIRECT_URI", "https://localhost/callback").strip()

    if not client_id or not client_secret:
        print("Set UPWORK_CLIENT_ID and UPWORK_CLIENT_SECRET in .env first.")
        return 1

    auth_url = (
        f"{AUTHORIZE_URL}?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
    )
    print("\n1) Open this URL in your browser and authorize the app:\n")
    print(f"   {auth_url}\n")
    print(f"2) After authorizing you'll be redirected to {redirect_uri}?code=...")
    print("   (the page may fail to load — that's fine, just copy the URL).\n")

    raw = input("3) Paste the full redirect URL (or just the code): ").strip()
    code = raw
    if "code=" in raw:
        parsed = urlparse(raw)
        code = parse_qs(parsed.query).get("code", [""])[0]
    if not code:
        print("No authorization code found.")
        return 1

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Accept": "application/json"},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"\nToken exchange failed ({resp.status_code}): {resp.text[:400]}")
        return 1

    tokens = resp.json()
    refresh = tokens.get("refresh_token", "")
    if not refresh:
        print(f"\nNo refresh_token in response: {tokens}")
        return 1

    print("\n✅ Success! Add this line to your .env:\n")
    print(f"   UPWORK_REFRESH_TOKEN={refresh}\n")
    print("Access token TTL is 24h; the refresh token stays valid as long as it's")
    print("used at least once every 2 weeks (the daily run keeps it alive).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

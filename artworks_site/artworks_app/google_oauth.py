"""Connexion / inscription via Google OAuth 2.0."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlencode

import requests
from flask import current_app, url_for

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'


def google_oauth_configured() -> bool:
    return bool(
        current_app.config.get('GOOGLE_OAUTH_CLIENT_ID')
        and current_app.config.get('GOOGLE_OAUTH_CLIENT_SECRET')
    )


def redirect_uri() -> str:
    site = (current_app.config.get('SITE_URL') or '').rstrip('/')
    if site:
        return f'{site}/auth/google/callback'
    return url_for('auth.google_callback', _external=True)


def _secret() -> bytes:
    return (current_app.config.get('SECRET_KEY') or 'dev').encode('utf-8')


def state_make(
    *,
    action: str = 'login',
    role: str | None = None,
    plan: str | None = None,
    next_url: str | None = None,
) -> str:
    payload = {
        'a': action,
        'r': role or '',
        'p': plan or 'free',
        'n': (next_url or '')[:500],
        'ts': int(time.time()),
        'nonce': secrets.token_urlsafe(8),
    }
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode()
    sig = hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()[:32]
    return f'{raw}.{sig}'


def state_verify(state: str | None, *, max_age: int = 900) -> dict | None:
    if not state or '.' not in state:
        return None
    try:
        raw, sig = state.rsplit('.', 1)
        expected = hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
        if (int(time.time()) - int(payload.get('ts', 0))) > max_age:
            return None
        return payload
    except Exception:
        return None


def authorization_url(*, state: str) -> str:
    params = {
        'client_id': current_app.config['GOOGLE_OAUTH_CLIENT_ID'],
        'redirect_uri': redirect_uri(),
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'online',
        'prompt': 'select_account',
    }
    return f'{GOOGLE_AUTH_URL}?{urlencode(params)}'


def exchange_code(code: str) -> dict | None:
    try:
        resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                'code': code,
                'client_id': current_app.config['GOOGLE_OAUTH_CLIENT_ID'],
                'client_secret': current_app.config['GOOGLE_OAUTH_CLIENT_SECRET'],
                'redirect_uri': redirect_uri(),
                'grant_type': 'authorization_code',
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def fetch_userinfo(access_token: str) -> dict | None:
    try:
        resp = requests.get(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None

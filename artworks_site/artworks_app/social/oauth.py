"""OAuth helpers — PKCE, state signé (port V2 social.py)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time

from flask import current_app, request


def _oauth_secret() -> bytes:
    return (current_app.config.get('SECRET_KEY') or 'dev').encode('utf-8')


def oauth_state_make(platform: str) -> str:
    ts = int(time.time())
    nonce = secrets.token_urlsafe(8)
    payload = f'{platform}|{ts}|{nonce}'
    sig = hmac.new(_oauth_secret(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f'{payload}|{sig}'


def oauth_state_verify(state: str | None, platform: str, *, max_age: int = 900) -> bool:
    if not state:
        return False
    try:
        payload, sig = state.rsplit('|', 1)
        expected = hmac.new(_oauth_secret(), payload.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return False
        plat, ts_s, _nonce = payload.split('|', 2)
        if plat != platform:
            return False
        return (int(time.time()) - int(ts_s)) <= max_age
    except Exception:
        return False


def pkce_verifier() -> str:
    return secrets.token_urlsafe(48)[:96]


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


def _pkce_cookie_name(platform: str) -> str:
    return f'awx_oauth_pkce_{platform}'


def _cookie_secure() -> bool:
    return bool(os.environ.get('SCALINGO_APP'))


def pkce_set_cookie(response, platform: str, verifier: str) -> None:
    ts = int(time.time())
    inner = f'{platform}|{ts}|{verifier}'
    sig = hmac.new(_oauth_secret(), inner.encode(), hashlib.sha256).hexdigest()[:32]
    val = base64.urlsafe_b64encode(f'{inner}|{sig}'.encode()).decode().rstrip('=')
    response.set_cookie(
        _pkce_cookie_name(platform),
        val,
        max_age=600,
        httponly=True,
        secure=_cookie_secure(),
        samesite='Lax',
    )


def pkce_read_verifier(platform: str) -> str | None:
    raw = request.cookies.get(_pkce_cookie_name(platform))
    if not raw:
        return None
    try:
        decoded = base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4)).decode()
        inner, sig = decoded.rsplit('|', 1)
        expected = hmac.new(_oauth_secret(), inner.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return None
        plat, ts_s, verifier = inner.split('|', 2)
        if plat != platform or (int(time.time()) - int(ts_s)) > 600:
            return None
        return verifier
    except Exception:
        return None


def pkce_clear_cookie(response, platform: str) -> None:
    response.delete_cookie(
        _pkce_cookie_name(platform),
        httponly=True,
        secure=_cookie_secure(),
        samesite='Lax',
    )


def redirect_uri(platform: str) -> str:
    """Callback OAuth CRM — /crm/social/oauth/<platform>/callback."""
    from flask import url_for
    explicit = {
        'deviantart': current_app.config.get('DEVIANTART_REDIRECT_URI', ''),
        'pinterest': current_app.config.get('PINTEREST_REDIRECT_URI', ''),
    }.get(platform, '').strip().rstrip('/')
    if explicit:
        return explicit
    site = (current_app.config.get('SITE_URL') or '').rstrip('/')
    if site and 'localhost' not in site and '127.0.0.1' not in site:
        return f'{site}/crm/social/oauth/{platform}/callback'
    return url_for('crm.social_oauth_callback', platform=platform, _external=True)

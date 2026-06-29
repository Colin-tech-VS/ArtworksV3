"""Stockage OAuth DeviantArt / Pinterest (équivalent V2 social_tokens)."""
from __future__ import annotations

from datetime import datetime

from .. import db
from ..models import SocialToken


def get_token(platform: str) -> dict | None:
    rec = SocialToken.query.get(platform)
    if not rec:
        return None
    return {
        'platform': rec.platform,
        'access_token': rec.access_token,
        'refresh_token': rec.refresh_token or '',
        'token_expires_at': rec.token_expires_at.isoformat() if rec.token_expires_at else '',
        'account_username': rec.account_username or '',
        'account_id': rec.account_id or '',
        'scopes': rec.scopes or '',
    }


def save_token(
    platform: str,
    *,
    access_token: str,
    refresh_token: str = '',
    token_expires_at: str | datetime | None = None,
    account_username: str = '',
    account_id: str = '',
    scopes: str = '',
) -> None:
    rec = SocialToken.query.get(platform)
    if not rec:
        rec = SocialToken(platform=platform)
        db.session.add(rec)
    rec.access_token = access_token
    if refresh_token:
        rec.refresh_token = refresh_token
    if token_expires_at:
        if isinstance(token_expires_at, str):
            try:
                rec.token_expires_at = datetime.fromisoformat(token_expires_at.replace('Z', '+00:00'))
            except ValueError:
                rec.token_expires_at = None
        else:
            rec.token_expires_at = token_expires_at
    if account_username:
        rec.account_username = account_username
    if account_id:
        rec.account_id = account_id
    if scopes:
        rec.scopes = scopes
    rec.updated_at = datetime.utcnow()
    db.session.commit()


def delete_token(platform: str) -> None:
    rec = SocialToken.query.get(platform)
    if rec:
        db.session.delete(rec)
        db.session.commit()

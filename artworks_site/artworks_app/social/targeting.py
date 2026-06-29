"""Ciblage posts sociaux — réutilise segments CRM."""
from __future__ import annotations

from ..models import EmailSegment, User
from ..crm.segments import segment_users


def resolve_target_users(
    *,
    mode: str,
    segment_id: int | None = None,
    role: str | None = None,
    user_ids: list[int] | None = None,
) -> list[User]:
    mode = (mode or 'role').strip()
    if mode == 'segment' and segment_id:
        seg = EmailSegment.query.get(segment_id)
        if seg:
            return segment_users(seg.filters)
    if mode == 'role' and role:
        return User.query.filter(
            User.role == role,
            User.is_staff.is_(False),
            User.role != 'admin',
        ).order_by(User.display_name, User.username).all()
    if mode == 'users' and user_ids:
        return User.query.filter(User.id.in_(user_ids)).all()
    return []


def pick_featured_artwork(user: User):
    """Première œuvre avec image du client (pour visuel du post)."""
    for a in sorted(user.artworks or [], key=lambda x: x.created_at or '', reverse=True):
        if a.image:
            return a
    return None


def build_destination_url(user: User, site_url: str) -> str:
    from flask import url_for
    return f'{site_url.rstrip("/")}{url_for("main.artist", artist_id=user.id)}'

"""Audience segmentation for CRM email campaigns."""
from __future__ import annotations

from sqlalchemy import func

from ..models import Artwork, User, db


ROLE_LABELS = {
    'artiste': 'Artistes',
    'galerie': 'Galeries',
    'collectionneur': 'Collectionneurs',
}

PLAN_LABELS = {
    'free': 'Compte / Découverte',
    'portfolio': 'Portfolio Marketplace',
    'essentiel': 'Portfolio Marketplace',
    'pro': 'Pro',
    'galerie_pro': 'Galerie Pro',
    'premium': 'Premium',
    'membre': 'Membre',
    'patron': 'Patron',
}


def apply_segment_filters(query, filters: dict | None):
    filters = filters or {}
    q = query

    role = filters.get('role')
    if role and role != 'all':
        q = q.filter(User.role == role)

    plan = filters.get('plan')
    if plan and plan != 'all':
        q = q.filter(User.subscription_plan == plan)

    status = filters.get('subscription_status')
    if status and status != 'all':
        q = q.filter(User.subscription_status == status)

    paid = filters.get('paid_only')
    if paid in (True, '1', 'true', 'yes'):
        q = q.filter(User.subscription_plan != 'free')

    min_artworks = filters.get('min_artworks')
    if min_artworks is not None and str(min_artworks).isdigit():
        n = int(min_artworks)
        sub = (
            db.session.query(Artwork.user_id, func.count(Artwork.id).label('cnt'))
            .group_by(Artwork.user_id)
            .subquery()
        )
        q = q.outerjoin(sub, User.id == sub.c.user_id).filter(
            func.coalesce(sub.c.cnt, 0) >= n
        )

    has_stripe = filters.get('has_stripe')
    if has_stripe in (True, '1', 'true', 'yes'):
        q = q.filter(User.stripe_customer_id.isnot(None))

    q = q.filter(User.is_staff.is_(False), User.role != 'admin')
    return q.distinct()


def segment_users(filters: dict | None):
    return apply_segment_filters(User.query, filters).order_by(User.id).all()


def segment_count(filters: dict | None) -> int:
    return apply_segment_filters(User.query, filters).count()


def preview_segment_name(filters: dict | None) -> str:
    filters = filters or {}
    parts = []
    role = filters.get('role')
    if role and role != 'all':
        parts.append(ROLE_LABELS.get(role, role))
    plan = filters.get('plan')
    if plan and plan != 'all':
        parts.append(PLAN_LABELS.get(plan, plan))
    if filters.get('paid_only'):
        parts.append('payants')
    if not parts:
        return 'Tous les utilisateurs'
    return ' · '.join(parts)

"""Segmentation intelligente automatique — chaque utilisateur est classé à l'inscription."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func

from ..models import Artwork, EmailSegment, User, UserSegmentMembership, db
from .segments import PLAN_LABELS, ROLE_LABELS, apply_segment_filters


SYSTEM_SEGMENTS = [
    {'slug': 'sys-artistes', 'name': 'Artistes', 'filters': {'role': 'artiste'}},
    {'slug': 'sys-galeries', 'name': 'Galeries', 'filters': {'role': 'galerie'}},
    {'slug': 'sys-collectionneurs', 'name': 'Collectionneurs', 'filters': {'role': 'collectionneur'}},
    {'slug': 'sys-abonnes-payants', 'name': 'Abonnés payants', 'filters': {'paid_only': True}},
    {'slug': 'sys-gratuits', 'name': 'Comptes gratuits', 'filters': {'plan': 'free'}},
    {'slug': 'sys-portfolio', 'name': 'Portfolio Marketplace', 'filters': {'plan': 'portfolio'}},
    {'slug': 'sys-essentiel', 'name': 'Formule Essentiel (legacy)', 'filters': {'plan': 'essentiel'}},
    {'slug': 'sys-pro', 'name': 'Formule Pro', 'filters': {'plan': 'pro'}},
    {'slug': 'sys-galerie-pro', 'name': 'Formule Galerie Pro', 'filters': {'plan': 'pro', 'role': 'galerie'}},
    {'slug': 'sys-premium', 'name': 'Formule Premium', 'filters': {'plan': 'premium'}},
    {'slug': 'sys-membre', 'name': 'Formule Membre', 'filters': {'plan': 'membre'}},
    {'slug': 'sys-patron', 'name': 'Formule Patron', 'filters': {'plan': 'patron'}},
    {'slug': 'sys-stripe', 'name': 'Clients Stripe', 'filters': {'has_stripe': True}},
    {'slug': 'sys-abo-actif', 'name': 'Abonnement actif', 'filters': {'subscription_status': 'active', 'paid_only': True}},
    {'slug': 'sys-abo-annule', 'name': 'Abonnement annulé', 'filters': {'subscription_status': 'cancelled'}},
    {'slug': 'sys-createurs-actifs', 'name': 'Créateurs actifs (≥3 œuvres)', 'filters': {'min_artworks': 3}},
]


def ensure_system_segments() -> None:
    """Crée ou met à jour les segments système."""
    for spec in SYSTEM_SEGMENTS:
        seg = EmailSegment.query.filter_by(slug=spec['slug']).first()
        if seg is None:
            seg = EmailSegment(
                slug=spec['slug'],
                name=spec['name'],
                description=f'Segment automatique — {spec["name"]}',
                is_system=True,
            )
            db.session.add(seg)
        else:
            seg.name = spec['name']
            seg.is_system = True
        seg.filters = spec['filters']
        seg.updated_at = datetime.utcnow()
    db.session.commit()


def _user_matches_segment(user: User, filters: dict) -> bool:
    q = apply_segment_filters(User.query.filter(User.id == user.id), filters)
    return q.first() is not None


def classify_user(user: User, *, commit: bool = True) -> list[EmailSegment]:
    """Classifie un utilisateur dans tous les segments système correspondants."""
    if user.is_staff or user.role == 'admin':
        return []

    ensure_system_segments()
    system_segments = EmailSegment.query.filter_by(is_system=True).all()
    matched_ids = {s.id for s in system_segments if _user_matches_segment(user, s.filters)}

    existing = {
        m.segment_id: m
        for m in UserSegmentMembership.query.filter_by(user_id=user.id, auto_assigned=True).all()
    }

    for seg_id, membership in list(existing.items()):
        if seg_id not in matched_ids:
            db.session.delete(membership)

    added = []
    for seg in system_segments:
        if seg.id in matched_ids and seg.id not in existing:
            db.session.add(UserSegmentMembership(
                user_id=user.id,
                segment_id=seg.id,
                auto_assigned=True,
            ))
            added.append(seg)

    if commit:
        db.session.commit()
    return added


def reclassify_all_users() -> int:
    """Reclasse tous les utilisateurs (maintenance)."""
    ensure_system_segments()
    count = 0
    for user in User.query.filter(User.is_staff.is_(False), User.role != 'admin').all():
        classify_user(user, commit=False)
        count += 1
    db.session.commit()
    return count


def user_segments(user: User) -> list[EmailSegment]:
    """Segments auxquels appartient un utilisateur."""
    return (
        EmailSegment.query
        .join(UserSegmentMembership, UserSegmentMembership.segment_id == EmailSegment.id)
        .filter(UserSegmentMembership.user_id == user.id)
        .order_by(EmailSegment.name)
        .all()
    )


def segment_label(filters: dict | None) -> str:
    from .segments import preview_segment_name
    return preview_segment_name(filters)

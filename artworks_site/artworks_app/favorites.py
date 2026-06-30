"""Favoris œuvres — un like par utilisateur connecté, persisté en base."""
from __future__ import annotations

from . import db
from .models import Artwork, ArtworkFavorite


def favorite_ids_for_user(user) -> list[int]:
    if not user or not getattr(user, 'id', None):
        return []
    rows = (
        ArtworkFavorite.query.filter_by(user_id=user.id)
        .order_by(ArtworkFavorite.created_at.desc())
        .with_entities(ArtworkFavorite.artwork_id)
        .all()
    )
    return [r[0] for r in rows]


def favorite_artworks_for_user(user, *, limit: int = 48) -> list[Artwork]:
    ids = favorite_ids_for_user(user)
    if not ids:
        return []
    by_id = {a.id: a for a in Artwork.query.filter(Artwork.id.in_(ids)).all()}
    return [by_id[i] for i in ids if i in by_id][:limit]


def favorite_count_for_user(user) -> int:
    if not user or not getattr(user, 'id', None):
        return 0
    return ArtworkFavorite.query.filter_by(user_id=user.id).count()


def toggle_favorite(user, artwork_id: int) -> tuple[bool, int]:
    """Ajoute ou retire un favori. Retourne (liked, total_count)."""
    existing = ArtworkFavorite.query.filter_by(
        user_id=user.id, artwork_id=artwork_id,
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        liked = False
    else:
        db.session.add(ArtworkFavorite(user_id=user.id, artwork_id=artwork_id))
        db.session.commit()
        liked = True
    return liked, favorite_count_for_user(user)

"""Synchronisation stats DeviantArt (vues / favoris)."""
from __future__ import annotations

import logging

from .. import db
from ..models import Artwork
from .platforms import DeviantArt

log = logging.getLogger(__name__)


def sync_artwork_deviantart_stats(artwork: Artwork) -> bool:
    if not artwork.deviantart_deviation_id or not DeviantArt.is_connected():
        return False
    stats = DeviantArt.fetch_deviation_stats(artwork.deviantart_deviation_id)
    if not stats:
        return False
    artwork.deviantart_views = stats.get('views', artwork.deviantart_views or 0)
    artwork.deviantart_favorites = stats.get('favorites', artwork.deviantart_favorites or 0)
    if stats.get('url'):
        artwork.deviantart_url = stats['url']
    db.session.commit()
    return True


def sync_all_deviantart_stats(*, limit: int = 200) -> int:
    """Met à jour les stats DA pour toutes les œuvres syndiquées."""
    if not DeviantArt.is_connected():
        return 0
    q = Artwork.query.filter(
        Artwork.deviantart_deviation_id.isnot(None),
        Artwork.deviantart_deviation_id != '',
    ).order_by(Artwork.id.desc()).limit(limit)
    updated = 0
    for art in q.all():
        try:
            if sync_artwork_deviantart_stats(art):
                updated += 1
        except Exception:
            log.exception('sync DA stats artwork %s', art.id)
    return updated

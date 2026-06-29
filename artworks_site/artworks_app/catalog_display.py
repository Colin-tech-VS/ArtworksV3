"""Tri et visibilité des œuvres selon les abonnements."""

from __future__ import annotations

from datetime import datetime, timedelta

from .entitlements import collector_early_access_hours, search_rank, user_entitlements


def artwork_visible_to_viewer(artwork, viewer) -> bool:
    """Filtre avant-première collectionneur & ventes privées."""
    if getattr(artwork, 'early_access', False):
        if not viewer or not getattr(viewer, 'is_authenticated', False):
            return False
        return bool(user_entitlements(viewer).get('private_sales'))

    if not artwork.created_at:
        return True

    age = datetime.utcnow() - artwork.created_at
    if age >= timedelta(hours=48):
        return True

    # Visiteurs anonymes : catalogue public (SEO Google + découverte acheteurs)
    if not viewer or not getattr(viewer, 'is_authenticated', False):
        return True

    # Artistes, galeries, staff : accès complet
    if viewer.role != 'collectionneur':
        return True

    # Collectionneurs free : avant-première 48 h réservée Membre / Patron
    return collector_early_access_hours(viewer) >= 48


def sort_artworks(artworks, viewer=None):
    """Priorité recherche + mise en avant homepage."""
    from .entitlements import has_public_portfolio

    visible = []
    for a in artworks:
        if not artwork_visible_to_viewer(a, viewer):
            continue
        if a.owner and a.owner.role == 'artiste' and not has_public_portfolio(a.owner):
            continue
        visible.append(a)

    def key(a):
        owner = a.owner
        ent = user_entitlements(owner) if owner else {}
        featured = 1 if ent.get('homepage_featured') else 0
        boost = search_rank(owner) if owner else 0
        ts = a.created_at.timestamp() if a.created_at else 0
        return (featured, boost, ts, a.id or 0)

    return sorted(visible, key=key, reverse=True)


def featured_artworks(all_artworks, limit=8):
    """Sélection homepage : priorité Pro / Premium puis récent."""
    ranked = sort_artworks(all_artworks)
    if len(ranked) >= limit:
        return ranked[:limit]
    return ranked

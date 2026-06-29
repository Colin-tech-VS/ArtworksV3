"""Droits effectifs par rôle + formule — source unique pour l'application."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .subscriptions import ROLE_LABELS, normalize_plan, is_paid_plan, portfolio_required_for_role

_PLAN_CAPS: dict[tuple[str, str], dict[str, Any]] = {
    ('artiste', 'free'): {
        'artwork_limit': 0,
        'portfolio_public': False,
        'curatorial_monthly_limit': 0,
        'curatorial_unlimited': False,
        'homepage_featured': False,
        'search_boost': 0,
        'pro_badge': False,
        'verified_badge': False,
        'stats_level': 'none',
        'seo_profile': False,
        'seo_level': 'none',
        'marketplace_enabled': False,
        'gallery_artist_limit': 0,
        'early_access_hours': 0,
        'price_alerts': False,
        'shareable_wishlist': False,
        'collector_matching': False,
        'private_sales': False,
        'curator_session': False,
        'export_reports': False,
        'support_tier': 'community',
    },
    ('artiste', 'portfolio'): {
        'artwork_limit': 25,
        'portfolio_public': True,
        'curatorial_monthly_limit': None,
        'curatorial_unlimited': True,
        'homepage_featured': False,
        'search_boost': 2,
        'pro_badge': False,
        'verified_badge': False,
        'stats_level': 'basic',
        'seo_profile': True,
        'seo_level': 'basic',
        'marketplace_enabled': True,
        'gallery_artist_limit': 0,
        'early_access_hours': 0,
        'price_alerts': False,
        'shareable_wishlist': False,
        'collector_matching': False,
        'private_sales': False,
        'curator_session': False,
        'export_reports': False,
        'support_tier': 'email_48h',
    },
    ('artiste', 'pro'): {
        'artwork_limit': None,
        'portfolio_public': True,
        'curatorial_monthly_limit': None,
        'curatorial_unlimited': True,
        'homepage_featured': True,
        'search_boost': 4,
        'pro_badge': True,
        'verified_badge': False,
        'stats_level': 'advanced',
        'seo_profile': True,
        'seo_level': 'max',
        'marketplace_enabled': True,
        'gallery_artist_limit': 0,
        'early_access_hours': 0,
        'price_alerts': False,
        'shareable_wishlist': False,
        'collector_matching': False,
        'private_sales': False,
        'curator_session': False,
        'export_reports': True,
        'support_tier': 'priority_24h',
    },
    ('galerie', 'free'): {
        'artwork_limit': 5,
        'portfolio_public': True,
        'curatorial_monthly_limit': 1,
        'curatorial_unlimited': False,
        'homepage_featured': False,
        'search_boost': 0,
        'pro_badge': False,
        'verified_badge': False,
        'stats_level': 'none',
        'seo_profile': True,
        'seo_level': 'basic',
        'marketplace_enabled': False,
        'gallery_artist_limit': 0,
        'early_access_hours': 0,
        'price_alerts': False,
        'shareable_wishlist': False,
        'collector_matching': False,
        'private_sales': False,
        'curator_session': False,
        'export_reports': False,
        'support_tier': 'community',
    },
    ('galerie', 'pro'): {
        'artwork_limit': None,
        'portfolio_public': True,
        'curatorial_monthly_limit': None,
        'curatorial_unlimited': True,
        'homepage_featured': False,
        'search_boost': 2,
        'pro_badge': False,
        'verified_badge': False,
        'stats_level': 'basic',
        'seo_profile': True,
        'seo_level': 'basic',
        'marketplace_enabled': True,
        'gallery_artist_limit': 15,
        'early_access_hours': 0,
        'price_alerts': False,
        'shareable_wishlist': False,
        'collector_matching': False,
        'private_sales': False,
        'curator_session': False,
        'export_reports': False,
        'support_tier': 'email_48h',
    },
    ('galerie', 'premium'): {
        'artwork_limit': None,
        'portfolio_public': True,
        'curatorial_monthly_limit': None,
        'curatorial_unlimited': True,
        'homepage_featured': True,
        'search_boost': 4,
        'pro_badge': False,
        'verified_badge': True,
        'stats_level': 'advanced',
        'seo_profile': True,
        'seo_level': 'max',
        'marketplace_enabled': True,
        'gallery_artist_limit': None,
        'early_access_hours': 0,
        'price_alerts': False,
        'shareable_wishlist': False,
        'collector_matching': True,
        'private_sales': True,
        'curator_session': False,
        'export_reports': True,
        'support_tier': 'priority_24h',
    },
    ('collectionneur', 'free'): {
        'artwork_limit': None,
        'portfolio_public': True,
        'curatorial_monthly_limit': 0,
        'curatorial_unlimited': False,
        'homepage_featured': False,
        'search_boost': 0,
        'pro_badge': False,
        'verified_badge': False,
        'stats_level': 'none',
        'seo_profile': False,
        'seo_level': 'none',
        'marketplace_enabled': False,
        'gallery_artist_limit': 0,
        'early_access_hours': 0,
        'price_alerts': False,
        'shareable_wishlist': False,
        'collector_matching': False,
        'private_sales': False,
        'curator_session': False,
        'export_reports': False,
        'support_tier': 'community',
    },
    ('collectionneur', 'membre'): {
        'artwork_limit': None,
        'portfolio_public': True,
        'curatorial_monthly_limit': 0,
        'curatorial_unlimited': False,
        'homepage_featured': False,
        'search_boost': 0,
        'pro_badge': False,
        'verified_badge': False,
        'stats_level': 'basic',
        'seo_profile': False,
        'seo_level': 'none',
        'marketplace_enabled': False,
        'gallery_artist_limit': 0,
        'early_access_hours': 48,
        'price_alerts': True,
        'shareable_wishlist': True,
        'collector_matching': False,
        'private_sales': False,
        'curator_session': False,
        'export_reports': False,
        'support_tier': 'email_48h',
    },
    ('collectionneur', 'patron'): {
        'artwork_limit': None,
        'portfolio_public': True,
        'curatorial_monthly_limit': 0,
        'curatorial_unlimited': False,
        'homepage_featured': False,
        'search_boost': 0,
        'pro_badge': False,
        'verified_badge': False,
        'stats_level': 'advanced',
        'seo_profile': False,
        'seo_level': 'none',
        'marketplace_enabled': False,
        'gallery_artist_limit': 0,
        'early_access_hours': 48,
        'price_alerts': True,
        'shareable_wishlist': True,
        'collector_matching': True,
        'private_sales': True,
        'curator_session': True,
        'export_reports': False,
        'support_tier': 'priority_24h',
    },
}


def effective_plan(user) -> str:
    if not user:
        return 'free'
    role = user.role or 'collectionneur'
    plan = normalize_plan(role, user.subscription_plan)
    status = user.subscription_status or 'active'

    if status == 'expired':
        return 'free'
    if status == 'cancelled' and user.subscription_period_end:
        if user.subscription_period_end > datetime.utcnow():
            return plan
        return 'free'
    if status in ('past_due', 'active'):
        return plan
    return plan


def entitlements_for(role: str, plan_slug: str) -> dict[str, Any]:
    role = role or 'collectionneur'
    plan_slug = normalize_plan(role, plan_slug)
    caps = _PLAN_CAPS.get((role, plan_slug))
    if not caps:
        caps = _PLAN_CAPS.get((role, 'free'), {})
    return dict(caps)


def user_entitlements(user) -> dict[str, Any]:
    if getattr(user, 'role', '') == 'admin' or (getattr(user, 'is_staff', False) and user.role == 'admin'):
        return {
            'role': 'admin', 'plan': 'free', 'role_label': 'Administrateur',
            'artwork_limit': 0, 'portfolio_public': True, 'seo_level': 'max',
            'marketplace_enabled': True, 'stats_level': 'advanced',
        }
    role = user.role or 'collectionneur'
    plan = effective_plan(user)
    caps = entitlements_for(role, plan)
    caps['role'] = role
    caps['plan'] = plan
    caps['role_label'] = ROLE_LABELS.get(role, role.capitalize())
    caps['is_paid'] = is_paid_plan(role, plan)
    return caps


def has_public_portfolio(user) -> bool:
    ent = user_entitlements(user)
    if not ent.get('portfolio_public'):
        return False
    from .stripe_connect import connect_required_for, connect_ready
    if connect_required_for(user) and not connect_ready(user):
        return False
    return True


def portfolio_subscription_active(user) -> bool:
    """Abonnement payant avec droit portfolio (avant Connect)."""
    return bool(user_entitlements(user).get('portfolio_public'))


def can_publish_artwork(user) -> tuple[bool, str | None]:
    from .monetization import commission_percent_label
    ent = user_entitlements(user)
    if portfolio_required_for_role(user.role or '') and not ent.get('portfolio_public'):
        from .subscriptions import plan_for_role, price_label
        pf = plan_for_role('artiste', 'portfolio')
        price = price_label(pf) if pf else '9,99 €'
        comm = commission_percent_label()
        return False, (
            f'Activez votre Portfolio Marketplace ({price}/mois) pour publier vos œuvres '
            f'et vendre en ligne. Commission {comm} uniquement à la vente.'
        )
    limit = ent.get('artwork_limit')
    if limit is None:
        return True, None
    count = len(user.artworks)
    if count >= limit:
        return False, (
            f'Limite de {limit} œuvre{"s" if limit > 1 else ""} atteinte '
            f'({ent["role_label"]} — {plan_for_display(user)}). Passez à une formule supérieure.'
        )
    return True, None


def plan_for_display(user) -> str:
    from .subscriptions import plan_for_role
    p = plan_for_role(user.role or 'collectionneur', effective_plan(user))
    return p['name'] if p else 'Compte'


def can_regenerate_curatorial(user) -> tuple[bool, str | None]:
    ent = user_entitlements(user)
    if ent.get('curatorial_unlimited'):
        return True, None
    limit = ent.get('curatorial_monthly_limit') or 0
    if limit <= 0:
        return False, 'Note curatoriale IA incluse avec Portfolio Marketplace ou supérieur.'
    used = _curatorial_used_this_month(user)
    if used >= limit:
        return False, f'Quota curatoral atteint ({limit}/mois).'
    return True, None


def _curatorial_used_this_month(user) -> int:
    month = datetime.utcnow().strftime('%Y-%m')
    if (user.curatorial_quota_month or '') != month:
        return 0
    return user.curatorial_quota_used or 0


def record_curatorial_use(user) -> None:
    month = datetime.utcnow().strftime('%Y-%m')
    if (user.curatorial_quota_month or '') != month:
        user.curatorial_quota_month = month
        user.curatorial_quota_used = 1
    else:
        user.curatorial_quota_used = (user.curatorial_quota_used or 0) + 1


def search_rank(user) -> int:
    return int(user_entitlements(user).get('search_boost') or 0)


def collector_early_access_hours(user) -> int:
    if not user or not user.is_authenticated:
        return 0
    if user.role != 'collectionneur':
        return 9999
    return int(user_entitlements(user).get('early_access_hours') or 0)


def artwork_limit(user) -> int | None:
    return user_entitlements(user).get('artwork_limit')


def curatorial_quota_status(user) -> dict[str, Any]:
    ent = user_entitlements(user)
    if ent.get('curatorial_unlimited'):
        return {'unlimited': True, 'used': 0, 'limit': None, 'remaining': None}
    limit = ent.get('curatorial_monthly_limit') or 0
    used = _curatorial_used_this_month(user)
    return {
        'unlimited': False,
        'used': used,
        'limit': limit,
        'remaining': max(0, limit - used) if limit else 0,
    }

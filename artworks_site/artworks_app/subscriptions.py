"""Catalogue d'abonnements Artworks V3 — aligné V2 staging (sans offre « site web »).

Modèle : portfolio payant + commission à la vente (tarifs live via CRM).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

_PLAN_TEMPLATES: dict[str, dict[str, dict[str, Any]]] = {
    'artiste': {
        'free': {
            'slug': 'free',
            'name': 'Compte',
            'badge': None,
            'tagline': 'Inscription — activez votre portfolio pour publier et vendre.',
            'price_cents': 0,
            'interval': None,
            'highlight': False,
            'cta': 'Activer le portfolio',
            'features': [
                'Espace personnel (tableau de bord)',
                'Préparation du profil (non public)',
                'Accès à l\'explorateur Artworks',
            ],
            'missing': [
                'Portfolio public & SEO Google',
                'Publication d\'œuvres',
                'Vente en ligne (marketplace)',
            ],
        },
        'portfolio': {
            'slug': 'portfolio',
            'name': 'Portfolio Marketplace',
            'badge': 'Essentiel',
            'tagline': 'Portfolio public, SEO et vente en ligne — commission uniquement à la vente.',
            'price_cents': 999,
            'interval': 'month',
            'highlight': True,
            'cta': 'Activer mon portfolio',
            'features': [
                'Portfolio public optimisé SEO Google',
                'Jusqu\'à 25 œuvres en ligne',
                'Marketplace & paiement Stripe sécurisé',
                'Commission {commission} uniquement à la vente (frais Stripe inclus)',
                'Note curatoriale IA illimitée',
                'Statistiques de vues & favoris',
                'Support email sous 48 h',
            ],
            'missing': [
                'Mise en avant homepage',
                'Badge Artiste Pro',
            ],
        },
        'pro': {
            'slug': 'pro',
            'name': 'Artiste Pro',
            'badge': 'Visibilité max',
            'tagline': 'Référencement maximal et visibilité premium.',
            'price_cents': 2499,
            'interval': 'month',
            'highlight': False,
            'cta': 'Passer Artiste Pro',
            'features': [
                'Tout Portfolio Marketplace, plus :',
                'Œuvres illimitées',
                'SEO avancé (JSON-LD, rich snippets)',
                'Mise en avant sur la homepage',
                'Badge « Artiste Pro » sur votre profil',
                'Priorité dans les résultats de recherche',
                'Commission {commission} à la vente',
                'Support prioritaire sous 24 h',
            ],
            'missing': [],
        },
    },
    'galerie': {
        'free': {
            'slug': 'free',
            'name': 'Découverte',
            'badge': None,
            'tagline': 'Page galerie limitée — idéal pour tester la plateforme.',
            'price_cents': 0,
            'interval': None,
            'highlight': False,
            'cta': 'Rester en Découverte',
            'features': [
                'Page galerie publique (SEO basique)',
                'Jusqu\'à 5 œuvres listées',
                'Contact collectionneurs',
            ],
            'missing': [
                'Multi-artistes',
                'Marketplace & ventes en ligne',
                'CRM collectionneurs',
            ],
        },
        'pro': {
            'slug': 'pro',
            'name': 'Galerie Pro',
            'badge': 'Recommandé',
            'tagline': 'Catalogue multi-artistes et ventes en ligne.',
            'price_cents': 7900,
            'interval': 'month',
            'highlight': True,
            'cta': 'Activer Galerie Pro',
            'features': [
                'Jusqu\'à 15 artistes rattachés',
                'Œuvres illimitées — SEO galerie optimisé',
                'Marketplace & demandes d\'achat',
                'Commission {commission} sur ventes plateforme',
                'Tableau de bord multi-artistes',
                'Statistiques par artiste & par œuvre',
                'Support dédié sous 48 h',
            ],
            'missing': [
                'Badge « Galerie vérifiée »',
            ],
        },
        'premium': {
            'slug': 'premium',
            'name': 'Galerie Premium',
            'badge': 'Sur mesure',
            'tagline': 'Pour galeries établies et foires internationales.',
            'price_cents': 12900,
            'interval': 'month',
            'highlight': False,
            'cta': 'Passer en Premium',
            'features': [
                'Artistes illimités',
                'SEO maximal (pages, artistes, œuvres)',
                'Badge « Galerie vérifiée »',
                'Mise en avant éditoriale',
                'Matching artistes & collectionneurs',
                'Commission {commission} — ventes privées',
                'Exports & rapports mensuels',
                'Account manager & support 24 h',
            ],
            'missing': [],
        },
    },
    'collectionneur': {
        'free': {
            'slug': 'free',
            'name': 'Découverte',
            'badge': None,
            'tagline': 'Explorez, suivez et enregistrez vos coups de cœur.',
            'price_cents': 0,
            'interval': None,
            'highlight': False,
            'cta': 'Rester en Découverte',
            'features': [
                'Accès complet à l\'explorateur',
                'Liste de favoris illimitée',
                'Profil collectionneur',
            ],
            'missing': [
                'Accès avant-première (48 h)',
                'Alertes prix en temps réel',
            ],
        },
        'membre': {
            'slug': 'membre',
            'name': 'Membre',
            'badge': 'Populaire',
            'tagline': 'Soyez informé en premier des nouvelles pièces.',
            'price_cents': 900,
            'interval': 'month',
            'highlight': True,
            'cta': 'Devenir Membre',
            'features': [
                'Alertes prix & disponibilité',
                'Accès avant-première (48 h)',
                'Wishlist partageable (SEO privé)',
                'Historique & notes privées',
                'Newsletter curatée hebdomadaire',
            ],
            'missing': [
                'Sessions conseil curatorales',
            ],
        },
        'patron': {
            'slug': 'patron',
            'name': 'Patron',
            'badge': 'Exclusif',
            'tagline': 'Accompagnement curatoral pour bâtir votre collection.',
            'price_cents': 1900,
            'interval': 'month',
            'highlight': False,
            'cta': 'Devenir Patron',
            'features': [
                'Tout Membre, plus :',
                '1 session conseil curatoral / mois',
                'Invitations vernissages & previews',
                'Matching artistes selon vos critères',
                'Accès ventes privées',
                'Support direct prioritaire',
            ],
            'missing': [],
        },
    },
}

# Alias rétrocompatibilité (catalogue live — préférer role_plans_catalog())
ROLE_PLANS = _PLAN_TEMPLATES

ROLE_LABELS = {
    'artiste': 'Artiste',
    'galerie': 'Galerie',
    'collectionneur': 'Collectionneur',
}

_LEGACY_PLAN_MAP = {
    'artiste': {'essentiel': 'portfolio', 'galerie': 'free', 'decouverte': 'free'},
    'galerie': {'essentiel': 'free', 'galerie_pro': 'pro'},
    'collectionneur': {'essentiel': 'free', 'pro': 'free', 'galerie': 'free', 'premium': 'membre'},
}


def role_plans_catalog() -> dict[str, dict[str, dict[str, Any]]]:
    from .pricing_store import role_plans_catalog as _live
    return _live()


def normalize_plan(role: str, plan: str | None) -> str:
    role = role or 'collectionneur'
    slug = (plan or 'free').strip().lower()
    catalog = _PLAN_TEMPLATES.get(role, _PLAN_TEMPLATES['collectionneur'])
    if slug in catalog:
        return slug
    mapped = _LEGACY_PLAN_MAP.get(role, {}).get(slug)
    if mapped and mapped in catalog:
        return mapped
    return 'free'


def plans_for_role(role: str) -> list[dict[str, Any]]:
    from .pricing_store import finalize_plan
    role = role or 'collectionneur'
    catalog = _PLAN_TEMPLATES.get(role, _PLAN_TEMPLATES['collectionneur'])
    return [finalize_plan(role, deepcopy(catalog[s])) for s in catalog.keys()]


def plan_for_role(role: str, slug: str) -> dict[str, Any] | None:
    from .pricing_store import finalize_plan
    role = role or 'collectionneur'
    slug = normalize_plan(role, slug)
    catalog = _PLAN_TEMPLATES.get(role, _PLAN_TEMPLATES['collectionneur'])
    p = catalog.get(slug)
    return finalize_plan(role, deepcopy(p)) if p else None


def is_paid_plan(role: str, slug: str) -> bool:
    p = plan_for_role(role, slug)
    return bool(p and p.get('price_cents', 0) > 0)


def price_label(plan: dict[str, Any]) -> str:
    from .pricing_store import cents_to_euros_label
    return cents_to_euros_label(int(plan.get('price_cents') or 0))


def stripe_product_name(role: str, plan: dict[str, Any]) -> str:
    role_label = ROLE_LABELS.get(role, role.capitalize())
    return f'Artworks {role_label} — {plan["name"]}'


def portfolio_required_for_role(role: str) -> bool:
    return role == 'artiste'

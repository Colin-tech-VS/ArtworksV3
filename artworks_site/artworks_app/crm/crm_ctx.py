"""Shared CRM template context — nav counts, badge labels."""
from __future__ import annotations

from ..models import Artwork, CmsPage, EmailCampaign, EmailSegment, SocialPost, User

ROLE_LABELS = {
    'artiste': 'Artiste',
    'galerie': 'Galerie',
    'collectionneur': 'Collectionneur',
    'admin': 'Administrateur',
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

SUB_STATUS_LABELS = {
    'active': 'Actif',
    'cancelled': 'Annulé',
    'past_due': 'Impayé',
    'expired': 'Expiré',
}

ARTWORK_STATUS_LABELS = {
    'dispo': 'Disponible',
    'reserve': 'Réservé',
    'vendu': 'Vendu',
}

CAMPAIGN_STATUS_LABELS = {
    'draft': 'Brouillon',
    'sending': 'En cours',
    'sent': 'Envoyée',
    'failed': 'Échec',
}

NAV_META = {
    'overview': {'label': "Vue d'ensemble", 'section': 'Pilotage'},
    'analytics': {'label': 'Analytics', 'section': 'Pilotage'},
    'users': {'label': 'Utilisateurs', 'section': 'Communauté'},
    'artworks': {'label': 'Portfolio', 'section': 'Communauté'},
    'pages': {'label': 'Pages CMS', 'section': 'Contenu'},
    'segments': {'label': 'Segmentation', 'section': 'Marketing'},
    'emails': {'label': 'Emails', 'section': 'Marketing'},
    'social': {'label': 'Réseaux sociaux', 'section': 'Marketing'},
    'integrations': {'label': 'Intégrations', 'section': 'Système'},
    'pricing': {'label': 'Tarifs & commission', 'section': 'Système'},
}


def crm_nav_counts() -> dict:
    return {
        'users': User.query.filter(User.is_staff.is_(False), User.role != 'admin').count(),
        'artworks': Artwork.query.count(),
        'pages': CmsPage.query.count(),
        'pages_draft': CmsPage.query.filter_by(published=False).count(),
        'segments': EmailSegment.query.count(),
        'campaigns': EmailCampaign.query.count(),
        'campaigns_draft': EmailCampaign.query.filter_by(status='draft').count(),
        'social_posts': SocialPost.query.count(),
        'social_draft': SocialPost.query.filter_by(status='draft').count(),
    }

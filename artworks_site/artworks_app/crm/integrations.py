"""CRM — statut des intégrations / variables d'environnement."""
from __future__ import annotations

import os
import smtplib
import ssl
import urllib.error
import urllib.request

from flask import current_app

from ..mail_config import smtp_config


def _mask(val: str | None, show: int = 4) -> str:
    if not val:
        return ''
    if len(val) <= show * 2:
        return '••••'
    return val[:show] + '…' + val[-show:]


def _check_mistral() -> dict:
    key = current_app.config.get('MISTRAL_API_KEY', '')
    if not key:
        return {'id': 'mistral', 'name': 'Mistral AI', 'category': 'IA',
                'status': 'missing', 'message': 'MISTRAL_API_KEY non définie', 'env_keys': ['MISTRAL_API_KEY']}
    try:
        req = urllib.request.Request(
            'https://api.mistral.ai/v1/models',
            headers={'Authorization': f'Bearer {key}', 'Accept': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            ok = r.status == 200
        return {'id': 'mistral', 'name': 'Mistral AI', 'category': 'IA',
                'status': 'connected' if ok else 'error',
                'message': 'API accessible' if ok else 'Réponse inattendue',
                'env_keys': ['MISTRAL_API_KEY', 'MISTRAL_MODEL', 'MISTRAL_MODEL_HEAVY'],
                'detail': _mask(key)}
    except Exception as exc:
        return {'id': 'mistral', 'name': 'Mistral AI', 'category': 'IA',
                'status': 'error', 'message': str(exc)[:120],
                'env_keys': ['MISTRAL_API_KEY'], 'detail': _mask(key)}


def _check_stripe() -> dict:
    sk = current_app.config.get('STRIPE_SECRET_KEY', '')
    pk = current_app.config.get('STRIPE_PUBLISHABLE_KEY', '')
    wh = current_app.config.get('STRIPE_WEBHOOK_SECRET', '')
    demo = current_app.config.get('STRIPE_DEMO_MODE')
    if not sk:
        return {'id': 'stripe', 'name': 'Stripe', 'category': 'Paiements',
                'status': 'missing', 'message': 'STRIPE_SECRET_KEY manquante',
                'env_keys': ['STRIPE_SECRET_KEY', 'STRIPE_PUBLISHABLE_KEY', 'STRIPE_WEBHOOK_SECRET']}
    mode = 'live' if sk.startswith('sk_live_') else 'test'
    if demo:
        status, msg = 'warning', 'Mode démo actif (STRIPE_DEMO_MODE)'
    else:
        status, msg = 'connected', f'Clés {mode} configurées'
    return {'id': 'stripe', 'name': 'Stripe', 'category': 'Paiements',
            'status': status, 'message': msg,
            'env_keys': ['STRIPE_SECRET_KEY', 'STRIPE_PUBLISHABLE_KEY', 'STRIPE_WEBHOOK_SECRET', 'STRIPE_DEMO_MODE'],
            'detail': f'sk: {_mask(sk)} · pk: {"✓" if pk else "✗"} · webhook: {"✓" if wh else "✗"}'}


def _check_smtp_live() -> dict:
    cfg = smtp_config()
    keys = ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD', 'SMTP_FROM',
            'MAIL_SERVER', 'MAIL_USERNAME', 'MAIL_PASSWORD', 'BREVO_SMTP_KEY']
    if not cfg['ready']:
        missing = []
        if not cfg['host']:
            missing.append('SMTP_HOST')
        if not cfg['user']:
            missing.append('SMTP_USER')
        if not cfg['password']:
            missing.append('SMTP_PASSWORD')
        return {'id': 'smtp', 'name': 'Email SMTP (Brevo / LWS)', 'category': 'Email',
                'status': 'missing',
                'message': f"Variables manquantes : {', '.join(missing) or 'identifiants'}",
                'env_keys': keys,
                'detail': cfg['host'] or '(host vide)'}
    port = int(cfg['port'])
    try:
        ctx = ssl.create_default_context()
        if cfg['use_ssl']:
            server = smtplib.SMTP_SSL(cfg['host'], port, timeout=12, context=ctx)
        else:
            server = smtplib.SMTP(cfg['host'], port, timeout=12)
        with server as s:
            s.ehlo()
            if not cfg['use_ssl'] and cfg['use_tls']:
                s.starttls(context=ctx)
                s.ehlo()
            s.login(cfg['user'], cfg['password'])
        mode = 'SSL' if cfg['use_ssl'] else 'STARTTLS'
        return {'id': 'smtp', 'name': 'Email SMTP', 'category': 'Email',
                'status': 'connected',
                'message': f"Connexion OK ({cfg['host']}:{port}, {mode})",
                'env_keys': keys,
                'detail': f"{cfg['user']} · expéditeur {cfg['from_email']}"}
    except smtplib.SMTPAuthenticationError:
        return {'id': 'smtp', 'name': 'Email SMTP', 'category': 'Email',
                'status': 'error', 'message': 'Authentification refusée — vérifiez SMTP_USER / SMTP_PASSWORD',
                'env_keys': keys, 'detail': cfg['host']}
    except Exception as exc:
        return {'id': 'smtp', 'name': 'Email SMTP', 'category': 'Email',
                'status': 'error', 'message': str(exc)[:140],
                'env_keys': keys, 'detail': cfg['host']}


def _check_google_oauth() -> dict:
    cid = current_app.config.get('GOOGLE_OAUTH_CLIENT_ID', '')
    secret = current_app.config.get('GOOGLE_OAUTH_CLIENT_SECRET', '')
    if not cid or not secret:
        return {
            'id': 'google_oauth', 'name': 'Google OAuth (connexion)', 'category': 'Authentification',
            'status': 'missing', 'message': 'GOOGLE_OAUTH_CLIENT_ID / SECRET non définis',
            'env_keys': ['GOOGLE_OAUTH_CLIENT_ID', 'GOOGLE_OAUTH_CLIENT_SECRET'],
        }
    from ..google_oauth import redirect_uri
    return {
        'id': 'google_oauth', 'name': 'Google OAuth (connexion)', 'category': 'Authentification',
        'status': 'configured', 'message': 'Connexion / inscription Google activée',
        'env_keys': ['GOOGLE_OAUTH_CLIENT_ID', 'GOOGLE_OAUTH_CLIENT_SECRET'],
        'detail': redirect_uri(),
    }


def _check_google_places() -> dict:
    key = current_app.config.get('GOOGLE_PLACES_API_KEY', '')
    if not key:
        return {'id': 'google_places', 'name': 'Google Places', 'category': 'Cartographie',
                'status': 'missing', 'message': 'GOOGLE_PLACES_API_KEY non définie',
                'env_keys': ['GOOGLE_PLACES_API_KEY']}
    return {'id': 'google_places', 'name': 'Google Places', 'category': 'Cartographie',
            'status': 'configured', 'message': 'Clé présente (autocomplete profil)',
            'env_keys': ['GOOGLE_PLACES_API_KEY'], 'detail': _mask(key)}


def _check_site() -> dict:
    url = current_app.config.get('SITE_URL', '')
    if not url:
        return {'id': 'site', 'name': 'Site URL', 'category': 'Application',
                'status': 'missing', 'message': 'SITE_URL non définie',
                'env_keys': ['SITE_URL']}
    return {'id': 'site', 'name': 'Site URL', 'category': 'Application',
            'status': 'configured', 'message': url, 'env_keys': ['SITE_URL', 'SECRET_KEY']}


def _check_database() -> dict:
    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if 'sqlite' in uri:
        st = 'configured'
        msg = 'SQLite (développement)'
    elif uri:
        st = 'configured'
        msg = 'PostgreSQL / DATABASE_URL'
    else:
        st = 'missing'
        msg = 'DATABASE_URL manquante'
    return {'id': 'database', 'name': 'Base de données', 'category': 'Application',
            'status': st, 'message': msg, 'env_keys': ['DATABASE_URL']}


def _check_social() -> dict:
    from ..social.platforms import DeviantArt, Facebook, Instagram, Pinterest
    keys = [
        'FACEBOOK_PAGE_ACCESS_TOKEN', 'FACEBOOK_PAGE_ID', 'INSTAGRAM_USER_ID',
        'INSTAGRAM_ACCESS_TOKEN', 'DEVIANTART_CLIENT_ID', 'DEVIANTART_CLIENT_SECRET',
        'PINTEREST_CLIENT_ID', 'PINTEREST_CLIENT_SECRET', 'PINTEREST_DEFAULT_BOARD_ID',
    ]
    fb = Facebook.is_configured()
    ig = Instagram.is_configured()
    da = DeviantArt.is_connected()
    pt = Pinterest.is_connected()
    parts = []
    if fb:
        parts.append('FB')
    if ig:
        parts.append('IG')
    if da:
        parts.append('DA')
    if pt:
        parts.append('PT')
    if parts:
        st, msg = 'connected', f'Actif : {", ".join(parts)}'
    elif Facebook.is_configured() or DeviantArt.is_configured() or Pinterest.is_configured():
        st, msg = 'configured', 'Clés présentes — OAuth DA/Pinterest requis'
    else:
        st, msg = 'missing', 'Variables réseaux sociaux absentes'
    return {'id': 'social', 'name': 'Réseaux sociaux', 'category': 'Marketing',
            'status': st, 'message': msg, 'env_keys': keys}


def integrations_overview() -> dict:
    items = [
        _check_smtp_live(),
        _check_mistral(),
        _check_stripe(),
        _check_social(),
        _check_google_places(),
        _check_google_oauth(),
        _check_site(),
        _check_database(),
    ]
    connected = sum(1 for i in items if i['status'] == 'connected')
    configured = sum(1 for i in items if i['status'] in ('connected', 'configured'))
    errors = sum(1 for i in items if i['status'] == 'error')
    missing = sum(1 for i in items if i['status'] == 'missing')
    return {
        'items': items,
        'connected': connected,
        'configured': configured,
        'errors': errors,
        'missing': missing,
        'total': len(items),
    }

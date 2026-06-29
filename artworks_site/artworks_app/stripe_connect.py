"""Stripe Connect Express — encaissement des ventes (artistes & galeries)."""
from __future__ import annotations

import logging
from datetime import datetime

from flask import current_app, url_for

from . import db

log = logging.getLogger(__name__)

try:
    import stripe  # type: ignore[import-untyped]
except ImportError:
    stripe = None


def _stripe_ready() -> bool:
    if stripe is None:
        return False
    key = current_app.config.get('STRIPE_SECRET_KEY', '')
    demo = current_app.config.get('STRIPE_DEMO_MODE', False)
    return bool(key) and not demo


def connect_required_for(user) -> bool:
    """Connect obligatoire pour publier / vendre — artiste avec abo portfolio, galerie avec marketplace."""
    if not user or user.role not in ('artiste', 'galerie'):
        return False
    from .entitlements import portfolio_subscription_active, user_entitlements
    if user.role == 'artiste':
        return portfolio_subscription_active(user)
    ent = user_entitlements(user)
    return bool(ent.get('marketplace_enabled'))


def connect_ready(user) -> bool:
    if not user or not user.stripe_connect_id:
        return False
    return bool(getattr(user, 'stripe_connect_charges_enabled', False))


def connect_status(user) -> dict:
    from .entitlements import portfolio_subscription_active, user_entitlements

    role = getattr(user, 'role', '') if user else ''
    show_section = role in ('artiste', 'galerie')
    required = connect_required_for(user)
    ready = connect_ready(user) if required else False
    has_account = bool(user and user.stripe_connect_id)
    ent = user_entitlements(user) if user else {}

    if role == 'artiste':
        needs_subscription = not portfolio_subscription_active(user)
    elif role == 'galerie':
        needs_subscription = not ent.get('marketplace_enabled')
    else:
        needs_subscription = False

    can_connect = required and not needs_subscription
    needs_connect = can_connect and not ready

    return {
        'show_section': show_section,
        'required': required,
        'ready': ready,
        'has_account': has_account,
        'pending': can_connect and has_account and not ready,
        'missing': can_connect and not has_account,
        'needs_subscription': needs_subscription,
        'needs_connect': needs_connect,
        'can_connect': can_connect,
        'portfolio_public_blocked': required and not ready,
        'account_id': user.stripe_connect_id if user else None,
        'stripe_configured': _stripe_ready(),
        'demo_mode': bool(current_app.config.get('STRIPE_DEMO_MODE')),
    }


def _business_type(user) -> str:
    return 'company' if user.role == 'galerie' else 'individual'


def create_express_account(user) -> str | None:
    if not _stripe_ready():
        return None
    try:
        acct = stripe.Account.create(
            type='express',
            country='FR',
            email=user.email,
            capabilities={
                'card_payments': {'requested': True},
                'transfers': {'requested': True},
            },
            business_type=_business_type(user),
            metadata={
                'user_id': str(user.id),
                'role': user.role or '',
            },
        )
        return acct.id
    except Exception:
        log.exception('stripe express account create failed')
        return None


def create_account_link(*, account_id: str, return_url: str, refresh_url: str) -> str | None:
    if not _stripe_ready():
        return None
    try:
        link = stripe.AccountLink.create(
            account=account_id,
            return_url=return_url,
            refresh_url=refresh_url,
            type='account_onboarding',
        )
        return link.url
    except Exception:
        log.exception('stripe account link failed')
        return None


def account_link_error_hint(return_url: str) -> str:
    key = current_app.config.get('STRIPE_SECRET_KEY', '')
    if key.startswith('sk_live_') and return_url.startswith('http://'):
        return (
            'Stripe LIVE exige HTTPS pour l\'onboarding. '
            'En local : clés test (sk_test_…) ou tunnel HTTPS (ngrok).'
        )
    return (
        'Connexion Stripe indisponible. Vérifiez que Stripe Connect est activé '
        'sur votre compte Stripe, ou utilisez le mode simulation ci-dessous.'
    )


def retrieve_account(account_id: str):
    if not _stripe_ready():
        return None
    try:
        return stripe.Account.retrieve(account_id)
    except Exception:
        log.exception('stripe account retrieve failed')
        return None


def sync_connect_status(user) -> bool:
    if not user.stripe_connect_id:
        user.stripe_connect_charges_enabled = False
        user.stripe_connect_payouts_enabled = False
        db.session.commit()
        return False
    if user.stripe_connect_id.startswith('acct_demo_'):
        user.stripe_connect_charges_enabled = True
        user.stripe_connect_payouts_enabled = True
        if not user.stripe_connected_at:
            user.stripe_connected_at = datetime.utcnow()
        db.session.commit()
        return True
    acct = retrieve_account(user.stripe_connect_id)
    if not acct:
        return False
    user.stripe_connect_charges_enabled = bool(acct.get('charges_enabled'))
    user.stripe_connect_payouts_enabled = bool(acct.get('payouts_enabled'))
    if user.stripe_connect_charges_enabled and not user.stripe_connected_at:
        user.stripe_connected_at = datetime.utcnow()
    db.session.commit()
    return user.stripe_connect_charges_enabled


def create_login_link(account_id: str) -> str | None:
    if not _stripe_ready() or account_id.startswith('acct_demo_'):
        return None
    try:
        link = stripe.Account.create_login_link(account_id)
        return link.url
    except Exception:
        log.exception('stripe login link failed')
        return None


def demo_connect_user(user) -> None:
    user.stripe_connect_id = f'acct_demo_{user.id}'
    user.stripe_connect_charges_enabled = True
    user.stripe_connect_payouts_enabled = True
    user.stripe_connected_at = datetime.utcnow()
    db.session.commit()


def can_simulate_connect() -> bool:
    """Simulation locale si Stripe Connect indisponible (dev / démo)."""
    if current_app.config.get('STRIPE_DEMO_MODE'):
        return True
    if not current_app.config.get('STRIPE_ENABLED'):
        return True
    site = (current_app.config.get('SITE_URL') or '').lower()
    if '127.0.0.1' in site or 'localhost' in site:
        return True
    return False


def start_onboarding(user) -> tuple[str | None, str]:
    if not connect_required_for(user):
        return None, 'Activez d\'abord un abonnement avec vente en ligne.'

    if current_app.config.get('STRIPE_DEMO_MODE'):
        demo_connect_user(user)
        return None, 'ok_demo'

    if not _stripe_ready():
        if can_simulate_connect():
            demo_connect_user(user)
            return None, 'ok_demo'
        return None, 'Stripe n\'est pas configuré sur la plateforme.'

    account_id = user.stripe_connect_id
    if not account_id:
        account_id = create_express_account(user)
        if not account_id:
            if can_simulate_connect():
                demo_connect_user(user)
                return None, 'ok_demo'
            return None, 'Impossible de créer votre compte Stripe (Connect activé sur le dashboard Stripe ?).'
        user.stripe_connect_id = account_id
        db.session.commit()

    return_url = url_for('main.stripe_connect_callback', _external=True)
    refresh_url = url_for('main.stripe_connect_start', _external=True)
    link = create_account_link(
        account_id=account_id,
        return_url=return_url,
        refresh_url=refresh_url,
    )
    if not link:
        if can_simulate_connect():
            demo_connect_user(user)
            return None, 'ok_demo'
        return None, account_link_error_hint(return_url)
    return link, 'ok'


def payout_label_for_role(role: str) -> str:
    if role == 'galerie':
        return 'Encaissez les ventes de votre galerie directement sur votre compte bancaire.'
    return 'Encaissez le montant de vos ventes d\'œuvres directement sur votre compte bancaire.'

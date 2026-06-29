"""Marketplace — achat d'œuvres avec commission plateforme (18 %)."""
from __future__ import annotations

import logging
import secrets

from flask import current_app, url_for

from . import db
from .monetization import commission_cents, commission_rate
from .models import Artwork

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


def create_artwork_checkout(*, artwork: Artwork, buyer_email: str, success_url: str, cancel_url: str) -> tuple[str | None, str]:
    if not _stripe_ready():
        return None, 'Paiements Stripe non configurés.'
    if artwork.status == 'reserve' or not artwork.price:
        return None, 'Cette œuvre n\'est plus disponible à l\'achat.'
    if not artwork.owner:
        return None, 'Vendeur introuvable.'

    from .entitlements import user_entitlements
    if not user_entitlements(artwork.owner).get('marketplace_enabled'):
        return None, 'La vente en ligne n\'est pas activée pour ce vendeur.'

    gross = int(round(float(artwork.price) * 100))
    if gross < 100:
        return None, 'Prix invalide.'

    fee = commission_cents(gross)
    order_no = secrets.token_hex(6).upper()
    image_url = None
    try:
        from flask import url_for as uf
        if artwork.image:
            image_url = uf('static', filename=f'uploads/{artwork.image}' if '/' not in artwork.image else artwork.image, _external=True)
    except Exception:
        pass

    product_data = {
        'name': (artwork.title or 'Œuvre')[:120],
        'metadata': {
            'artwork_id': str(artwork.id),
            'seller_id': str(artwork.user_id),
            'order_number': order_no,
        },
    }
    if image_url and image_url.startswith('http'):
        product_data['images'] = [image_url]

    params = {
        'mode': 'payment',
        'customer_email': buyer_email,
        'line_items': [{
            'price_data': {
                'currency': 'eur',
                'product_data': product_data,
                'unit_amount': gross,
            },
            'quantity': 1,
        }],
        'success_url': success_url + ('&' if '?' in success_url else '?') + 'session_id={CHECKOUT_SESSION_ID}',
        'cancel_url': cancel_url,
        'metadata': {
            'kind': 'artworks_sale',
            'artwork_id': str(artwork.id),
            'seller_id': str(artwork.user_id),
            'order_number': order_no,
            'commission_cents': str(fee),
            'gross_cents': str(gross),
        },
        'payment_intent_data': {
            'metadata': {'order_number': order_no, 'artwork_id': str(artwork.id)},
        },
    }

    dest = getattr(artwork.owner, 'stripe_connect_id', None)
    if dest:
        params['payment_intent_data']['application_fee_amount'] = fee
        params['payment_intent_data']['transfer_data'] = {'destination': dest}

    try:
        session = stripe.checkout.Session.create(**params)
        return session.url, 'ok'
    except Exception as exc:
        log.exception('marketplace checkout failed')
        return None, str(exc)


def fulfill_artwork_sale(session: dict) -> bool:
    meta = dict(session.get('metadata') or {})
    if meta.get('kind') != 'artworks_sale':
        return False
    try:
        artwork_id = int(meta.get('artwork_id') or 0)
    except (TypeError, ValueError):
        return False
    artwork = Artwork.query.get(artwork_id)
    if not artwork:
        return False
    artwork.status = 'reserve'
    db.session.commit()
    return True

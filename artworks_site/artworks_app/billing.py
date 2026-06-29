"""Stripe Checkout & webhooks pour les abonnements Artworks V3."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from flask import current_app

from . import db
from .subscriptions import is_paid_plan, normalize_plan, plan_for_role, stripe_product_name
from .entitlements import user_entitlements

log = logging.getLogger(__name__)

try:
    import stripe  # type: ignore[import-untyped]
except ImportError:
    stripe = None


def stripe_ready() -> bool:
    return _stripe_ready()


def _stripe_ready() -> bool:
    if stripe is None:
        return False
    key = current_app.config.get('STRIPE_SECRET_KEY', '')
    demo = current_app.config.get('STRIPE_DEMO_MODE', False)
    return bool(key) and not demo


def configure_stripe(app) -> None:
    key = app.config.get('STRIPE_SECRET_KEY', '')
    if stripe and key:
        stripe.api_key = key


def _ts_to_dt(ts) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OSError):
        return None


def _apply_plan_perks(user) -> None:
    import secrets
    ent = user_entitlements(user)
    if ent.get('shareable_wishlist') and not user.wishlist_share_token:
        user.wishlist_share_token = secrets.token_urlsafe(12)[:32]


def _sync_user_subscription(user, *, plan_slug: str, status: str,
                            subscription_id: str | None = None,
                            customer_id: str | None = None,
                            period_end: datetime | None = None,
                            since: datetime | None = None) -> None:
    role = user.role or 'collectionneur'
    user.subscription_plan = normalize_plan(role, plan_slug)
    user.subscription_status = status
    if subscription_id is not None:
        user.stripe_subscription_id = subscription_id or None
    if customer_id:
        user.stripe_customer_id = customer_id
    if period_end is not None:
        user.subscription_period_end = period_end
    if since is not None:
        user.subscription_since = since
    elif status == 'active' and user.subscription_plan != 'free' and not user.subscription_since:
        user.subscription_since = datetime.utcnow()
    if user.subscription_plan == 'free':
        user.stripe_subscription_id = None
        user.subscription_period_end = None
        if status == 'active':
            user.subscription_status = 'active'
    _apply_plan_perks(user)
    db.session.commit()


def get_or_create_customer(user) -> str | None:
    if not _stripe_ready():
        return None
    if user.stripe_customer_id:
        return user.stripe_customer_id
    try:
        cust = stripe.Customer.create(
            email=user.email,
            name=user.name,
            metadata={'user_id': str(user.id), 'role': user.role or ''},
        )
        user.stripe_customer_id = cust.id
        db.session.commit()
        return cust.id
    except Exception:
        log.exception('stripe customer create failed')
        return None


def create_checkout_session(user, plan_slug: str, *, success_url: str, cancel_url: str) -> str | None:
    role = user.role or 'collectionneur'
    plan_slug = normalize_plan(role, plan_slug)
    plan = plan_for_role(role, plan_slug)
    if not plan:
        return None

    if not is_paid_plan(role, plan_slug):
        _sync_user_subscription(user, plan_slug='free', status='active',
                                subscription_id=None, period_end=None)
        return None

    if not _stripe_ready():
        return None

    amount_cents = int(plan['price_cents'])
    metadata = {
        'kind': 'artworks_subscription',
        'user_id': str(user.id),
        'role': role,
        'plan_slug': plan_slug,
    }
    price_data = {
        'currency': 'eur',
        'product_data': {'name': stripe_product_name(role, plan)},
        'unit_amount': amount_cents,
        'recurring': {'interval': plan.get('interval') or 'month'},
    }
    params = {
        'mode': 'subscription',
        'line_items': [{'price_data': price_data, 'quantity': 1}],
        'success_url': success_url + '?session_id={CHECKOUT_SESSION_ID}',
        'cancel_url': cancel_url,
        'metadata': metadata,
        'subscription_data': {'metadata': metadata},
        'allow_promotion_codes': True,
    }
    customer_id = get_or_create_customer(user)
    if customer_id:
        params['customer'] = customer_id
    else:
        params['customer_email'] = user.email

    try:
        session = stripe.checkout.Session.create(**params)
        return session.url
    except Exception:
        log.exception('stripe checkout create failed')
        return None


def create_portal_session(user, *, return_url: str) -> str | None:
    if not _stripe_ready() or not user.stripe_customer_id:
        return None
    try:
        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=return_url,
        )
        return session.url
    except Exception:
        log.exception('stripe portal create failed')
        return None


def cancel_stripe_subscription(user, *, at_period_end: bool = True) -> bool:
    if not _stripe_ready() or not user.stripe_subscription_id:
        return False
    try:
        if at_period_end:
            stripe.Subscription.modify(user.stripe_subscription_id, cancel_at_period_end=True)
            user.subscription_status = 'cancelled'
        else:
            stripe.Subscription.delete(user.stripe_subscription_id)
            _sync_user_subscription(user, plan_slug='free', status='active',
                                    subscription_id=None, period_end=None)
        db.session.commit()
        from .crm.transactional_hooks import notify_subscription_email
        from .crm.auto_segments import classify_user
        classify_user(user)
        notify_subscription_email(user, 'cancelled')
        return True
    except Exception:
        log.exception('stripe subscription cancel failed')
        return False


def retrieve_session(session_id: str):
    if not _stripe_ready():
        return None
    try:
        return stripe.checkout.Session.retrieve(
            session_id,
            expand=['subscription', 'customer'],
        )
    except Exception:
        log.exception('stripe session retrieve failed')
        return None


def fulfill_checkout_session(session_id: str) -> bool:
    from .models import User

    session_id = (session_id or '').strip()
    if not session_id:
        return False

    sess = retrieve_session(session_id)
    if not sess:
        return False
    if (sess.get('status') or '').lower() != 'complete':
        return False
    pay_status = (sess.get('payment_status') or '').lower()
    if pay_status and pay_status not in ('paid', 'no_payment_required'):
        return False

    meta = dict(sess.get('metadata') or {})
    if meta.get('kind') != 'artworks_subscription':
        return False

    try:
        user_id = int(meta.get('user_id') or 0)
    except (TypeError, ValueError):
        return False
    user = User.query.get(user_id)
    if not user:
        return False

    role = meta.get('role') or user.role
    plan_slug = normalize_plan(role, meta.get('plan_slug') or 'free')
    sub = sess.get('subscription')
    sub_id = sub.id if hasattr(sub, 'id') else (sub or sess.get('subscription'))
    customer = sess.get('customer')
    cust_id = customer.id if hasattr(customer, 'id') else customer
    period_end = None
    if sub and hasattr(sub, 'current_period_end'):
        period_end = _ts_to_dt(sub.current_period_end)

    old_sub = user.stripe_subscription_id
    if old_sub and sub_id and old_sub != sub_id and _stripe_ready():
        try:
            stripe.Subscription.delete(old_sub)
        except Exception:
            log.exception('cancel old subscription %s', old_sub)

    _sync_user_subscription(
        user,
        plan_slug=plan_slug,
        status='active',
        subscription_id=sub_id,
        customer_id=cust_id,
        period_end=period_end,
        since=datetime.utcnow(),
    )
    db.session.commit()
    from .crm.transactional_hooks import notify_subscription_email
    notify_subscription_email(user, 'activated')
    return True


def demo_activate_plan(user, plan_slug: str) -> None:
    """Fallback local sans Stripe (dev uniquement)."""
    role = user.role or 'collectionneur'
    plan_slug = normalize_plan(role, plan_slug)
    if is_paid_plan(role, plan_slug):
        _sync_user_subscription(user, plan_slug=plan_slug, status='active',
                                since=datetime.utcnow())
    else:
        _sync_user_subscription(user, plan_slug='free', status='active',
                                subscription_id=None, period_end=None)


def handle_webhook(payload: bytes, signature: str) -> tuple[bool, str]:
    from .models import User

    secret = current_app.config.get('STRIPE_WEBHOOK_SECRET', '')
    if not _stripe_ready() or not secret:
        return False, 'stripe_not_configured'

    try:
        event = stripe.Webhook.construct_event(payload, signature, secret)
    except Exception as exc:
        log.warning('webhook signature failed: %s', exc)
        return False, 'invalid_signature'

    etype = event.get('type', '')
    data = event.get('data', {}).get('object', {})

    if etype == 'checkout.session.completed':
        meta = dict(data.get('metadata') or {})
        if meta.get('kind') == 'artworks_sale':
            from .marketplace import fulfill_artwork_sale
            fulfill_artwork_sale(data)
        else:
            sid = data.get('id')
            if sid:
                fulfill_checkout_session(sid)

    elif etype in ('customer.subscription.updated', 'customer.subscription.deleted'):
        sub_id = data.get('id')
        meta = dict(data.get('metadata') or {})
        user = None
        if meta.get('user_id'):
            user = User.query.get(int(meta['user_id']))
        if not user and sub_id:
            user = User.query.filter_by(stripe_subscription_id=sub_id).first()

        if not user:
            return True, 'ok'

        role = user.role or 'collectionneur'
        status_raw = (data.get('status') or '').lower()
        plan_slug = normalize_plan(role, meta.get('plan_slug') or user.subscription_plan)
        period_end = _ts_to_dt(data.get('current_period_end'))

        if etype == 'customer.subscription.deleted' or status_raw in ('canceled', 'unpaid', 'incomplete_expired'):
            _sync_user_subscription(user, plan_slug='free', status='expired',
                                    subscription_id=None, period_end=None)
            db.session.commit()
            from .crm.transactional_hooks import notify_subscription_email
            from .crm.auto_segments import classify_user
            classify_user(user)
            notify_subscription_email(user, 'cancelled')
        elif data.get('cancel_at_period_end'):
            _sync_user_subscription(user, plan_slug=plan_slug, status='cancelled',
                                    subscription_id=sub_id, period_end=period_end)
            db.session.commit()
            from .crm.transactional_hooks import notify_subscription_email
            from .crm.auto_segments import classify_user
            classify_user(user)
            notify_subscription_email(user, 'cancelled')
        elif status_raw == 'active':
            _sync_user_subscription(user, plan_slug=plan_slug, status='active',
                                    subscription_id=sub_id, period_end=period_end)
            db.session.commit()
            from .crm.auto_segments import classify_user
            classify_user(user)
        else:
            _sync_user_subscription(user, plan_slug=plan_slug, status=status_raw or 'active',
                                    subscription_id=sub_id, period_end=period_end)
            db.session.commit()
            from .crm.auto_segments import classify_user
            classify_user(user)

    elif etype == 'invoice.payment_failed':
        sub_id = data.get('subscription')
        if sub_id:
            user = User.query.filter_by(stripe_subscription_id=sub_id).first()
            if user:
                user.subscription_status = 'past_due'
                db.session.commit()
                from .crm.transactional_hooks import notify_subscription_email
                from .crm.auto_segments import classify_user
                classify_user(user)
                notify_subscription_email(user, 'past_due')

    return True, 'ok'

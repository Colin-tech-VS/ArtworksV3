from __future__ import annotations

import re
import secrets

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from .forms import RegistrationForm, LoginForm
from .models import User
from . import db
from flask_login import login_user, logout_user, current_user

bp = Blueprint('auth', __name__)

_ROLE_LABELS = {
    'collectionneur': 'Collectionneur',
    'galerie': 'Galerie',
    'artiste': 'Artiste',
}


def _find_user(identifier):
    ident = (identifier or '').strip()
    if not ident:
        return None
    return User.query.filter(
        or_(User.username == ident, User.email == ident.lower())
    ).first()


def _find_by_google_sub(sub: str):
    if not sub:
        return None
    return User.query.filter_by(google_sub=sub).first()


def _find_by_email(email: str):
    email = (email or '').strip().lower()
    if not email:
        return None
    return User.query.filter_by(email=email).first()


def _username_from_email(email: str) -> str:
    base = re.sub(r'[^\w\-]', '', (email.split('@')[0] or 'membre'))[:40] or 'membre'
    candidate = base
    n = 1
    while User.query.filter_by(username=candidate).first():
        candidate = f'{base}{n}'
        n += 1
    return candidate


def _plans_register_context():
    from .subscriptions import plans_for_role, price_label, normalize_plan
    roles = ('collectionneur', 'galerie', 'artiste')
    by_role = {}
    for role in roles:
        by_role[role] = []
        for p in plans_for_role(role):
            by_role[role].append({
                'slug': p['slug'],
                'name': p['name'],
                'tagline': p.get('tagline', ''),
                'price': price_label(p),
                'price_cents': int(p.get('price_cents') or 0),
                'highlight': bool(p.get('highlight')),
                'badge': p.get('badge'),
                'cta': p.get('cta', 'Choisir'),
            })
    return by_role, normalize_plan


def _welcome_user(user: User) -> None:
    # Les effets de bord CRM (segmentation, email de bienvenue) ne doivent jamais
    # faire échouer une création de compte déjà validée — sinon le compte existe
    # mais l'utilisateur voit une erreur 500.
    try:
        from .crm.auto_segments import classify_user
        classify_user(user)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('classify_user failed during registration')
    welcome_slug = {
        'artiste': 'welcome_artiste',
        'galerie': 'welcome_galerie',
        'collectionneur': 'welcome_collectionneur',
    }.get(user.role, 'welcome_collectionneur')
    try:
        from .crm.email_service import send_transactional
        from .crm.email_templates_seed import ensure_default_email_templates
        ensure_default_email_templates()
        send_transactional(welcome_slug, user)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('welcome email failed during registration')


def _apply_free_plan(user: User, role: str, plan_slug: str) -> str:
    """Retourne le slug payant en attente de checkout, ou None."""
    from .subscriptions import normalize_plan, is_paid_plan
    slug = normalize_plan(role, plan_slug)
    if is_paid_plan(role, slug):
        user.subscription_plan = 'free'
        user.subscription_status = 'active'
        return slug
    user.subscription_plan = slug
    user.subscription_status = 'active'
    return None


def _redirect_after_login(user: User, *, next_page: str | None = None):
    if user.role == 'admin' or getattr(user, 'is_staff', False):
        flash(f'Bienvenue, {user.name} (Administrateur).', 'success')
        return redirect(url_for('crm.index'))
    label = _ROLE_LABELS.get(user.role, user.role)
    flash(f'Bienvenue, {user.name} ({label}).', 'success')
    if next_page:
        return redirect(next_page)
    if user.role == 'artiste':
        from .entitlements import has_public_portfolio, portfolio_subscription_active
        if not has_public_portfolio(user):
            if portfolio_subscription_active(user):
                flash(
                    'Connectez Stripe pour encaisser vos ventes et activer votre portfolio public.',
                    'info',
                )
                return redirect(url_for('main.encaissements'))
            flash(
                'Activez Portfolio Marketplace pour publier vos œuvres et apparaître sur Google.',
                'info',
            )
            return redirect(url_for('main.subscription'))
    elif user.role == 'galerie':
        from .entitlements import has_public_portfolio
        from .stripe_connect import connect_required_for
        if connect_required_for(user) and not has_public_portfolio(user):
            flash(
                'Connectez Stripe pour encaisser vos ventes et activer votre page galerie publique.',
                'info',
            )
            return redirect(url_for('main.encaissements'))
    return redirect(url_for('main.dashboard'))


def _start_paid_checkout(user: User, plan_slug: str):
    from . import billing
    from .stripe_connect import connect_required_for
    success = url_for('main.subscription_success', _external=True)
    cancel = url_for('main.subscription', _external=True)
    url = billing.create_checkout_session(user, plan_slug, success_url=success, cancel_url=cancel)
    if url:
        return redirect(url)
    if current_app.config.get('STRIPE_DEMO_MODE') or not current_app.config.get('STRIPE_ENABLED'):
        billing.demo_activate_plan(user, plan_slug)
        msg = 'Compte créé — abonnement activé (mode démo).'
        if connect_required_for(user):
            msg += ' Connectez Stripe pour encaisser et publier.'
            flash(msg, 'success')
            return redirect(url_for('main.encaissements'))
        flash(msg, 'success')
        return redirect(url_for('main.dashboard'))
    flash(
        'Compte créé. Configurez Stripe pour finaliser le paiement de votre formule.',
        'warning',
    )
    return redirect(url_for('main.subscription'))


def _finish_registration(user: User, *, pending_paid_plan: str | None):
    login_user(user)
    _welcome_user(user)
    if pending_paid_plan:
        flash('Compte créé — finalisez le paiement pour activer votre formule.', 'info')
        return _start_paid_checkout(user, pending_paid_plan)
    label = _ROLE_LABELS.get(user.role, user.role)
    if user.role == 'artiste':
        from .pricing_store import pricing_context
        pr = pricing_context()
        flash(
            f'Compte {label} créé — activez Portfolio Marketplace '
            f'({pr["portfolio_price_label"]}/mois) depuis votre espace pour publier.',
            'success',
        )
    else:
        flash(f'Compte {label} créé — bienvenue sur Artworks.', 'success')
    return _redirect_after_login(user)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    plans_by_role, normalize_plan = _plans_register_context()
    if form.validate_on_submit():
        username = form.username.data.strip()
        role = form.role.data
        plan_slug = normalize_plan(role, form.plan.data)
        u = User(
            username=username,
            email=form.email.data.strip().lower(),
            role=role,
            display_name=username,
        )
        u.set_password(form.password.data)
        pending = _apply_free_plan(u, role, plan_slug)
        db.session.add(u)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Ce compte existe déjà (nom d\'utilisateur ou email).', 'error')
            return render_template(
                'register.html', form=form, plans_by_role=plans_by_role,
            )
        return _finish_registration(u, pending_paid_plan=pending)
    if request.method == 'POST' and form.errors:
        flash('Veuillez corriger les erreurs du formulaire.', 'warning')
    role_prefill = request.args.get('role', '')
    plan_prefill = request.args.get('plan', '')
    if role_prefill in _ROLE_LABELS and request.method == 'GET':
        form.role.data = role_prefill
    if plan_prefill and request.method == 'GET':
        form.plan.data = normalize_plan(role_prefill or form.role.data, plan_prefill)
    return render_template('register.html', form=form, plans_by_role=plans_by_role)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = _find_user(form.username.data)
        if user is None:
            flash('Identifiant ou mot de passe invalide.', 'error')
            return redirect(url_for('auth.login'))
        if not user.check_password(form.password.data):
            if user.google_sub:
                flash('Ce compte est lié à Google — utilisez « Continuer avec Google ».', 'info')
            else:
                flash('Identifiant ou mot de passe invalide.', 'error')
            return redirect(url_for('auth.login'))
        login_user(user)
        return _redirect_after_login(user, next_page=request.args.get('next'))
    if request.method == 'POST':
        if form.errors.get('csrf_token'):
            flash('Session expirée — rechargez la page et réessayez.', 'error')
        elif form.errors:
            flash('Vérifiez votre identifiant et votre mot de passe.', 'error')
    return render_template('login.html', form=form)


@bp.route('/auth/google')
def google_start():
    from .google_oauth import (
        authorization_url, google_oauth_configured, state_make,
    )
    from .subscriptions import normalize_plan, role_plans_catalog

    if not google_oauth_configured():
        flash('Connexion Google non configurée.', 'warning')
        return redirect(request.referrer or url_for('auth.login'))

    action = request.args.get('action', 'login')
    if action not in ('login', 'register'):
        action = 'login'

    role = (request.args.get('role') or '').strip()
    plan = (request.args.get('plan') or 'free').strip()
    if action == 'register':
        if role not in _ROLE_LABELS:
            flash('Choisissez d\'abord votre profil (collectionneur, galerie ou artiste).', 'warning')
            return redirect(url_for('auth.register'))
        plan = normalize_plan(role, plan)
        if plan not in role_plans_catalog().get(role, {}):
            plan = 'free'

    state = state_make(
        action=action,
        role=role or None,
        plan=plan,
        next_url=request.args.get('next', ''),
    )
    return redirect(authorization_url(state=state))


@bp.route('/auth/google/callback')
def google_callback():
    from .google_oauth import (
        exchange_code, fetch_userinfo, google_oauth_configured, state_verify,
    )
    from .subscriptions import normalize_plan, role_plans_catalog, is_paid_plan

    if not google_oauth_configured():
        flash('Connexion Google non configurée.', 'warning')
        return redirect(url_for('auth.login'))

    if request.args.get('error'):
        flash('Connexion Google annulée.', 'info')
        return redirect(url_for('auth.login'))

    state_payload = state_verify(request.args.get('state'))
    if not state_payload:
        flash('Session Google expirée — réessayez.', 'error')
        return redirect(url_for('auth.login'))

    code = request.args.get('code', '')
    token_data = exchange_code(code)
    if not token_data or not token_data.get('access_token'):
        flash('Impossible de valider la connexion Google.', 'error')
        return redirect(url_for('auth.login'))

    profile = fetch_userinfo(token_data['access_token'])
    if not profile or not profile.get('sub'):
        flash('Profil Google inaccessible.', 'error')
        return redirect(url_for('auth.login'))

    google_sub = str(profile['sub'])
    email = (profile.get('email') or '').strip().lower()
    if not email:
        flash('Votre compte Google doit partager une adresse email.', 'error')
        return redirect(url_for('auth.login'))

    action = state_payload.get('a', 'login')
    next_page = state_payload.get('n') or None

    user = _find_by_google_sub(google_sub) or _find_by_email(email)
    if user:
        if not user.google_sub:
            user.google_sub = google_sub
            if profile.get('name') and not user.display_name:
                user.display_name = profile['name'][:120]
            db.session.commit()
        login_user(user)
        return _redirect_after_login(user, next_page=next_page)

    if action == 'login':
        flash('Aucun compte Artworks pour cet email — créez-en un d\'abord.', 'info')
        return redirect(url_for('auth.register'))

    role = state_payload.get('r') or 'collectionneur'
    if role not in _ROLE_LABELS:
        role = 'collectionneur'
    plan = normalize_plan(role, state_payload.get('p') or 'free')
    if plan not in role_plans_catalog().get(role, {}):
        plan = 'free'

    display = (profile.get('name') or email.split('@')[0])[:120]
    username = _username_from_email(email)
    u = User(
        username=username,
        email=email,
        role=role,
        display_name=display,
        google_sub=google_sub,
    )
    u.set_password(secrets.token_urlsafe(32))
    pending = _apply_free_plan(u, role, plan)
    db.session.add(u)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = _find_by_email(email)
        if existing:
            login_user(existing)
            return _redirect_after_login(existing, next_page=next_page)
        flash('Impossible de créer le compte — réessayez.', 'error')
        return redirect(url_for('auth.register'))

    return _finish_registration(u, pending_paid_plan=pending)


@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))

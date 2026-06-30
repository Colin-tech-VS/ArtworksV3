"""Redirections post-connexion selon le rôle (admin CRM vs dashboard membre)."""
from __future__ import annotations

from flask import redirect, url_for, flash

from .crm.auth import is_staff_user

ROLE_LABELS = {
    'collectionneur': 'Collectionneur',
    'galerie': 'Galerie',
    'artiste': 'Artiste',
    'admin': 'Administrateur',
}


def safe_next_url(next_page: str | None) -> str | None:
    """Autorise uniquement les chemins relatifs internes."""
    url = (next_page or '').strip()
    if not url.startswith('/') or url.startswith('//'):
        return None
    return url


def home_url_for(user) -> str:
    if is_staff_user(user):
        return url_for('crm.index')
    return url_for('main.dashboard')


def redirect_after_login(user, *, next_page: str | None = None):
    """Redirige après connexion avec message de bienvenue adapté au rôle."""
    if is_staff_user(user):
        flash(f'Bienvenue, {user.name} (Administrateur).', 'success')
        return redirect(url_for('crm.index'))

    label = ROLE_LABELS.get(user.role or '', user.role or 'Membre')
    flash(f'Bienvenue, {user.name} ({label}).', 'success')

    safe = safe_next_url(next_page)
    if safe:
        return redirect(safe)

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


def redirect_if_authenticated(user):
    """Utilisateur déjà connecté : envoi vers CRM ou dashboard."""
    return redirect(home_url_for(user))

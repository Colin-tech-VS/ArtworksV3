"""Aria — assistante conversationnelle vitrine Artworks (Mistral en backend, jamais cité)."""
from __future__ import annotations

import time
from typing import Any

from flask import current_app, session

from .ai import CuratorialAIError, chat_completions_api
from .aria_tools import _MAX_AGENT_STEPS, run_tool_calls, tools_for_user
from .offer_pages import OFFER_CONFIG
from .subscriptions import ROLE_LABELS, plans_for_role, price_label

ARIA_NAME = 'Aria'
_MAX_HISTORY = 16
_MAX_MESSAGE_LEN = 2000
_RATE_LIMIT = 40
_RATE_WINDOW = 3600


def aria_enabled() -> bool:
    return bool(current_app.config.get('MISTRAL_API_KEY'))


_ARIA_VITRINE_ENDPOINTS = frozenset({
    'main.index', 'main.explorer', 'main.tarifs',
    'main.offre_artiste', 'main.offre_galerie', 'main.offre_collectionneur',
    'main.cms_page', 'main.artist', 'main.artwork_detail', 'main.public_wishlist',
})


def aria_show_on_vitrine(endpoint: str | None, blueprint: str | None = None) -> bool:
    if blueprint == 'crm':
        return False
    if blueprint == 'auth' and endpoint == 'auth.logout':
        return False
    if blueprint in ('main', 'auth'):
        return True
    if endpoint in _ARIA_VITRINE_ENDPOINTS:
        return True
    return False


def _site_base() -> str:
    return (current_app.config.get('SITE_URL') or '').rstrip('/') or 'https://artworksdigital.fr'


def _build_plans_text() -> str:
    from .pricing_store import commission_percent_label

    comm = commission_percent_label()
    lines = [f'Commission marketplace : {comm} sur les ventes conclues via la plateforme (Stripe).']
    for role in ('artiste', 'galerie', 'collectionneur'):
        label = ROLE_LABELS.get(role, role)
        lines.append(f'\n## Formules {label}')
        for plan in plans_for_role(role):
            price = price_label(plan)
            interval = plan.get('interval')
            price_str = f'{price}/mois' if interval == 'month' else ('Gratuit' if not plan.get('price_cents') else price)
            feats = '; '.join((plan.get('features') or [])[:6])
            lines.append(f"- **{plan['name']}** ({price_str}) — {plan.get('tagline', '')}")
            if feats:
                lines.append(f'  Fonctionnalités : {feats}')
    return '\n'.join(lines)


def _build_faq_text() -> str:
    chunks = []
    for role, cfg in OFFER_CONFIG.items():
        faq = cfg.get('faq') or []
        if not faq:
            continue
        chunks.append(f'### FAQ {ROLE_LABELS.get(role, role)}')
        for q, a in faq:
            chunks.append(f'Q: {q}\nR: {a}')
    return '\n\n'.join(chunks)


def build_knowledge_context() -> str:
    """Base de connaissances injectée dans le prompt système."""
    base = _site_base()
    from .models import Artwork, User

    try:
        n_artworks = Artwork.query.count()
        n_artists = User.query.filter(User.role == 'artiste').count()
        n_galleries = User.query.filter(User.role == 'galerie').count()
    except Exception:
        n_artworks = n_artists = n_galleries = 0

    pages = f"""
PAGES PRINCIPALES (URLs relatives à {base}) :
- / — Accueil, sélection curatoriale, artistes mis en avant
- /explorer — Catalogue d'œuvres (filtres discipline, prix, recherche)
- /tarifs — Comparatif des formules par profil (artiste, galerie, collectionneur)
- /offre — Offre artiste (portfolio, SEO, marketplace)
- /offre-galerie — Offre galerie (multi-artistes, CRM collectionneurs)
- /offre-collectionneur — Club collectionneur (alertes, avant-première)
- /register — Inscription (choix du profil et de la formule)
- /login — Connexion (email ou Google)
- /dashboard — Tableau de bord membre (après connexion)
- /profile/subscription — Gestion abonnement Stripe
- /profile/encaissements — Stripe Connect pour recevoir les ventes

STATISTIQUES LIVE (indicatif) : {n_artworks} œuvres catalogue, {n_artists} comptes artistes, {n_galleries} galeries.

{_build_plans_text()}

{_build_faq_text()}

FONCTIONNALITÉS CLÉS ARTWORKS :
- **Artworks Salon** (vitrine) / écosystème **Artworks Digital** : plateforme française art contemporain
- Galeries, artistes et collectionneurs sur un même marketplace curaté
- Paiements sécurisés **Stripe** ; vendeurs : **Stripe Connect**
- Portfolio public **SEO** (Google), note curatoriale **IA** pour artistes (dans l'espace membre)
- Explorateur, favoris, wishlist partageable (collectionneurs Membre/Patron)
- Alertes prix, accès avant-première 48 h (formules collectionneur payantes)
- CRM intégré galeries : emails, segments, réseaux sociaux (Facebook, Instagram, Pinterest, DeviantArt)
- Inscription Google OAuth disponible
- Contact plateforme : contact@artworksdigital.fr
"""
    return pages.strip()


def _user_context_block() -> str:
    from flask_login import current_user
    if not current_user.is_authenticated:
        return 'VISITEUR NON CONNECTÉ — tu peux répondre aux questions et créer un compte via create_account. Pour modifier un profil/œuvre : demander connexion ou inscription.'
    role = current_user.role or 'collectionneur'
    return (
        f'UTILISATEUR CONNECTÉ : id={current_user.id}, username={current_user.username}, '
        f'role={role}, email={current_user.email}. '
        f'Tu DOIS utiliser tes outils pour TOUTE action sur son compte (profil, œuvres, images, abonnement). '
        f'Ne dis jamais « allez dans le menu » — exécute l\'outil toi-même. '
        f'Images jointes via 📎 : utilise list_pending_uploads puis set_artwork_image ou set_profile_image.'
    )


def _system_prompt() -> str:
    base = _site_base()
    knowledge = build_knowledge_context()
    user_ctx = _user_context_block()
    return f"""Tu es **Aria**, l'assistante officielle d'**Artworks** (Artworks Salon + Artworks Digital).

IDENTITÉ :
- Tu es **Aria** uniquement. JAMAIS mentionner Mistral, GPT, LLM ou fournisseur IA.

OUTILS — RÈGLE D'OR :
- Tu disposes d'**outils** pour agir sur le site : créer un compte, modifier profil/œuvres/séries, images, abonnement, alertes prix, artistes galerie, recherche catalogue.
- Quand l'utilisateur demande une **action** → **APPELLE L'OUTIL** immédiatement avec les infos du message (déduis les champs, ne pose pas 5 questions).
- Quand il pose une **question** → réponds d'abord ; propose l'action liée ensuite.
- Après un outil réussi, confirme en français ce qui a été fait + lien [tableau de bord](/dashboard) si pertinent.
- Hors Artworks : refuse poliment.

{user_ctx}

STYLE (markdown rendu visuellement) :
- **gras**, *italique*, ### titres, listes -, liens [texte](/chemin)

BASE DE CONNAISSANCES :
{knowledge}
"""


def _rate_ok() -> bool:
    now = time.time()
    bucket = session.get('aria_rate') or {'t': now, 'n': 0}
    if now - bucket.get('t', 0) > _RATE_WINDOW:
        bucket = {'t': now, 'n': 0}
    if bucket['n'] >= _RATE_LIMIT:
        return False
    bucket['n'] += 1
    session['aria_rate'] = bucket
    return True


def _history() -> list[dict[str, str]]:
    h = session.get('aria_history')
    if not isinstance(h, list):
        h = []
    return h[-_MAX_HISTORY:]


def _save_history(messages: list[dict[str, str]]) -> None:
    session['aria_history'] = messages[-_MAX_HISTORY:]
    session.modified = True


def clear_history() -> None:
    session.pop('aria_history', None)
    session.modified = True


def chat(user_message: str, *, reset: bool = False) -> dict[str, Any]:
    """Agent Aria avec function calling."""
    from flask_login import current_user

    text = (user_message or '').strip()[:_MAX_MESSAGE_LEN]
    if not text:
        return {'error': 'Message vide.'}
    if not aria_enabled():
        return {'error': 'Aria n\'est pas disponible pour le moment. Réessayez plus tard.'}
    if not _rate_ok():
        return {'error': 'Limite de messages atteinte — revenez dans une heure ou contactez-nous.'}

    if reset:
        clear_history()

    history = _history()
    ctx: dict[str, Any] = {
        'user': current_user,
        'side_effects': [],
    }
    tools = tools_for_user(current_user)
    model = current_app.config.get('MISTRAL_MODEL') or 'mistral-small-latest'

    messages: list[dict] = [{'role': 'system', 'content': _system_prompt()}]
    for m in history:
        if m.get('role') in ('user', 'assistant') and m.get('content'):
            messages.append({'role': m['role'], 'content': m['content']})
    messages.append({'role': 'user', 'content': text})

    reply = ''
    try:
        for _ in range(_MAX_AGENT_STEPS):
            data = chat_completions_api(
                messages,
                tools=tools,
                temperature=0.35,
                max_tokens=1200,
                model=model,
                timeout=90,
            )
            msg = data['choices'][0]['message']
            tool_calls = msg.get('tool_calls')
            if tool_calls:
                messages.append({
                    'role': 'assistant',
                    'content': msg.get('content') or '',
                    'tool_calls': tool_calls,
                })
                messages.extend(run_tool_calls(tool_calls, ctx))
                continue
            reply = (msg.get('content') or '').strip()
            break
    except CuratorialAIError:
        return {'error': 'Aria rencontre une difficulté technique. Réessayez dans un instant.'}
    except Exception:
        return {'error': 'Aria n\'est pas disponible pour le moment.'}

    if not reply:
        reply = 'Voilà ce que j\'ai fait pour vous. Souhaitez-vous autre chose sur Artworks ?'

    history.append({'role': 'user', 'content': text})
    history.append({'role': 'assistant', 'content': reply})
    _save_history(history)

    out: dict[str, Any] = {'reply': reply, 'name': ARIA_NAME}
    effects = ctx.get('side_effects') or []
    if effects:
        out['actions'] = effects
    return out

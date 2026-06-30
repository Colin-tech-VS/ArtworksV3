"""Aria — assistante conversationnelle vitrine Artworks (Mistral en backend, jamais cité)."""
from __future__ import annotations

import logging
import re
import secrets
import time
from typing import Any

from flask import current_app, session

from .ai import CuratorialAIError, chat_completions_api
from .aria_tools import _MAX_AGENT_STEPS, run_tool_calls, tools_for_user
from .offer_pages import OFFER_CONFIG
from .subscriptions import ROLE_LABELS, plans_for_role, price_label

_log = logging.getLogger(__name__)

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

RÔLE COMMERCIAL — TU VENDS LE CATALOGUE :
- Ta mission première : **faire découvrir et vendre** les œuvres, artistes, galeries et collectionneurs d'Artworks.
- Pour parler d'une œuvre, d'un artiste, d'une galerie ou d'un collectionneur : appelle d'abord l'outil de lecture (`search_artworks`, `search_artists`, `get_artwork`, `get_profile`) — **ne devine jamais** prix, disponibilité ou stock.
- **Montre toujours l'image** de l'œuvre quand le champ `image` est fourni : écris-la en markdown `![titre](image)` juste avant le lien.
- Présente toujours : le **prix** (`price_label`), la **disponibilité**, et un **lien cliquable** vers l'œuvre `[titre](/artwork/ID)` ou le profil `[nom](/artist/ID)`.
- Pour **vendre** : si `buyable_online` est vrai → mets un appel à l'action clair **[Acheter — prix](buy_url)** (paiement Stripe sécurisé sur la page œuvre). Sinon → propose **[Voir l'œuvre](url)** puis de **contacter l'artiste/la galerie** (champ `contact`) ou de demander le prix.
- Quand tu présentes plusieurs œuvres, fais une liste : pour chacune, image + titre lié + prix.
- Mets en valeur la provenance, l'authenticité et la sélection curatoriale pour rassurer l'acheteur, sans inventer de détails absents des données.

OUTILS — RÈGLE D'OR :
- Tu disposes d'**outils** pour lire le catalogue (œuvres, profils) et pour agir sur le site : créer un compte (`create_account` role=galerie), **connecter** (`login_account`), changer de rôle (`change_my_role`), profil/œuvres/images, abonnement, etc.
- **Dès que l'utilisateur donne email + mot de passe** → appelle `create_account` **immédiatement** (l'outil connecte aussi les comptes existants avec le bon mot de passe).
- Le **nom de galerie** = `display_name` (espaces autorisés, ex. « Artworks Salon »). **Username** : 3–64 caractères, généré auto — **ne jamais** inventer de limite à 12 ou 20 caractères.
- **Ne jamais** refuser un nom pour longueur sans avoir appelé l'outil.
- Quand il demande une **action** → **APPELLE L'OUTIL** immédiatement.
- Après succès, confirme en français + lien [tableau de bord](/dashboard).
- Hors Artworks : refuse poliment.

{user_ctx}

STYLE (markdown rendu visuellement) :
- **gras**, *italique*, ### titres, listes -, liens [texte](/chemin)
- **images** : `![texte](url_image)` — affichées en vignette dans le chat (utilise le champ `image` des œuvres).

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


def _normalize_tool_calls(tool_calls: list) -> list[dict]:
    """Réécrit les tool_calls Mistral avec un id valide (a-zA-Z0-9, longueur 9).

    Mistral rejette tout `tool_call_id` non conforme : on régénère un id propre
    quand celui renvoyé est absent ou invalide, et on s'assure que l'id du message
    `assistant` correspond exactement à celui du message `tool` (même objet réutilisé
    par run_tool_calls)."""
    norm = []
    for tc in tool_calls or []:
        fn = tc.get('function') or {}
        tid = tc.get('id')
        if not (isinstance(tid, str) and re.fullmatch(r'[a-zA-Z0-9]{9}', tid)):
            tid = secrets.token_hex(5)[:9]
        norm.append({
            'id': tid,
            'type': 'function',
            'function': {
                'name': fn.get('name') or '',
                'arguments': fn.get('arguments') or '{}',
            },
        })
    return norm


def clear_history() -> None:
    session.pop('aria_history', None)
    session.pop('aria_signup_role', None)
    session.pop('aria_signup_pending', None)
    session.modified = True


def _track_signup_intent(text: str) -> None:
    low = (text or '').lower()
    if any(w in low for w in ('galerie', 'gallery')) and any(
        w in low for w in ('compte', 'créer', 'creer', 'inscri', 'inscription', 'crée', 'cree')
    ):
        session['aria_signup_role'] = 'galerie'
        session.modified = True
    elif 'artiste' in low and any(w in low for w in ('compte', 'créer', 'creer', 'inscri')):
        session['aria_signup_role'] = 'artiste'
        session.modified = True
    elif 'collectionneur' in low and any(w in low for w in ('compte', 'créer', 'creer', 'inscri')):
        session['aria_signup_role'] = 'collectionneur'
        session.modified = True


def _try_signup_fast_path(text: str, ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Inscription sans LLM quand email + mot de passe sont dans le message."""
    from flask_login import current_user
    from .aria_tools import execute_tool, format_signup_reply, parse_signup_credentials

    if current_user.is_authenticated:
        return None

    low = text.lower()
    pending = session.get('aria_signup_pending')
    if (
        isinstance(pending, dict)
        and pending.get('email')
        and pending.get('password')
        and len(text) < 80
        and '@' not in text
        and 'mdp' not in low
        and 'mail' not in low
        and 'email' not in low
    ):
        args = dict(pending)
        args['display_name'] = text.strip()
        role = args.get('role') or session.get('aria_signup_role') or 'galerie'
        args['role'] = role
        result = execute_tool('create_account', args, ctx)
        if result.get('ok'):
            session.pop('aria_signup_pending', None)
            session.pop('aria_signup_role', None)
        return {
            'reply': format_signup_reply(result, role=role),
            'name': ARIA_NAME,
            'actions': ctx.get('side_effects') or None,
        }

    parsed = parse_signup_credentials(text)
    if not parsed:
        return None

    role = parsed.get('role') or session.get('aria_signup_role') or 'galerie'
    parsed['role'] = role
    session['aria_signup_pending'] = dict(parsed)
    session.modified = True

    result = execute_tool('create_account', parsed, ctx)
    if result.get('ok'):
        session.pop('aria_signup_pending', None)
        session.pop('aria_signup_role', None)
    return {
        'reply': format_signup_reply(result, role=role),
        'name': ARIA_NAME,
        'actions': ctx.get('side_effects') or None,
    }


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

    _track_signup_intent(text)
    fast = _try_signup_fast_path(text, ctx)
    if fast:
        history.append({'role': 'user', 'content': text})
        history.append({'role': 'assistant', 'content': fast['reply']})
        _save_history(history)
        out = dict(fast)
        if not out.get('actions'):
            out.pop('actions', None)
        return out

    tools = tools_for_user(current_user)
    # Boucle conversationnelle temps réel : on privilégie le modèle rapide.
    # Un appel d'outil enchaîne plusieurs requêtes séquentielles — le modèle lourd
    # (mistral-large) les rend trop lentes et fait « bloquer » Aria / expirer le worker.
    model = (
        current_app.config.get('MISTRAL_MODEL')
        or current_app.config.get('MISTRAL_MODEL_HEAVY')
        or 'mistral-small-latest'
    )

    messages: list[dict] = [{'role': 'system', 'content': _system_prompt()}]
    for m in history:
        if m.get('role') in ('user', 'assistant') and m.get('content'):
            messages.append({'role': m['role'], 'content': m['content']})
    messages.append({'role': 'user', 'content': text})

    reply = ''
    try:
        for step in range(_MAX_AGENT_STEPS):
            data = chat_completions_api(
                messages,
                tools=tools,
                temperature=0.35,
                max_tokens=1200,
                model=model,
                timeout=45,
            )
            choices = data.get('choices') or []
            if not choices:
                raise CuratorialAIError('Réponse vide du service.')
            msg = choices[0].get('message') or {}
            tool_calls = msg.get('tool_calls')
            if tool_calls:
                tool_calls = _normalize_tool_calls(tool_calls)
                messages.append({
                    'role': 'assistant',
                    'content': msg.get('content') or '',
                    'tool_calls': tool_calls,
                })
                messages.extend(run_tool_calls(tool_calls, ctx))
                continue
            reply = (msg.get('content') or '').strip()
            break
    except CuratorialAIError as exc:
        _log.warning('Aria CuratorialAIError: %s', exc)
        msg = str(exc)
        if 'Quota' in msg or '429' in msg:
            return {'error': 'Aria est momentanément saturée — réessayez dans 1 minute ou utilisez [l\'inscription](/register).'}
        return {'error': 'Aria rencontre une difficulté technique. Réessayez dans un instant.'}
    except Exception as exc:
        _log.exception('Aria chat failed: %s', exc)
        return {'error': 'Aria rencontre une difficulté inattendue. Réessayez ou utilisez [l\'inscription classique](/register).'}

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

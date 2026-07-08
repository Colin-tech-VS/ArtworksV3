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
- **Artworks Digital** : marketplace française d'art contemporain (artistes, galeries, collectionneurs)
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
    return f"""Tu es **Aria**, l'assistante officielle d'**Artworks Digital**.

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
- Tu disposes d'**outils** pour lire le catalogue (œuvres, profils) et pour agir sur le site : créer un compte (`create_account`), **connecter** (`login_account`), changer de rôle (`change_my_role`), profil/œuvres/images, abonnement, etc.
- **INSCRIPTION** : la collecte des identifiants est gérée par un flux guidé du site. Tu **ne dois JAMAIS inventer** d'email, de mot de passe ni de nom. Si l'utilisateur veut un compte, demande-lui son **email**, puis son **mot de passe** ; n'appelle `create_account` **que** lorsque l'utilisateur a fourni email ET mot de passe explicitement.
- Le **nom de galerie** = `display_name` (espaces autorisés, ex. « Galerie Moderne »). **Username** : 3–64 caractères, généré auto — **ne jamais** inventer de limite à 12 ou 20 caractères.
- **Ne jamais** refuser un nom pour longueur sans avoir appelé l'outil.
- Quand il demande une **action** (autre que l'inscription) → **APPELLE L'OUTIL** immédiatement.

ÉDITEUR DE PAGE (compte artiste/galerie connecté) :
- Quand on te demande de **structurer / construire / refaire la page** : le site applique automatiquement un brouillon — **ne montre JAMAIS** de JSON, de code `set_page_layout` ni de blocs à copier-coller. Réponds en 2–3 phrases après l'application.
- Si tu dois quand même agir via outil : appelle `get_my_page` puis `set_page_layout` (brouillon). L'utilisateur valide avec **Enregistrer** ou **Annuler**.
- **Refonte** : si `current_blocks` ou `has_draft` est vrai, `set_page_layout` **remplace** toute la page — réutilise le contenu utile des blocs existants, ne recopie pas en plus le profil/bio déjà présents dans les blocs.
- **Design galerie haut de gamme** : sobre, éditorial, typographie élégante (Cormorant). Inspirations : page de galerie d'art contemporain (pas de blog, pas de flyer).
- **INTERDIT** : emojis dans les blocs, JSON de mise en page, instructions « copiez dans l'éditeur », URLs d'images inventées.
- **Structure type** (8–14 blocs, courts) :
  1. `heading` — nom (5–8 mots)
  2. `text` — accroche (2 phrases max)
  3. `divider`
  4. `heading` — section (ex. « Notre sélection »)
  5. `text` — paragraphe court (3–4 lignes max)
  6. `gallery` ou `slider` — images réelles depuis `artwork_images` de `get_my_page` (jamais d'URL inventée)
  7. `divider`
  8. `heading` + `text` — engagement / valeurs (court)
  9. `button` — « Découvrir les œuvres » → `/explorer` ou « Nous contacter » → mailto
- **Un bloc = un rôle** : ne mets jamais toute la page dans un seul bloc `text`.
- Styles : `font: display` pour titres, `serif` pour corps, `color: #1a2832`, accent `#b8734a` sur boutons.
- Après `set_page_layout` : réponds en **2–3 phrases** (pas de recopie du contenu). L'aperçu se met à jour automatiquement à droite.
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


def _merge_histories(client: list | None, server: list) -> list[dict[str, str]]:
    """Historique client (fiable) + session serveur."""
    merged: list[dict[str, str]] = []
    for src in (client or []) + (server or []):
        if not isinstance(src, dict):
            continue
        role = src.get('role')
        content = str(src.get('content') or '').strip()
        if role in ('user', 'assistant') and content:
            merged.append({'role': role, 'content': content[:2000]})
    return merged[-_MAX_HISTORY:]


def _state_from_client_signup(data: dict | None) -> dict | None:
    if not isinstance(data, dict) or not data.get('active'):
        return None
    return {
        'active': True,
        'role': data.get('role') or 'galerie',
        'email': data.get('email'),
        'password': None,
        'display_name': data.get('display_name'),
        'plan': data.get('plan') or 'free',
        'awaiting': data.get('awaiting'),
    }


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
    session.pop('aria_signup', None)
    session.modified = True


# ---------------------------------------------------------------------------
# Inscription guidée (déterministe, sans deviner) : Aria demande le rôle, puis
# l'email, puis le mot de passe, puis le nom — et NE crée le compte qu'une fois
# email + mot de passe explicitement fournis par l'utilisateur.
# ---------------------------------------------------------------------------
_SIGNUP_CANCEL = (
    'annuler', 'annule', 'laisse tomber', 'laisser tomber', "j'arrête", "j'arrete",
    'arrête', 'arrete', 'stop', 'abandonner', 'abandon',
)
_SIGNUP_SKIP = ('passer', 'passe', 'skip', 'non', 'aucun', 'plus tard', 'sans', 'rien', 'no')
_ROLE_WORDS = (
    ('galerie', 'galerie'), ('gallery', 'galerie'),
    ('artiste', 'artiste'), ('artist', 'artiste'),
    ('collectionneur', 'collectionneur'), ('collectionneuse', 'collectionneur'),
    ('collector', 'collectionneur'),
)
_ROLE_LABEL = {'galerie': 'galerie', 'artiste': 'artiste', 'collectionneur': 'collectionneur'}
_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')


def _detect_role(low: str) -> str | None:
    for word, role in _ROLE_WORDS:
        if word in low:
            return role
    return None


def _has_signup_intent(low: str) -> bool:
    if 'inscri' in low:
        return True
    verbs = ('créer', 'creer', 'crée', 'cree', 'créez', 'creez', 'ouvrir', 'rejoindre', 'nouveau compte')
    if any(v in low for v in verbs) and ('compte' in low or _detect_role(low)):
        return True
    return False


def _extract_email(text: str) -> str | None:
    m = re.search(r'(?:mail|email|courriel)\s*[:=]?\s*([\w.+-]+@[\w-]+\.[\w.-]+)', text, re.I)
    if m:
        return m.group(1).strip().rstrip('.,;').lower()
    m = _EMAIL_RE.search(text)
    return m.group(0).strip().rstrip('.,;').lower() if m else None


def _extract_password_labeled(text: str) -> str | None:
    m = re.search(r'(?:mot\s*de\s*passe|mdp|password|pass)\s*(?:est|:|=)?\s*(\S+)', text, re.I)
    if m:
        pw = m.group(1).strip().strip('"\'').rstrip('.,;')
        if len(pw) >= 6:
            return pw
    return None


def _extract_name_labeled(text: str) -> str | None:
    m = re.search(
        r'(?:nom|name|nomm[ée]e?|appel[ée]e?|intitul[ée]e?)\s*[:=]?\s*([^\n|]+?)'
        r'(?:\s*\||\s+mdp|\s+mot\s*de\s*passe|\s+email|\s+mail|$)',
        text, re.I,
    )
    if m:
        nm = m.group(1).strip().strip('"\'')
        if nm and '@' not in nm and not re.fullmatch(r'(?:galerie|artiste|collectionneur)', nm, re.I):
            return nm[:120]
    return None


def _extract_plan(low: str) -> str | None:
    if any(w in low for w in ('gratuit', 'gratuite', 'découverte', 'decouverte', 'free')):
        return 'gratuit'
    m = re.search(r'formule\s*[:=]?\s*(\w+)', low)
    return m.group(1) if m else None


def _last_assistant_text(history: list[dict]) -> str:
    for m in reversed(history):
        if m.get('role') == 'assistant' and m.get('content'):
            return str(m['content'])
    return ''


def _role_from_assistant(text: str) -> str | None:
    low = text.lower()
    role = _detect_role(low)
    if role:
        return role
    if 'compte' in low and 'galerie' in low:
        return 'galerie'
    if 'compte' in low and 'artiste' in low:
        return 'artiste'
    if 'compte' in low and 'collectionneur' in low:
        return 'collectionneur'
    return None


def _last_user_email(history: list[dict]) -> str | None:
    for m in reversed(history):
        if m.get('role') != 'user':
            continue
        em = _extract_email(m.get('content') or '')
        if em:
            return em
    return None


def _capture_password(text: str) -> str | None:
    pw = _extract_password_labeled(text)
    if pw:
        return pw
    cand = text.strip().strip('"\'').rstrip('.,;')
    if ' ' in cand:
        toks = [t for t in re.split(r'\s+', cand) if t]
        cand = toks[-1] if toks else cand
    if 6 <= len(cand) <= 128 and '@' not in cand:
        return cand
    return None


def _recover_signup_from_history(history: list[dict], text: str) -> dict | None:
    """Reconstitue l'inscription si la session a été perdue entre deux messages."""
    if not history:
        return None
    last_a = _last_assistant_text(history)
    if not last_a:
        return None
    low_a = last_a.lower()
    role = _role_from_assistant(last_a)
    for m in history:
        if m.get('role') == 'assistant':
            r = _role_from_assistant(m.get('content') or '')
            if r:
                role = r
                break

    if 'mot de passe' in low_a or 'password' in low_a:
        email = _extract_email(text) or _last_user_email(history)
        if not email:
            return None
        pw = _capture_password(text)
        if not pw:
            return None
        return {
            'active': True,
            'role': role or 'galerie',
            'email': email,
            'password': pw,
            'display_name': '',
            'plan': 'free',
            'awaiting': None,
        }

    if 'adresse email' in low_a or 'adresse e-mail' in low_a or 'votre email' in low_a:
        em = _extract_email(text)
        if not em:
            return None
        return {
            'active': True,
            'role': role or 'galerie',
            'email': em,
            'password': None,
            'display_name': None,
            'plan': 'free',
            'awaiting': 'password',
        }

    if 'nom de votre galerie' in low_a or "nom d'artiste" in low_a or 'nom souhaitez-vous' in low_a:
        if low_a and text.strip().lower() in _SIGNUP_SKIP:
            dn = ''
        else:
            dn = text.strip().strip('"\'')[:120]
        email = _last_user_email(history)
        if not email:
            return None
        return {
            'active': True,
            'role': role or 'galerie',
            'email': email,
            'password': _capture_password(text),
            'display_name': dn,
            'plan': 'free',
            'awaiting': None,
        }
    return None


def _signup_reply(
    message: str,
    ctx: dict[str, Any] | None = None,
    state: dict | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {'reply': message, 'name': ARIA_NAME}
    if ctx and ctx.get('side_effects'):
        out['actions'] = ctx['side_effects']
    if state and state.get('active'):
        logged_in = any(
            isinstance(a, dict) and a.get('type') in ('redirect', 'login')
            for a in (out.get('actions') or [])
        )
        if not logged_in:
            out['signup_state'] = {
                'active': True,
                'role': state.get('role'),
                'email': state.get('email'),
                'awaiting': state.get('awaiting'),
                'plan': state.get('plan') or 'free',
            }
    return out


def _save_signup_state(state: dict) -> None:
    session['aria_signup'] = state
    session.modified = True


def _handle_signup_flow(text: str, ctx: dict[str, Any], history: list[dict] | None = None) -> dict[str, Any] | None:
    """Collecte guidée des informations d'inscription, étape par étape.

    Retourne une réponse Aria si la conversation porte sur une inscription,
    sinon None (le LLM prend le relais). Ne crée jamais le compte tant que
    l'email ET le mot de passe n'ont pas été donnés explicitement."""
    from flask_login import current_user
    from .aria_tools import execute_tool, format_signup_reply, parse_signup_credentials

    if current_user.is_authenticated:
        session.pop('aria_signup', None)
        return None

    history = history or []
    low = text.lower().strip()
    state = session.get('aria_signup')
    if not isinstance(state, dict):
        state = None

    client_signup = ctx.get('client_signup')
    if (not state or not state.get('active')) and client_signup:
        restored = _state_from_client_signup(client_signup)
        if restored:
            state = restored

    # Inscription en une ligne (email + mdp + rôle dans le même message)
    one_shot = parse_signup_credentials(text)
    if one_shot and one_shot.get('email') and one_shot.get('password'):
        role = one_shot.get('role') or _detect_role(low) or 'galerie'
        result = execute_tool('create_account', {
            'email': one_shot['email'],
            'password': one_shot['password'],
            'role': role,
            'plan': one_shot.get('plan') or 'free',
            'display_name': one_shot.get('display_name') or '',
        }, ctx)
        if result.get('ok'):
            session.pop('aria_signup', None)
            session.modified = True
        return _signup_reply(format_signup_reply(result, role=role), ctx)

    # Annulation explicite
    if state and state.get('active') and any(w in low for w in _SIGNUP_CANCEL):
        session.pop('aria_signup', None)
        session.modified = True
        return _signup_reply(
            "Pas de souci, j'annule la création de compte. Je reste disponible si vous "
            "avez des questions sur Artworks ou souhaitez réessayer plus tard."
        )

    role = _detect_role(low)
    if not state or not state.get('active'):
        recovered = _recover_signup_from_history(history, text)
        if recovered:
            state = recovered
        elif not _has_signup_intent(low):
            return None
        else:
            state = {
                'active': True, 'role': role, 'email': None, 'password': None,
                'display_name': None, 'plan': 'free', 'awaiting': None,
            }

    awaiting = state.get('awaiting')
    last_a = _last_assistant_text(history).lower()
    if not awaiting and last_a:
        if 'mot de passe' in last_a or 'password' in last_a:
            awaiting = state['awaiting'] = 'password'
        elif 'adresse email' in last_a or 'adresse e-mail' in last_a:
            awaiting = state['awaiting'] = 'email'

    # Changement de rôle tant que l'email n'est pas fixé
    if role and not state.get('email') and role != state.get('role'):
        state['role'] = role
    if awaiting == 'role' and role:
        state['role'] = role

    # Extraction de tout champ présent dans le message
    em = _extract_email(text)
    if em:
        state['email'] = em
    plan = _extract_plan(low)
    if plan:
        state['plan'] = plan
    plab = _extract_password_labeled(text)
    if plab:
        state['password'] = plab
    nlab = _extract_name_labeled(text)
    if nlab:
        state['display_name'] = nlab

    # Mot de passe : étape explicite OU déduit de l'historique (session perdue)
    if not state.get('password') and not em:
        need_pw = awaiting == 'password' or 'mot de passe' in last_a
        if need_pw:
            pw = _capture_password(text)
            if pw:
                state['password'] = pw

    # Nom positionnel : on a explicitement demandé le nom
    if (
        awaiting == 'name' and state.get('email') and state.get('password')
        and state.get('display_name') is None and not em and not nlab
    ):
        if low in _SIGNUP_SKIP:
            state['display_name'] = ''
        else:
            nm = text.strip().strip('"\'')
            state['display_name'] = nm[:120] if nm else ''

    # Étape suivante : demander ce qui manque, sinon créer
    if not state.get('role'):
        state['awaiting'] = 'role'
        _save_signup_state(state)
        return _signup_reply(
            "Avec plaisir ! Quel type de compte souhaitez-vous créer : "
            "**galerie**, **artiste** ou **collectionneur** ?",
            ctx, state,
        )

    rlabel = _ROLE_LABEL.get(state['role'], state['role'])
    if not state.get('email'):
        state['awaiting'] = 'email'
        _save_signup_state(state)
        return _signup_reply(
            f"Parfait, créons votre compte **{rlabel}**. Quelle est votre **adresse email** ?",
            ctx, state,
        )

    if not state.get('password'):
        state['awaiting'] = 'password'
        _save_signup_state(state)
        return _signup_reply(
            "Merci ! Choisissez maintenant un **mot de passe** (au moins 6 caractères). "
            "Il restera confidentiel.",
            ctx, state,
        )

    # Nom optionnel : création directe (modifiable dans le profil ensuite)
    if state.get('display_name') is None:
        state['display_name'] = ''

    # Tout est collecté → création
    result = execute_tool('create_account', {
        'email': state['email'],
        'password': state['password'],
        'role': state['role'],
        'plan': state.get('plan') or 'free',
        'display_name': state.get('display_name') or '',
    }, ctx)

    if result.get('ok'):
        session.pop('aria_signup', None)
        session.modified = True
    elif result.get('code') == 'email_taken' or 'mot de passe' in (result.get('error') or '').lower():
        state['password'] = None
        state['awaiting'] = 'password'
        _save_signup_state(state)

    return _signup_reply(format_signup_reply(result, role=state['role']), ctx, state)


def _has_login_intent(low: str) -> bool:
    if _has_signup_intent(low):
        return False
    keys = ('connect', 'connexion', 'connecter', 'login', 'identif', 'se connecter')
    return any(k in low for k in keys)


def _handle_login_flow(text: str, ctx: dict[str, Any], history: list[dict]) -> dict[str, Any] | None:
    """Connexion directe email + mot de passe (sans passer par le LLM)."""
    from flask_login import current_user
    from .aria_tools import execute_tool

    if current_user.is_authenticated:
        return None

    low = text.lower().strip()
    em = _extract_email(text)
    pw = _capture_password(text)

    # Connexion en une phrase : email + mot de passe
    if em and pw and not _has_signup_intent(low):
        result = execute_tool('login_account', {'email': em, 'password': pw}, ctx)
        if result.get('ok'):
            msg = (
                f"Connexion réussie — bienvenue **{result.get('username', 'sur Artworks')}** !\n\n"
                f"[Accéder au tableau de bord](/dashboard)"
            )
        else:
            msg = f"**{result.get('error', 'Connexion impossible.')}**"
        return _signup_reply(msg, ctx)

    last_a = _last_assistant_text(history).lower()
    login_pw_step = (
        ('mot de passe' in last_a or 'password' in last_a)
        and any(w in last_a for w in ('connect', 'connexion', 'identif'))
        and 'créons votre compte' not in last_a
    )
    client_login = ctx.get('client_login') if isinstance(ctx.get('client_login'), dict) else {}
    if client_login.get('awaiting') == 'password' or login_pw_step:
        email = client_login.get('email') or _last_user_email(history)
        if not pw:
            pw = _capture_password(text)
        if email and pw:
            result = execute_tool('login_account', {'email': email, 'password': pw}, ctx)
            if result.get('ok'):
                msg = (
                    f"Connexion réussie — bienvenue **{result.get('username', '')}** !\n\n"
                    f"[Accéder au tableau de bord](/dashboard)"
                )
            else:
                msg = f"**{result.get('error', 'Connexion impossible.')}**"
            return _signup_reply(msg, ctx)

    if _has_login_intent(low) and em and not pw:
        return {
            **_signup_reply(
                f"Merci. Quel est votre **mot de passe** pour {em} ?",
                ctx,
            ),
            'login_state': {'email': em, 'awaiting': 'password'},
        }

    if _has_login_intent(low) and not em:
        return _signup_reply(
            "Pour vous connecter, indiquez votre **adresse email**.",
            ctx,
        )

    return None


def _norm_page_msg(text: str) -> str:
    return (text or '').lower().replace('œ', 'oe').replace('’', "'")


def _has_page_structure_intent(low: str) -> bool:
    keys = (
        'structure ma page', 'structure de page', 'structurer ma page',
        'structurer la page', 'structure ideale', 'page ideale',
        'refaire la structure', 'refaire la page', 'reconstruire la page',
        'construire ma page', 'construire la page', 'mise en page',
        'pour vendre mes oeuvres', 'vendre mes oeuvres',
    )
    if any(k in low for k in keys):
        return True
    return 'page' in low and any(v in low for v in ('structur', 'construi', 'refair', 'cree', 'cré', 'creer'))


def _has_presentation_intent(low: str) -> bool:
    if 'redige ma presentation' in low or 'rédige ma présentation' in low:
        return True
    return 'presentation' in low and any(v in low for v in ('redige', 'rédige', 'ecris', 'écris', 'rediger', 'rédiger'))


def _has_seo_intent(low: str) -> bool:
    return 'seo' in low or 'referencement' in low or 'référencement' in low


def _handle_page_editor_flow(text: str, ctx: dict, history: list) -> dict[str, Any] | None:
    """Applique directement la mise en page (brouillon) — fiable, sans JSON copier-coller."""
    from flask_login import current_user
    from .aria_tools import execute_tool
    from .page_layout_builder import (
        build_presentation_page_blocks,
        build_selling_page_blocks,
        build_seo_page_blocks,
    )

    user = ctx.get('user') or current_user
    if not user.is_authenticated or user.role not in ('artiste', 'galerie'):
        return None

    low = _norm_page_msg(text)
    mode = None
    if _has_presentation_intent(low):
        mode = 'presentation'
    elif _has_seo_intent(low):
        mode = 'seo'
    elif _has_page_structure_intent(low):
        mode = 'selling'
    else:
        return None

    page_data = execute_tool('get_my_page', {}, ctx)
    if not page_data.get('ok'):
        return {
            'reply': f"**{page_data.get('error', 'Impossible de lire votre page.')}**",
            'name': ARIA_NAME,
            'actions': list(ctx.get('side_effects') or []),
        }

    builders = {
        'selling': build_selling_page_blocks,
        'presentation': build_presentation_page_blocks,
        'seo': build_seo_page_blocks,
    }
    blocks = builders[mode](user, page_data)
    result = execute_tool('set_page_layout', {'blocks': blocks, 'publish': False, 'draft': True}, ctx)

    if not result.get('ok'):
        return {
            'reply': f"**{result.get('error', 'Échec de la mise en page.')}**",
            'name': ARIA_NAME,
            'actions': list(ctx.get('side_effects') or []),
        }

    count = result.get('count', len(blocks))
    labels = {
        'selling': (
            f'**Page structurée** ({count} blocs) — consultez l\'aperçu à droite. '
            'Cliquez sur **Enregistrer** pour publier ou **Annuler** pour revenir en arrière.'
        ),
        'presentation': (
            f'**Présentation rédigée** ({count} blocs). Vérifiez l\'aperçu à droite, puis **Enregistrer** pour publier.'
        ),
        'seo': (
            f'**Page optimisée** ({count} blocs). L\'aperçu est à jour — validez avec **Enregistrer** si cela vous convient.'
        ),
    }
    out: dict[str, Any] = {'reply': labels[mode], 'name': ARIA_NAME}
    effects = ctx.get('side_effects') or []
    if effects:
        out['actions'] = effects
    return out


def chat(
    user_message: str,
    *,
    reset: bool = False,
    client_context: list | None = None,
    client_signup: dict | None = None,
    client_login: dict | None = None,
) -> dict[str, Any]:
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

    history = _merge_histories(client_context, _history())
    ctx: dict[str, Any] = {
        'user': current_user,
        'side_effects': [],
        'client_signup': client_signup,
        'client_login': client_login,
    }

    login_flow = _handle_login_flow(text, ctx, history)
    if login_flow:
        history.append({'role': 'user', 'content': text})
        history.append({'role': 'assistant', 'content': login_flow['reply']})
        _save_history(history)
        out = dict(login_flow)
        if not out.get('actions'):
            out.pop('actions', None)
        return out

    signup = _handle_signup_flow(text, ctx, history)
    if signup:
        history.append({'role': 'user', 'content': text})
        history.append({'role': 'assistant', 'content': signup['reply']})
        _save_history(history)
        out = dict(signup)
        if not out.get('actions'):
            out.pop('actions', None)
        return out

    page_flow = _handle_page_editor_flow(text, ctx, history)
    if page_flow:
        history.append({'role': 'user', 'content': text})
        history.append({'role': 'assistant', 'content': page_flow['reply']})
        _save_history(history)
        out = dict(page_flow)
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

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
- Tu disposes d'**outils** pour lire le catalogue (œuvres, profils) et pour agir sur le site : créer un compte (`create_account`), **connecter** (`login_account`), changer de rôle (`change_my_role`), profil/œuvres/images, abonnement, etc.
- **INSCRIPTION** : la collecte des identifiants est gérée par un flux guidé du site. Tu **ne dois JAMAIS inventer** d'email, de mot de passe ni de nom. Si l'utilisateur veut un compte, demande-lui son **email**, puis son **mot de passe** ; n'appelle `create_account` **que** lorsque l'utilisateur a fourni email ET mot de passe explicitement.
- Le **nom de galerie** = `display_name` (espaces autorisés, ex. « Artworks Salon »). **Username** : 3–64 caractères, généré auto — **ne jamais** inventer de limite à 12 ou 20 caractères.
- **Ne jamais** refuser un nom pour longueur sans avoir appelé l'outil.
- Quand il demande une **action** (autre que l'inscription) → **APPELLE L'OUTIL** immédiatement.

ÉDITEUR DE PAGE (compte artiste/galerie connecté) :
- Quand on te demande de **structurer / construire / refaire la page** : appelle `get_my_page` puis `set_page_layout` (brouillon). L'utilisateur valide avec **Enregistrer** ou **Annuler** — ne dis pas que c'est publié tant qu'il n'a pas validé.
- **Refonte** : si `current_blocks` ou `has_draft` est vrai, `set_page_layout` **remplace** toute la page — réutilise le contenu utile des blocs existants, ne recopie pas en plus le profil/bio déjà présents dans les blocs.
- **Design galerie haut de gamme** : sobre, éditorial, typographie élégante (Cormorant). Inspirations : page de galerie d'art contemporain (pas de blog, pas de flyer).
- **INTERDIT dans les blocs `text` / `heading`** : emojis, markdown (`**`, `##`, listes `-`), liens markdown `[texte](url)`. Uniquement **texte français brut**.
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
    session.pop('aria_signup_role', None)
    session.pop('aria_signup_pending', None)
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


def _signup_reply(message: str, ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {'reply': message, 'name': ARIA_NAME}
    if ctx and ctx.get('side_effects'):
        out['actions'] = ctx['side_effects']
    return out


def _save_signup_state(state: dict) -> None:
    session['aria_signup'] = state
    session.modified = True


def _handle_signup_flow(text: str, ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Collecte guidée des informations d'inscription, étape par étape.

    Retourne une réponse Aria si la conversation porte sur une inscription,
    sinon None (le LLM prend le relais). Ne crée jamais le compte tant que
    l'email ET le mot de passe n'ont pas été donnés explicitement."""
    from flask_login import current_user
    from .aria_tools import execute_tool, format_signup_reply

    if current_user.is_authenticated:
        session.pop('aria_signup', None)
        return None

    low = text.lower().strip()
    state = session.get('aria_signup')
    if not isinstance(state, dict):
        state = None

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
        if not _has_signup_intent(low):
            return None
        state = {
            'active': True, 'role': role, 'email': None, 'password': None,
            'display_name': None, 'plan': 'free', 'awaiting': None,
        }

    awaiting = state.get('awaiting')

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

    # Mot de passe positionnel : on a explicitement demandé le mot de passe
    if awaiting == 'password' and not state.get('password') and not em:
        cand = text.strip().strip('"\'').rstrip('.,;')
        if ' ' in cand:
            toks = [t for t in re.split(r'\s+', cand) if t]
            cand = toks[-1] if toks else cand
        if 6 <= len(cand) <= 128:
            state['password'] = cand

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
            "**galerie**, **artiste** ou **collectionneur** ?"
        )

    rlabel = _ROLE_LABEL.get(state['role'], state['role'])
    if not state.get('email'):
        state['awaiting'] = 'email'
        _save_signup_state(state)
        return _signup_reply(
            f"Parfait, créons votre compte **{rlabel}**. Quelle est votre **adresse email** ?"
        )

    if not state.get('password'):
        state['awaiting'] = 'password'
        _save_signup_state(state)
        return _signup_reply(
            "Merci ! Choisissez maintenant un **mot de passe** (au moins 6 caractères). "
            "Il restera confidentiel."
        )

    if state.get('display_name') is None:
        state['awaiting'] = 'name'
        _save_signup_state(state)
        if state['role'] == 'galerie':
            q = "Et quel est le **nom de votre galerie** ? (ou répondez « passer »)"
        elif state['role'] == 'artiste':
            q = "Sous quel **nom d'artiste** souhaitez-vous apparaître ? (ou « passer »)"
        else:
            q = "Quel **nom** souhaitez-vous afficher sur votre profil ? (ou « passer »)"
        return _signup_reply(q)

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
        # Email déjà pris / mauvais mot de passe → on redemande le mot de passe
        state['password'] = None
        state['awaiting'] = 'password'
        _save_signup_state(state)

    return _signup_reply(format_signup_reply(result, role=state['role']), ctx)


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

    signup = _handle_signup_flow(text, ctx)
    if signup:
        history.append({'role': 'user', 'content': text})
        history.append({'role': 'assistant', 'content': signup['reply']})
        _save_history(history)
        out = dict(signup)
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

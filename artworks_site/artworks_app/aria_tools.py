"""Outils Aria — actions réelles sur le compte connecté (function calling)."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from flask import current_app, session, url_for
from flask_login import current_user, login_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from . import db
from .models import Artwork, GalleryArtist, PriceAlert, Series, User

_log = logging.getLogger(__name__)

_MAX_AGENT_STEPS = 8
_PENDING_KEY = 'aria_pending_images'


def _image_url(value: str | None) -> str | None:
    """URL absolue d'une image œuvre/profil pour l'affichage dans le chat Aria."""
    from .storage import absolute_url
    return absolute_url(value)


def save_upload_file(file_storage) -> str | None:
    from .storage import save_upload
    return save_upload(file_storage)


def pending_images() -> list[str]:
    raw = session.get(_PENDING_KEY) or []
    return [x for x in raw if isinstance(x, str) and x]


def push_pending_image(filename: str) -> None:
    imgs = pending_images()
    imgs.append(filename)
    session[_PENDING_KEY] = imgs[-5:]
    session.modified = True


def pop_pending_image() -> str | None:
    imgs = pending_images()
    if not imgs:
        return None
    fn = imgs.pop(0)
    session[_PENDING_KEY] = imgs
    session.modified = True
    return fn


def clear_pending_images() -> None:
    session.pop(_PENDING_KEY, None)
    session.modified = True


def _tool(name: str, description: str, properties: dict, required: list | None = None):
    schema: dict[str, Any] = {'type': 'object', 'properties': properties}
    if required:
        schema['required'] = required
    return {'type': 'function', 'function': {'name': name, 'description': description, 'parameters': schema}}


TOOLS_PUBLIC = [
    _tool(
        'platform_info',
        'Infos générales Artworks : formules, commission, pages utiles. Pas d\'action compte.',
        {'topic': {'type': 'string', 'description': 'Sujet optionnel : tarifs, commission, inscription, achat'}},
    ),
    _tool(
        'search_artworks',
        'Recherche dans le catalogue public d\'œuvres.',
        {
            'query': {'type': 'string'},
            'discipline': {'type': 'string'},
            'limit': {'type': 'integer', 'description': 'Max 12'},
        },
    ),
    _tool(
        'search_artists',
        'Recherche des profils publics : artistes, galeries ou collectionneurs.',
        {
            'role': {'type': 'string', 'enum': ['artiste', 'galerie', 'collectionneur']},
            'query': {'type': 'string'},
            'limit': {'type': 'integer'},
        },
    ),
    _tool(
        'get_artwork',
        'Détail complet d\'une œuvre par ID : prix, disponibilité et lien d\'achat (pour vendre).',
        {'artwork_id': {'type': 'integer'}},
        ['artwork_id'],
    ),
    _tool(
        'get_profile',
        'Profil public complet par ID (artiste, galerie ou collectionneur) : présentation, '
        'lien du portfolio/wishlist et liste des œuvres en vente avec prix et liens d\'achat.',
        {'user_id': {'type': 'integer'}},
        ['user_id'],
    ),
    _tool(
        'login_account',
        'Connecte un utilisateur existant (email + mot de passe). À utiliser si create_account échoue car l\'email existe déjà.',
        {
            'email': {'type': 'string'},
            'password': {'type': 'string'},
        },
        ['email', 'password'],
    ),
    _tool(
        'create_account',
        'Crée ou active un compte Artworks (email existant + bon mot de passe = connexion + rôle). '
        'display_name = nom public de la galerie (espaces OK). username optionnel (généré automatiquement).',
        {
            'role': {'type': 'string', 'enum': ['artiste', 'galerie', 'collectionneur']},
            'display_name': {'type': 'string', 'description': 'Nom affiché public (ex. Galerie Dupont)'},
            'username': {'type': 'string', 'description': 'Optionnel — identifiant technique, 3-64 car.'},
            'email': {'type': 'string'},
            'password': {'type': 'string'},
            'plan': {'type': 'string', 'description': 'free, gratuit, portfolio, pro, membre, patron, premium…'},
        },
        ['role', 'email', 'password'],
    ),
]

TOOLS_AUTH = [
    _tool(
        'change_my_role',
        'Compte connecté : change le rôle (ex. collectionneur → galerie). Réinitialise la formule gratuite du nouveau rôle.',
        {
            'role': {'type': 'string', 'enum': ['artiste', 'galerie', 'collectionneur']},
        },
        ['role'],
    ),
    _tool(
        'get_my_profile',
        'Lit le profil du compte connecté (tous rôles).',
        {},
    ),
    _tool(
        'update_my_profile',
        'Met à jour le profil connecté. Plusieurs champs en un appel.',
        {
            'display_name': {'type': 'string'},
            'email': {'type': 'string'},
            'discipline': {'type': 'string'},
            'location': {'type': 'string'},
            'gallery': {'type': 'string', 'description': 'Galerie / studio'},
            'description': {'type': 'string'},
            'statement': {'type': 'string'},
            'bio': {'type': 'string'},
        },
    ),
    _tool(
        'update_my_password',
        'Change le mot de passe du compte connecté (comptes email, pas Google seul).',
        {'new_password': {'type': 'string', 'description': 'Min 6 caractères'}},
        ['new_password'],
    ),
    _tool(
        'list_pending_uploads',
        'Liste les images jointes via le bouton 📎 en attente d\'être assignées à une œuvre ou au profil.',
        {},
    ),
    _tool(
        'set_profile_image',
        'Assigne la dernière image jointe (📎) au profil : avatar, cover ou logo.',
        {
            'field': {'type': 'string', 'enum': ['avatar', 'cover', 'logo']},
            'image_filename': {'type': 'string', 'description': 'Optionnel — sinon utilise la dernière image en attente'},
        },
        ['field'],
    ),
    _tool(
        'list_my_artworks',
        'Liste les œuvres du compte connecté (artiste/galerie).',
        {},
    ),
    _tool(
        'add_artwork',
        'Ajoute une œuvre au portfolio connecté. image_filename optionnel si upload 📎 récent.',
        {
            'title': {'type': 'string'},
            'description': {'type': 'string'},
            'price': {'type': 'number'},
            'discipline': {'type': 'string'},
            'medium': {'type': 'string'},
            'dimensions': {'type': 'string'},
            'year': {'type': 'string'},
            'series_id': {'type': 'integer'},
            'image_filename': {'type': 'string'},
        },
        ['title'],
    ),
    _tool(
        'update_artwork',
        'Modifie une œuvre appartenant au compte connecté.',
        {
            'artwork_id': {'type': 'integer'},
            'title': {'type': 'string'},
            'description': {'type': 'string'},
            'price': {'type': 'number'},
            'discipline': {'type': 'string'},
            'medium': {'type': 'string'},
            'dimensions': {'type': 'string'},
            'year': {'type': 'string'},
            'status': {'type': 'string', 'enum': ['dispo', 'reserve', 'vendu']},
            'series_id': {'type': 'integer'},
        },
        ['artwork_id'],
    ),
    _tool(
        'set_artwork_image',
        'Met à jour l\'image d\'une œuvre (upload 📎 ou filename).',
        {
            'artwork_id': {'type': 'integer'},
            'image_filename': {'type': 'string'},
        },
        ['artwork_id'],
    ),
    _tool(
        'delete_artwork',
        'Supprime une œuvre du compte connecté.',
        {'artwork_id': {'type': 'integer'}},
        ['artwork_id'],
    ),
    _tool(
        'list_my_series',
        'Liste les séries du compte connecté.',
        {},
    ),
    _tool(
        'add_series',
        'Crée une série.',
        {'name': {'type': 'string'}, 'description': {'type': 'string'}, 'year': {'type': 'string'}},
        ['name'],
    ),
    _tool(
        'update_series',
        'Modifie une série.',
        {
            'series_id': {'type': 'integer'},
            'name': {'type': 'string'},
            'description': {'type': 'string'},
            'year': {'type': 'string'},
        },
        ['series_id'],
    ),
    _tool(
        'delete_series',
        'Supprime une série (les œuvres restent, sans série).',
        {'series_id': {'type': 'integer'}},
        ['series_id'],
    ),
    _tool(
        'generate_curatorial_note',
        'Génère ou régénère la note curatoriale IA du profil connecté.',
        {},
    ),
    _tool(
        'get_my_page',
        'Lit la page publique : brouillon en cours (prioritaire), blocs actuels (current_blocks), '
        'profil et URLs images œuvres. Toujours appeler avant set_page_layout.',
        {},
    ),
    _tool(
        'set_page_layout',
        'Remplace entièrement la page (brouillon). Blocs ORDONNÉS, texte BRUT sans emoji ni markdown. '
        'Si current_blocks existe : refonte = nouvelle liste complète qui remplace l\'ancienne (pas d\'ajout). '
        'Types : heading, text, divider, gallery/slider (images de get_my_page), button (href requis).',
        {
            'blocks': {
                'type': 'array',
                'description': '8–14 blocs max, texte plain uniquement (pas de ** ni emojis). Remplace tout.',
                'items': {
                    'type': 'object',
                    'properties': {
                        'type': {'type': 'string', 'enum': ['heading', 'text', 'button', 'image', 'divider', 'slider', 'gallery']},
                        'text': {'type': 'string', 'description': 'Texte brut FR, court, sans markdown ni emoji'},
                        'href': {'type': 'string', 'description': 'Lien du bouton (interne ou http)'},
                        'src': {'type': 'string', 'description': 'URL image (type image)'},
                        'images': {'type': 'array', 'items': {'type': 'string'}, 'description': 'URLs (slider/gallery)'},
                        'width': {'type': 'integer'},
                        'align': {'type': 'string', 'enum': ['left', 'center', 'right']},
                        'color': {'type': 'string', 'description': 'Couleur texte hex #RRGGBB'},
                        'bg': {'type': 'string', 'description': 'Fond hex #RRGGBB'},
                        'font': {'type': 'string', 'enum': ['sans', 'serif', 'display', 'mono']},
                        'size': {'type': 'integer', 'description': 'Taille police px'},
                        'weight': {'type': 'integer', 'description': 'Graisse 400-700'},
                    },
                },
            },
            'publish': {'type': 'boolean', 'description': 'Publier (défaut: oui)'},
        },
        ['blocks'],
    ),
    _tool(
        'publish_my_page',
        'Publie ou masque la page publique personnalisée.',
        {'published': {'type': 'boolean'}},
    ),
    _tool(
        'get_subscription_status',
        'Statut abonnement et formule du compte connecté.',
        {},
    ),
    _tool(
        'list_available_plans',
        'Liste les formules disponibles pour le rôle du compte connecté.',
        {},
    ),
    _tool(
        'request_subscription_checkout',
        'Démarre l\'activation d\'une formule payante (redirection Stripe ou démo).',
        {'plan_slug': {'type': 'string'}},
        ['plan_slug'],
    ),
    _tool(
        'toggle_price_alert',
        'Collectionneur : active/désactive une alerte prix sur une œuvre.',
        {'artwork_id': {'type': 'integer'}},
        ['artwork_id'],
    ),
    _tool(
        'list_gallery_artists',
        'Galerie : liste les artistes rattachés.',
        {},
    ),
    _tool(
        'add_gallery_artist',
        'Galerie : ajoute un artiste au catalogue.',
        {'name': {'type': 'string'}, 'discipline': {'type': 'string'}},
        ['name'],
    ),
    _tool(
        'delete_gallery_artist',
        'Galerie : retire un artiste rattaché.',
        {'gallery_artist_id': {'type': 'integer'}},
        ['gallery_artist_id'],
    ),
]

TOOLS_STAFF = [
    _tool(
        'admin_search_users',
        'Staff uniquement : recherche comptes par email ou username.',
        {'query': {'type': 'string'}, 'limit': {'type': 'integer'}},
        ['query'],
    ),
]


def tools_for_user(user) -> list[dict]:
    tools = list(TOOLS_PUBLIC)
    if user and user.is_authenticated:
        tools.extend(TOOLS_AUTH)
        from .crm.auth import is_staff_user
        if is_staff_user(user):
            tools.extend(TOOLS_STAFF)
    return tools


def _require_user(ctx: dict) -> User | None:
    u = ctx.get('user')
    if u and getattr(u, 'is_authenticated', False):
        return u
    return None


def _side(ctx: dict, effect: dict) -> None:
    ctx.setdefault('side_effects', []).append(effect)


def _auth_success_side(ctx: dict, user: User) -> None:
    """Après connexion / inscription : CRM pour admin, dashboard pour les membres."""
    from .auth_redirect import home_url_for
    _side(ctx, {'type': 'login', 'user_id': user.id})
    _side(ctx, {'type': 'redirect', 'url': home_url_for(user)})


def _resolve_image(args: dict, ctx: dict) -> str | None:
    fn = (args.get('image_filename') or '').strip()
    if fn:
        return fn
    return pop_pending_image()


def _normalize_plan_slug(role: str, plan: str) -> str:
    from .subscriptions import normalize_plan
    p = (plan or 'free').strip().lower()
    aliases = {
        'gratuit': 'free',
        'gratuite': 'free',
        'decouverte': 'free',
        'découverte': 'free',
        'free': 'free',
    }
    p = aliases.get(p, p)
    return normalize_plan(role, p)


def _slug_username(base: str) -> str:
    s = re.sub(r'[^a-zA-Z0-9_-]', '', (base or '').replace(' ', ''))
    return s[:64] if len(s) >= 3 else ''


def _unique_username(base: str) -> str:
    slug = _slug_username(base)
    base = slug or re.sub(r'\s+', '', (base or 'membre').strip())[:64]
    if len(base) < 3:
        base = 'membre'
    candidate = base
    n = 1
    while User.query.filter_by(username=candidate).first():
        candidate = f'{base}{n}'
        n += 1
    return candidate


def parse_signup_credentials(text: str) -> dict[str, str] | None:
    """Extrait email, mot de passe et nom depuis un message utilisateur (FR)."""
    if not text:
        return None
    t = text.strip()
    low = t.lower()

    email = None
    m = re.search(r'(?:mail|email)\s*[:=]\s*(\S+@\S+)', t, re.I)
    if m:
        email = m.group(1).strip().rstrip('.,;')
    if not email:
        m = re.search(r'[\w.+-]+@[\w.-]+\.\w+', t)
        if m:
            email = m.group(0).strip().rstrip('.,;')
    if not email:
        return None

    password = None
    m = re.search(r'(?:mdp|mot\s*de\s*passe|password)\s*[:=]\s*(\S+)', t, re.I)
    if m:
        password = m.group(1).strip().rstrip('.,;')
    if not password or len(password) < 6:
        return None

    display_name = ''
    m = re.search(
        r'(?:nom|username|utilisateur|galerie)\s*[:=]\s*([^|\n]+?)(?:\s*\||\s+formule|\s+role|\s+rôle|$)',
        t,
        re.I,
    )
    if m:
        display_name = m.group(1).strip()

    role = ''
    if 'galerie' in low:
        role = 'galerie'
    elif 'artiste' in low:
        role = 'artiste'
    elif 'collectionneur' in low:
        role = 'collectionneur'

    plan = 'free'
    m = re.search(r'formule\s*[:=]\s*(\S+)', t, re.I)
    if m:
        plan = m.group(1).strip().rstrip('.,;')
    elif any(w in low for w in ('gratuit', 'gratuite', 'découverte', 'decouverte', 'free')):
        plan = 'gratuit'

    out: dict[str, str] = {
        'email': email.lower(),
        'password': password,
        'display_name': display_name,
        'plan': plan,
    }
    if role:
        out['role'] = role
    return out


def format_signup_reply(result: dict, *, role: str = 'galerie') -> str:
    if result.get('error'):
        err = result['error']
        if result.get('code') == 'email_taken':
            return (
                f'**{err}**\n\n'
                'Vérifiez votre mot de passe ou utilisez [mot de passe oublié](/forgot-password).'
            )
        return f'**{err}**'

    name = result.get('display_name') or result.get('username') or 'votre compte'
    role_label = {'galerie': 'galerie', 'artiste': 'artiste', 'collectionneur': 'collectionneur'}.get(
        result.get('role') or role, role
    )
    if result.get('existing_account'):
        intro = f'Votre compte **{name}** est connecté (rôle : **{role_label}**).'
        if result.get('role_changed'):
            intro = f'Compte existant converti en **{role_label}** — bienvenue **{name}** !'
    else:
        intro = f'Votre compte **{role_label}** *{name}* est créé !'

    return (
        f'{intro}\n\n'
        f'- **Formule** : Découverte (gratuite)\n'
        f'- [Accéder au tableau de bord](/dashboard)\n\n'
        f'Ajoutez vos premières œuvres depuis le dashboard.'
    )


def execute_tool(name: str, args: dict, ctx: dict) -> dict:
    args = args or {}
    user = _require_user(ctx)

    if name == 'platform_info':
        from .aria_assistant import build_knowledge_context
        return {'ok': True, 'info': build_knowledge_context()[:4000]}

    if name == 'search_artworks':
        q = (args.get('query') or '').strip().lower()
        discipline = (args.get('discipline') or '').strip()
        limit = min(int(args.get('limit') or 8), 12)
        qs = Artwork.query
        if discipline:
            qs = qs.filter(Artwork.discipline == discipline)
        rows = qs.order_by(Artwork.id.desc()).limit(80).all()
        if q:
            rows = [
                a for a in rows
                if q in (a.title or '').lower()
                or q in (a.description or '').lower()
                or (a.owner and q in (a.owner.display_name or a.owner.username or '').lower())
            ]
        return {
            'ok': True,
            'count': len(rows[:limit]),
            'artworks': [
                {
                    'id': a.id,
                    'title': a.title,
                    'price': float(a.price) if a.price else None,
                    'price_label': a.price_str if a.price else 'Prix sur demande',
                    'discipline': a.discipline,
                    'artist': a.owner.name if a.owner else None,
                    'image': _image_url(a.image),
                    'url': f'/artwork/{a.id}',
                }
                for a in rows[:limit]
            ],
        }

    if name == 'search_artists':
        role = (args.get('role') or 'artiste').strip()
        q = (args.get('query') or '').strip().lower()
        limit = min(int(args.get('limit') or 8), 12)
        from .entitlements import has_public_portfolio, user_entitlements
        rows = User.query.filter_by(role=role).limit(150).all()
        if role == 'collectionneur':
            # Collectionneurs « lisibles » publiquement = wishlist partageable activée.
            rows = [u for u in rows if user_entitlements(u).get('shareable_wishlist') and u.wishlist_share_token]
        else:
            rows = [u for u in rows if has_public_portfolio(u)]
        if q:
            rows = [
                u for u in rows
                if q in (u.display_name or '').lower() or q in (u.username or '').lower()
            ]
        return {
            'ok': True,
            'profiles': [
                {
                    'id': u.id,
                    'name': u.name,
                    'role': u.role,
                    'discipline': u.discipline,
                    'url': (f'/wishlist/{u.wishlist_share_token}' if role == 'collectionneur'
                            else f'/artist/{u.id}'),
                }
                for u in rows[:limit]
            ],
        }

    if name == 'get_profile':
        uid = int(args.get('user_id') or 0)
        u = User.query.get(uid)
        if not u:
            return {'error': 'Profil introuvable.'}
        from .entitlements import has_public_portfolio, user_entitlements
        role = u.role or 'collectionneur'
        ent = user_entitlements(u)
        if role == 'collectionneur':
            if not (ent.get('shareable_wishlist') and u.wishlist_share_token):
                return {'error': 'Ce collectionneur n\'a pas de profil public.'}
            profile_url = f'/wishlist/{u.wishlist_share_token}'
        else:
            if not has_public_portfolio(u):
                return {'error': 'Ce profil n\'est pas encore public.'}
            profile_url = f'/artist/{u.id}'
        works = []
        if role in ('artiste', 'galerie'):
            buyable = bool(ent.get('marketplace_enabled'))
            for a in u.artworks:
                works.append({
                    'id': a.id,
                    'title': a.title,
                    'price_label': a.price_str if a.price else 'Prix sur demande',
                    'image': _image_url(a.image),
                    'available': a.status == 'dispo',
                    'buyable_online': bool(buyable and a.status == 'dispo' and a.price),
                    'url': f'/artwork/{a.id}',
                })
        return {
            'ok': True,
            'profile': {
                'id': u.id,
                'name': u.name,
                'role': role,
                'discipline': u.discipline,
                'location': u.location,
                'gallery': u.gallery,
                'bio': (u.description or u.statement or u.bio or '')[:600],
                'curatorial_note': (getattr(u, 'curatorial_note', None) or '')[:600],
                'profile_url': profile_url,
                'contact': u.email or 'contact@artworksdigital.fr',
                'artworks_for_sale': works,
                'artworks_count': len(works),
            },
        }

    if name == 'get_artwork':
        aid = int(args.get('artwork_id') or 0)
        a = Artwork.query.get(aid)
        if not a:
            return {'error': 'Œuvre introuvable.'}
        from .entitlements import has_public_portfolio, user_entitlements
        owner_ent = user_entitlements(a.owner) if a.owner else {}
        # La page /artwork/<id> renvoie 404 si le portfolio n'est pas public :
        # on ne propose un lien d'achat que si l'œuvre est réellement consultable.
        publicly_visible = (
            a.owner is None
            or a.owner.role not in ('artiste', 'galerie')
            or has_public_portfolio(a.owner)
        )
        buyable = bool(
            publicly_visible and owner_ent.get('marketplace_enabled')
            and a.status == 'dispo' and a.price
        )
        contact = (a.owner.email if a.owner else None) or 'contact@artworksdigital.fr'
        return {
            'ok': True,
            'artwork': {
                'id': a.id,
                'title': a.title,
                'description': (a.description or '')[:600],
                'price': float(a.price) if a.price else None,
                'price_label': a.price_str if a.price else 'Prix sur demande',
                'image': _image_url(a.image),
                'discipline': a.discipline,
                'medium': a.technique or a.medium,
                'dimensions': a.dimensions,
                'year': a.year,
                'status': a.status,
                'available': a.status == 'dispo',
                'for_sale': bool(a.price) and a.status != 'reserve',
                'buyable_online': buyable,
                'buy_url': f'/artwork/{a.id}' if buyable else None,
                'url': f'/artwork/{a.id}' if publicly_visible else None,
                'contact': contact,
                'artist_id': a.user_id,
                'artist': a.owner.name if a.owner else None,
            },
        }

    if name == 'login_account':
        if user:
            return {'error': 'Vous êtes déjà connecté.', 'username': user.username}
        ident = (args.get('email') or args.get('username') or '').strip()
        password = args.get('password') or ''
        if not ident or not password:
            return {'error': 'Identifiant (email ou nom d\'utilisateur) et mot de passe requis.'}
        u = User.query.filter(
            or_(User.email == ident.lower(), User.username == ident)
        ).first()
        if not u:
            return {'error': 'Aucun compte avec cet identifiant.'}
        if not u.check_password(password):
            return {'error': 'Mot de passe incorrect.'}
        login_user(u)
        ctx['user'] = u
        _auth_success_side(ctx, u)
        return {
            'ok': True,
            'user_id': u.id,
            'username': u.username,
            'role': u.role,
            'message': 'Connexion réussie.',
        }

    if name == 'create_account':
        if user:
            return {'error': 'Vous êtes déjà connecté. Déconnectez-vous pour créer un autre compte.'}
        role = (args.get('role') or 'collectionneur').strip()
        username = (args.get('username') or '').strip()
        display_name = (args.get('display_name') or '').strip()
        email = (args.get('email') or '').strip().lower()
        password = args.get('password') or ''
        plan = (args.get('plan') or 'free').strip()
        if role not in ('artiste', 'galerie', 'collectionneur'):
            return {'error': 'Rôle invalide — utilisez artiste, galerie ou collectionneur.'}
        if not email or len(password) < 6:
            return {'error': 'Email et mot de passe (6+ caractères) requis.'}
        if not display_name and username:
            display_name = username
        name_seed = display_name or username or email.split('@')[0]
        if not username or len(username) < 3:
            username = _unique_username(_slug_username(name_seed) or name_seed)
        else:
            username = _unique_username(_slug_username(username) or username)
        existing = User.query.filter_by(email=email).first()
        if existing:
            if not existing.check_password(password):
                return {
                    'error': 'Cet email est déjà utilisé avec un autre mot de passe.',
                    'code': 'email_taken',
                    'existing_username': existing.username,
                    'existing_role': existing.role,
                }
            role_changed = existing.role != role
            if role_changed:
                existing.role = role
                existing.subscription_plan = 'free'
                existing.subscription_status = 'active'
            if display_name:
                existing.display_name = display_name[:120]
            db.session.commit()
            try:
                from .crm.auto_segments import classify_user
                classify_user(existing)
            except Exception:
                pass
            try:
                login_user(existing)
            except Exception as exc:
                _log.warning('Aria login existing user failed: %s', exc)
            ctx['user'] = existing
            _auth_success_side(ctx, existing)
            return {
                'ok': True,
                'existing_account': True,
                'role_changed': role_changed,
                'user_id': existing.id,
                'username': existing.username,
                'display_name': existing.display_name or existing.username,
                'role': existing.role,
                'logged_in': True,
            }
        from .auth import _apply_free_plan, _welcome_user

        slug = _normalize_plan_slug(role, plan)
        u = User(
            username=username,
            email=email,
            role=role,
            display_name=(display_name or username)[:120],
        )
        u.set_password(password)
        pending_paid = _apply_free_plan(u, role, slug)
        try:
            db.session.add(u)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {'error': 'Impossible de créer le compte — identifiant ou email déjà pris.'}
        try:
            login_user(u)
            _welcome_user(u)
        except Exception as exc:
            _log.warning('Aria post-register hooks failed: %s', exc)
        ctx['user'] = u
        _auth_success_side(ctx, u)
        if pending_paid:
            from . import billing
            checkout = billing.create_checkout_session(
                u, pending_paid,
                success_url=url_for('main.subscription_success', _external=True),
                cancel_url=url_for('main.subscription', _external=True),
            )
            if checkout:
                _side(ctx, {'type': 'redirect', 'url': checkout})
                return {'ok': True, 'user_id': u.id, 'checkout_url': checkout, 'plan_pending': pending_paid}
            if current_app.config.get('STRIPE_DEMO_MODE'):
                billing.demo_activate_plan(u, pending_paid)
                db.session.commit()
        pending_img = pop_pending_image()
        if pending_img and role in ('artiste', 'galerie'):
            from .entitlements import can_publish_artwork
            ok, _err = can_publish_artwork(u)
            if ok:
                art = Artwork(title='Sans titre', image=pending_img, user_id=u.id, status='dispo')
                db.session.add(art)
                db.session.commit()
                return {'ok': True, 'user_id': u.id, 'first_artwork_id': art.id, 'logged_in': True, 'role': role}
        return {'ok': True, 'user_id': u.id, 'role': role, 'username': username, 'logged_in': True}

    if not user:
        return {'error': 'Connexion requise — utilisez login_account ou create_account.'}

    if name == 'change_my_role':
        role = (args.get('role') or '').strip()
        if role not in ('artiste', 'galerie', 'collectionneur'):
            return {'error': 'Rôle invalide.'}
        if user.role == role:
            return {'ok': True, 'role': role, 'message': f'Vous êtes déjà {role}.'}
        user.role = role
        user.subscription_plan = 'free'
        user.subscription_status = 'active'
        db.session.commit()
        try:
            from .crm.auto_segments import classify_user
            classify_user(user)
        except Exception:
            pass
        _side(ctx, {'type': 'reload'})
        return {'ok': True, 'role': role, 'message': f'Rôle mis à jour : {role}.'}

    if name == 'get_my_profile':
        return {
            'ok': True,
            'profile': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'display_name': user.display_name,
                'discipline': user.discipline,
                'location': user.location,
                'gallery': user.gallery,
                'description': (user.description or '')[:800],
                'statement': (user.statement or '')[:800],
                'bio': (user.bio or '')[:800],
                'subscription_plan': user.subscription_plan,
                'subscription_status': user.subscription_status,
                'artworks_count': len(user.artworks),
                'series_count': len(user.series),
            },
        }

    if name == 'update_my_profile':
        updated = []
        mapping = {
            'display_name': 'display_name',
            'email': 'email',
            'discipline': 'discipline',
            'location': 'location',
            'gallery': 'gallery',
            'description': 'description',
            'statement': 'statement',
            'bio': 'bio',
        }
        for arg_key, field in mapping.items():
            if args.get(arg_key) is not None and str(args.get(arg_key)).strip() != '':
                val = str(args[arg_key]).strip()
                if field == 'email':
                    val = val.lower()
                    if User.query.filter(User.email == val, User.id != user.id).first():
                        return {'error': 'Email déjà utilisé.'}
                setattr(user, field, val)
                updated.append(field)
        if not updated:
            return {'error': 'Aucun champ à mettre à jour.'}
        db.session.commit()
        _side(ctx, {'type': 'reload'})
        return {'ok': True, 'updated': updated}

    if name == 'get_my_page':
        import json
        from .page_staging import load_page_draft
        from .page_blocks import elements_to_blocks

        has_draft = False
        layout = None
        draft = load_page_draft(user)
        if draft and isinstance(draft.get('layout'), dict):
            layout = draft['layout']
            has_draft = True
        elif user.page_layout_json:
            try:
                layout = json.loads(user.page_layout_json)
            except (ValueError, TypeError):
                layout = None
        elements = (layout or {}).get('elements') or []
        current_blocks = elements_to_blocks(elements)
        arts = []
        for a in (user.artworks or [])[:24]:
            img = _image_url(a.image)
            arts.append({
                'id': a.id,
                'title': a.title,
                'image': img,
                'price_label': a.price_str if a.price else 'Prix sur demande',
            })
        return {
            'ok': True,
            'published': bool(user.page_published),
            'has_draft': has_draft,
            'element_count': len(elements),
            'current_blocks': current_blocks,
            'profile': {
                'display_name': user.display_name or user.username,
                'discipline': user.discipline,
                'location': user.location,
                'bio': (user.bio or '')[:600],
                'statement': (user.statement or '')[:600],
            },
            'artworks': arts,
            'artwork_images': [a['image'] for a in arts if a['image']],
            'page_url': f'/artist/{user.id}',
        }

    if name == 'set_page_layout':
        if user.role not in ('artiste', 'galerie'):
            return {'error': 'La page publique est réservée aux comptes artiste et galerie.'}
        import json
        from .page_blocks import arrange_vertical
        blocks_in = args.get('blocks')
        if not isinstance(blocks_in, list) or not blocks_in:
            return {'error': 'Fournissez une liste de blocs (blocks).'}
        norm = []
        for b in blocks_in[:60]:
            if not isinstance(b, dict):
                continue
            style = {}
            if isinstance(b.get('style'), dict):
                for k, v in b['style'].items():
                    if v not in (None, ''):
                        style[k] = v
            for k in ('color', 'bg', 'font', 'size', 'align', 'weight'):
                if b.get(k) not in (None, ''):
                    style[k] = b[k]
            norm.append({
                'type': b.get('type'),
                'text': b.get('text'),
                'src': b.get('src'),
                'href': b.get('href'),
                'images': b.get('images'),
                'width': b.get('width'),
                'height': b.get('height'),
                'style': style or None,
            })
        elements = arrange_vertical(norm)
        if not elements:
            return {'error': 'Aucun bloc valide à appliquer.'}
        payload = {
            'elements': elements,
            'canvas': {'w': 960},
            'updated_at': datetime.utcnow().isoformat(),
        }
        publish = args.get('publish')
        pub_flag = True if publish is None else bool(publish)
        commit = args.get('commit')
        use_draft = commit is not True and args.get('draft', True) is not False

        if use_draft:
            from .page_staging import load_page_draft, save_page_draft
            draft = load_page_draft(user) or {}
            if not draft.get('baseline_layout'):
                draft['baseline_layout'] = user.page_layout_json
                draft['baseline_published'] = bool(user.page_published)
            draft['layout'] = payload
            draft['published'] = pub_flag
            save_page_draft(user, draft)
            preview_url = url_for('main.page_preview_frame')
            _side(ctx, {
                'type': 'page_preview',
                'url': preview_url,
                'draft': True,
                'element_count': len(elements),
            })
            return {
                'ok': True,
                'draft': True,
                'count': len(elements),
                'published': pub_flag,
                'preview_url': preview_url,
                'message': 'Brouillon créé — validez ou annulez dans l\'éditeur.',
            }

        user.page_layout_json = json.dumps(payload, ensure_ascii=False)
        if publish is None or bool(publish):
            user.page_published = True
        db.session.commit()
        page_url = f'/artist/{user.id}'
        _side(ctx, {'type': 'page_updated', 'url': page_url})
        return {
            'ok': True,
            'count': len(elements),
            'published': bool(user.page_published),
            'page_url': page_url,
        }

    if name == 'publish_my_page':
        if user.role not in ('artiste', 'galerie'):
            return {'error': 'La page publique est réservée aux comptes artiste et galerie.'}
        user.page_published = bool(args.get('published', True))
        db.session.commit()
        page_url = f'/artist/{user.id}'
        _side(ctx, {'type': 'page_updated', 'url': page_url})
        return {'ok': True, 'published': bool(user.page_published), 'page_url': page_url}

    if name == 'update_my_password':
        if user.uses_google_auth and not user.password_hash:
            return {'error': 'Compte Google — utilisez la connexion Google.'}
        pw = args.get('new_password') or ''
        if len(pw) < 6:
            return {'error': 'Mot de passe : 6 caractères minimum.'}
        user.set_password(pw)
        db.session.commit()
        return {'ok': True, 'message': 'Mot de passe mis à jour.'}

    if name == 'list_pending_uploads':
        return {'ok': True, 'images': pending_images()}

    if name == 'set_profile_image':
        field = (args.get('field') or '').strip()
        if field not in ('avatar', 'cover', 'logo'):
            return {'error': 'field doit être avatar, cover ou logo.'}
        fn = _resolve_image(args, ctx)
        if not fn:
            return {'error': 'Aucune image en attente — joignez une image via 📎.'}
        setattr(user, field, fn)
        db.session.commit()
        _side(ctx, {'type': 'reload'})
        return {'ok': True, 'field': field, 'filename': fn}

    if name == 'list_my_artworks':
        if user.role not in ('artiste', 'galerie'):
            return {'error': 'Réservé aux artistes et galeries.'}
        return {
            'ok': True,
            'artworks': [
                {
                    'id': a.id,
                    'title': a.title,
                    'price': float(a.price) if a.price else None,
                    'status': a.status,
                    'has_image': bool(a.image),
                }
                for a in user.artworks
            ],
        }

    if name == 'add_artwork':
        if user.role not in ('artiste', 'galerie'):
            return {'error': 'Réservé aux artistes et galeries.'}
        from .entitlements import can_publish_artwork
        ok, err = can_publish_artwork(user)
        if not ok:
            return {'error': err}
        title = (args.get('title') or 'Sans titre').strip()[:140]
        a = Artwork(title=title, user_id=user.id, status='dispo', created_at=datetime.utcnow())
        for f in ('description', 'medium', 'dimensions', 'year', 'discipline'):
            if args.get(f):
                setattr(a, f, str(args[f]).strip()[:2000 if f == 'description' else 120])
        if args.get('price') is not None:
            try:
                a.price = float(args['price'])
            except (TypeError, ValueError):
                pass
        if args.get('series_id'):
            s = Series.query.filter_by(id=int(args['series_id']), user_id=user.id).first()
            if s:
                a.series_id = s.id
        fn = _resolve_image(args, ctx)
        if fn:
            a.image = fn
        db.session.add(a)
        db.session.commit()
        _side(ctx, {'type': 'reload'})
        return {'ok': True, 'artwork_id': a.id, 'title': a.title, 'url': f'/artwork/{a.id}'}

    if name == 'update_artwork':
        aid = int(args.get('artwork_id') or 0)
        a = Artwork.query.filter_by(id=aid, user_id=user.id).first()
        if not a:
            return {'error': 'Œuvre introuvable ou non autorisée.'}
        for f in ('title', 'description', 'medium', 'dimensions', 'year', 'discipline', 'status'):
            if args.get(f) is not None:
                setattr(a, f, str(args[f]).strip())
        if args.get('price') is not None:
            try:
                a.price = float(args['price'])
            except (TypeError, ValueError):
                pass
        if args.get('series_id') is not None:
            sid = int(args['series_id'])
            if sid == 0:
                a.series_id = None
            else:
                s = Series.query.filter_by(id=sid, user_id=user.id).first()
                if s:
                    a.series_id = s.id
        db.session.commit()
        _side(ctx, {'type': 'reload'})
        return {'ok': True, 'artwork_id': a.id}

    if name == 'set_artwork_image':
        aid = int(args.get('artwork_id') or 0)
        a = Artwork.query.filter_by(id=aid, user_id=user.id).first()
        if not a:
            return {'error': 'Œuvre introuvable.'}
        fn = _resolve_image(args, ctx)
        if not fn:
            return {'error': 'Joignez une image via 📎 ou fournissez image_filename.'}
        a.image = fn
        db.session.commit()
        _side(ctx, {'type': 'reload'})
        return {'ok': True, 'artwork_id': a.id, 'filename': fn}

    if name == 'delete_artwork':
        aid = int(args.get('artwork_id') or 0)
        a = Artwork.query.filter_by(id=aid, user_id=user.id).first()
        if not a:
            return {'error': 'Œuvre introuvable.'}
        db.session.delete(a)
        db.session.commit()
        _side(ctx, {'type': 'reload'})
        return {'ok': True, 'deleted_id': aid}

    if name == 'list_my_series':
        return {
            'ok': True,
            'series': [{'id': s.id, 'name': s.name, 'year': s.year} for s in user.series],
        }

    if name == 'add_series':
        name_s = (args.get('name') or '').strip()
        if not name_s:
            return {'error': 'Nom de série requis.'}
        s = Series(name=name_s[:140], user_id=user.id)
        if args.get('description'):
            s.description = str(args['description'])[:2000]
        if args.get('year'):
            s.year = str(args['year'])[:8]
        db.session.add(s)
        db.session.commit()
        return {'ok': True, 'series_id': s.id, 'name': s.name}

    if name == 'update_series':
        sid = int(args.get('series_id') or 0)
        s = Series.query.filter_by(id=sid, user_id=user.id).first()
        if not s:
            return {'error': 'Série introuvable.'}
        for f in ('name', 'description', 'year'):
            if args.get(f) is not None:
                setattr(s, f, str(args[f]).strip())
        db.session.commit()
        return {'ok': True, 'series_id': s.id}

    if name == 'delete_series':
        sid = int(args.get('series_id') or 0)
        s = Series.query.filter_by(id=sid, user_id=user.id).first()
        if not s:
            return {'error': 'Série introuvable.'}
        for a in s.artworks:
            a.series_id = None
        db.session.delete(s)
        db.session.commit()
        return {'ok': True, 'deleted_id': sid}

    if name == 'generate_curatorial_note':
        from .curatorial import refresh_curatorial_note
        note, err = refresh_curatorial_note(user, commit=True)
        if err:
            return {'error': err}
        _side(ctx, {'type': 'reload'})
        return {'ok': True, 'note_preview': (note or '')[:400]}

    if name == 'get_subscription_status':
        from .entitlements import effective_plan, user_entitlements
        from .subscriptions import plan_for_role, price_label
        slug = effective_plan(user)
        plan = plan_for_role(user.role or 'collectionneur', slug)
        ent = user_entitlements(user)
        return {
            'ok': True,
            'plan': slug,
            'plan_name': plan['name'] if plan else slug,
            'price': price_label(plan) if plan else '',
            'status': user.subscription_status,
            'entitlements': {k: v for k, v in ent.items() if isinstance(v, (bool, int, str, type(None)))},
        }

    if name == 'list_available_plans':
        from .subscriptions import plans_for_role, price_label
        role = user.role or 'collectionneur'
        return {
            'ok': True,
            'plans': [
                {'slug': p['slug'], 'name': p['name'], 'price': price_label(p)}
                for p in plans_for_role(role)
            ],
        }

    if name == 'request_subscription_checkout':
        from .subscriptions import normalize_plan
        slug = normalize_plan(user.role or 'collectionneur', args.get('plan_slug') or 'free')
        from . import billing
        url = billing.create_checkout_session(
            user, slug,
            success_url=url_for('main.subscription_success', _external=True),
            cancel_url=url_for('main.subscription', _external=True),
        )
        if url:
            _side(ctx, {'type': 'redirect', 'url': url})
            return {'ok': True, 'checkout_url': url}
        if current_app.config.get('STRIPE_DEMO_MODE'):
            billing.demo_activate_plan(user, slug)
            db.session.commit()
            _side(ctx, {'type': 'reload'})
            return {'ok': True, 'demo_activated': slug}
        return {'error': 'Paiement indisponible — configurez Stripe ou activez le mode démo.'}

    if name == 'toggle_price_alert':
        if user.role != 'collectionneur':
            return {'error': 'Réservé aux collectionneurs.'}
        from .entitlements import user_entitlements
        if not user_entitlements(user).get('price_alerts'):
            return {'error': 'Alertes prix disponibles avec la formule Membre ou Patron.'}
        aid = int(args.get('artwork_id') or 0)
        a = Artwork.query.get(aid)
        if not a:
            return {'error': 'Œuvre introuvable.'}
        existing = PriceAlert.query.filter_by(user_id=user.id, artwork_id=aid).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
            return {'ok': True, 'active': False}
        db.session.add(PriceAlert(user_id=user.id, artwork_id=aid, created_at=datetime.utcnow()))
        db.session.commit()
        return {'ok': True, 'active': True}

    if name == 'list_gallery_artists':
        if user.role != 'galerie':
            return {'error': 'Réservé aux galeries.'}
        rows = GalleryArtist.query.filter_by(gallery_id=user.id).all()
        return {
            'ok': True,
            'artists': [{'id': g.id, 'name': g.name, 'discipline': g.discipline} for g in rows],
        }

    if name == 'add_gallery_artist':
        if user.role != 'galerie':
            return {'error': 'Réservé aux galeries.'}
        from .entitlements import user_entitlements
        ent = user_entitlements(user)
        limit = ent.get('gallery_artist_limit') or 0
        count = GalleryArtist.query.filter_by(gallery_id=user.id).count()
        if limit and count >= limit:
            return {'error': f'Limite de {limit} artistes atteinte.'}
        nm = (args.get('name') or '').strip()
        if not nm:
            return {'error': 'Nom artiste requis.'}
        ga = GalleryArtist(gallery_id=user.id, name=nm[:120], discipline=(args.get('discipline') or '')[:120])
        db.session.add(ga)
        db.session.commit()
        _side(ctx, {'type': 'reload'})
        return {'ok': True, 'id': ga.id, 'name': ga.name}

    if name == 'delete_gallery_artist':
        if user.role != 'galerie':
            return {'error': 'Réservé aux galeries.'}
        gid = int(args.get('gallery_artist_id') or 0)
        ga = GalleryArtist.query.filter_by(id=gid, gallery_id=user.id).first()
        if not ga:
            return {'error': 'Artiste introuvable.'}
        db.session.delete(ga)
        db.session.commit()
        _side(ctx, {'type': 'reload'})
        return {'ok': True}

    if name == 'admin_search_users':
        from .crm.auth import is_staff_user
        if not is_staff_user(user):
            return {'error': 'Accès staff requis.'}
        q = (args.get('query') or '').strip().lower()
        limit = min(int(args.get('limit') or 10), 20)
        rows = User.query.limit(200).all()
        if q:
            rows = [
                u for u in rows
                if q in (u.email or '').lower() or q in (u.username or '').lower()
            ]
        return {
            'ok': True,
            'users': [
                {'id': u.id, 'username': u.username, 'email': u.email, 'role': u.role}
                for u in rows[:limit]
            ],
        }

    return {'error': f'Outil inconnu : {name}'}


def run_tool_calls(tool_calls: list, ctx: dict) -> list[dict]:
    """Exécute les tool_calls Mistral et renvoie les messages tool."""
    out = []
    for i, tc in enumerate(tool_calls):
        fn = tc.get('function') or {}
        name = fn.get('name') or ''
        raw_args = fn.get('arguments') or '{}'
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
        except json.JSONDecodeError:
            args = {}
        try:
            result = execute_tool(name, args, ctx)
        except Exception as exc:
            _log.exception('Aria tool %s failed', name)
            result = {'error': f'Échec technique sur {name}.', 'detail': str(exc)[:120]}
        out.append({
            'role': 'tool',
            'content': json.dumps(result, ensure_ascii=False),
            'tool_call_id': tc.get('id') or f'call_{i}',
            'name': name,
        })
    return out

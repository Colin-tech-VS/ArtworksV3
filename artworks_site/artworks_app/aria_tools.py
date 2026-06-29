"""Outils Aria — actions réelles sur le compte connecté (function calling)."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any

from flask import current_app, session, url_for
from flask_login import current_user, login_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from . import db
from .catalog import DISCIPLINES
from .models import Artwork, GalleryArtist, PriceAlert, Series, User

_MAX_AGENT_STEPS = 8
_PENDING_KEY = 'aria_pending_images'


def save_upload_file(file_storage) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    name = f'{uuid.uuid4().hex}_{filename}'
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    os.makedirs(upload_folder, exist_ok=True)
    file_storage.save(os.path.join(upload_folder, name))
    return name


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
        'Recherche artistes ou galeries publiques.',
        {
            'role': {'type': 'string', 'enum': ['artiste', 'galerie']},
            'query': {'type': 'string'},
            'limit': {'type': 'integer'},
        },
    ),
    _tool(
        'get_artwork',
        'Détail d\'une œuvre par ID.',
        {'artwork_id': {'type': 'integer'}},
        ['artwork_id'],
    ),
    _tool(
        'create_account',
        'Crée un compte Artworks et connecte l\'utilisateur. Visiteur NON connecté uniquement. Demander email + mot de passe (6+ car.).',
        {
            'role': {'type': 'string', 'enum': ['artiste', 'galerie', 'collectionneur']},
            'username': {'type': 'string'},
            'email': {'type': 'string'},
            'password': {'type': 'string'},
            'plan': {'type': 'string', 'description': 'Slug formule : free, portfolio, pro, membre, patron, premium…'},
        },
        ['role', 'username', 'email', 'password'],
    ),
]

TOOLS_AUTH = [
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


def _resolve_image(args: dict, ctx: dict) -> str | None:
    fn = (args.get('image_filename') or '').strip()
    if fn:
        return fn
    return pop_pending_image()


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
                    'discipline': a.discipline,
                    'artist': a.owner.name if a.owner else None,
                    'url': f'/artwork/{a.id}',
                }
                for a in rows[:limit]
            ],
        }

    if name == 'search_artists':
        role = (args.get('role') or 'artiste').strip()
        q = (args.get('query') or '').strip().lower()
        limit = min(int(args.get('limit') or 8), 12)
        from .entitlements import has_public_portfolio
        rows = User.query.filter_by(role=role).limit(100).all()
        rows = [u for u in rows if has_public_portfolio(u)]
        if q:
            rows = [
                u for u in rows
                if q in (u.display_name or '').lower() or q in (u.username or '').lower()
            ]
        return {
            'ok': True,
            'profiles': [
                {'id': u.id, 'name': u.name, 'role': u.role, 'url': f'/artist/{u.id}'}
                for u in rows[:limit]
            ],
        }

    if name == 'get_artwork':
        aid = int(args.get('artwork_id') or 0)
        a = Artwork.query.get(aid)
        if not a:
            return {'error': 'Œuvre introuvable.'}
        return {
            'ok': True,
            'artwork': {
                'id': a.id,
                'title': a.title,
                'description': (a.description or '')[:500],
                'price': float(a.price) if a.price else None,
                'discipline': a.discipline,
                'status': a.status,
                'artist_id': a.user_id,
                'artist': a.owner.name if a.owner else None,
                'url': f'/artwork/{a.id}',
            },
        }

    if name == 'create_account':
        if user:
            return {'error': 'Vous êtes déjà connecté. Déconnectez-vous pour créer un autre compte.'}
        role = (args.get('role') or 'collectionneur').strip()
        username = (args.get('username') or '').strip()
        email = (args.get('email') or '').strip().lower()
        password = args.get('password') or ''
        plan = (args.get('plan') or 'free').strip()
        if role not in ('artiste', 'galerie', 'collectionneur'):
            return {'error': 'Rôle invalide.'}
        if len(username) < 3 or not email or len(password) < 6:
            return {'error': 'username (3+), email et password (6+) requis.'}
        if User.query.filter_by(username=username).first():
            return {'error': 'Ce nom d\'utilisateur est déjà pris.'}
        if User.query.filter_by(email=email).first():
            return {'error': 'Cet email est déjà utilisé.'}
        from .subscriptions import normalize_plan, is_paid_plan
        from .auth import _apply_free_plan, _welcome_user

        slug = normalize_plan(role, plan)
        u = User(username=username, email=email, role=role, display_name=username)
        u.set_password(password)
        pending_paid = _apply_free_plan(u, role, slug)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        _welcome_user(u)
        ctx['user'] = u
        _side(ctx, {'type': 'login', 'user_id': u.id})
        _side(ctx, {'type': 'reload'})
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
            ok, err = can_publish_artwork(u)
            if ok:
                art = Artwork(title='Sans titre', image=pending_img, user_id=u.id, status='dispo')
                db.session.add(art)
                db.session.commit()
                return {'ok': True, 'user_id': u.id, 'first_artwork_id': art.id, 'logged_in': True}
        return {'ok': True, 'user_id': u.id, 'role': role, 'logged_in': True}

    if not user:
        return {'error': 'Connexion requise — connectez-vous ou créez un compte via create_account.'}

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
        result = execute_tool(name, args, ctx)
        out.append({
            'role': 'tool',
            'content': json.dumps(result, ensure_ascii=False),
            'tool_call_id': tc.get('id') or f'call_{i}',
            'name': name,
        })
    return out

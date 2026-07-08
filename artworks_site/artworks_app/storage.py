"""Stockage des uploads — local (dev) ou Supabase Storage (prod Scalingo).

Sur Scalingo le disque est éphémère : sans Supabase Storage, les images disparaissent à chaque déploiement.
"""
from __future__ import annotations

import logging
import mimetypes
import os
import uuid

import requests
from flask import current_app, url_for
from werkzeug.utils import secure_filename

_log = logging.getLogger(__name__)
_remote_exists: dict[str, bool] = {}


def remote_enabled() -> bool:
    return bool(
        current_app.config.get('SUPABASE_URL')
        and current_app.config.get('SUPABASE_SERVICE_KEY')
        and current_app.config.get('SUPABASE_STORAGE_BUCKET')
    )


def _upload_supabase(key: str, data: bytes, content_type: str) -> bool:
    base = current_app.config['SUPABASE_URL'].rstrip('/')
    bucket = current_app.config['SUPABASE_STORAGE_BUCKET']
    service_key = current_app.config['SUPABASE_SERVICE_KEY']
    url = f'{base}/storage/v1/object/{bucket}/{key}'
    try:
        r = requests.post(
            url,
            headers={
                'Authorization': f'Bearer {service_key}',
                'Content-Type': content_type,
                'x-upsert': 'true',
            },
            data=data,
            timeout=90,
        )
        if r.status_code in (200, 201):
            return True
        _log.error('Supabase upload failed %s: %s', r.status_code, r.text[:300])
    except requests.RequestException as exc:
        _log.error('Supabase upload error: %s', exc)
    return False


def _remote_object_ok(url: str) -> bool:
    """Vérifie qu'un objet Supabase existe (cache en mémoire par worker)."""
    if url in _remote_exists:
        return _remote_exists[url]
    ok = False
    try:
        r = requests.head(url, timeout=3, allow_redirects=True)
        ok = r.status_code == 200
        if not ok:
            # Certains endpoints Supabase répondent mal au HEAD
            r = requests.get(url, stream=True, timeout=3, allow_redirects=True)
            ok = r.status_code == 200
            r.close()
    except requests.RequestException as exc:
        _log.debug('remote image check failed %s: %s', url[:80], exc)
    _remote_exists[url] = ok
    if len(_remote_exists) > 400:
        _remote_exists.clear()
    return ok


def _supabase_public_url(key: str) -> str:
    base = current_app.config['SUPABASE_URL'].rstrip('/')
    bucket = current_app.config['SUPABASE_STORAGE_BUCKET']
    return f'{base}/storage/v1/object/public/{bucket}/{key}'


def _local_upload_url(key: str) -> str | None:
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if upload_folder and os.path.isfile(os.path.join(upload_folder, key)):
        return url_for('static', filename=f'uploads/{key}')
    return None


def save_upload(file_storage) -> str | None:
    """Enregistre un fichier uploadé. Retourne la clé stockée en base (nom de fichier)."""
    if not file_storage or not getattr(file_storage, 'filename', None):
        return None
    filename = secure_filename(file_storage.filename)
    if not filename:
        return None
    key = f'{uuid.uuid4().hex}_{filename}'
    data = file_storage.read()
    if not data:
        return None
    content_type = (
        getattr(file_storage, 'content_type', None)
        or mimetypes.guess_type(filename)[0]
        or 'application/octet-stream'
    )

    if remote_enabled():
        if _upload_supabase(key, data, content_type):
            return key
        _log.warning('Supabase upload failed — fallback disque local pour %s', key)

    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        return None
    os.makedirs(upload_folder, exist_ok=True)
    path = os.path.join(upload_folder, key)
    with open(path, 'wb') as fh:
        fh.write(data)
    return key


def normalize_image_ref(value: str | None) -> str | None:
    """Normalise une référence image (clé, chemin demo, URL legacy) pour stockage/résolution."""
    if not value:
        return None
    value = str(value).strip()
    if not value:
        return None
    if value.startswith('http://') or value.startswith('https://'):
        # URLs V2 (render/image) — conserver l'URL complète telle quelle
        if '/storage/v1/render/image/public/' in value:
            return value
        marker = '/storage/v1/object/public/'
        if marker in value:
            rest = value.split(marker, 1)[1]
            if '/' in rest:
                return rest.split('/', 1)[1].split('?')[0]
        for prefix in ('/static/uploads/', '/uploads/'):
            if prefix in value:
                return value.split(prefix, 1)[1].split('?')[0]
        return value
    if value.startswith('/static/uploads/'):
        return value.replace('/static/uploads/', '', 1).split('?')[0]
    if value.startswith('uploads/'):
        return value.replace('uploads/', '', 1).split('?')[0]
    return value.split('?')[0]


def public_url(value: str | None) -> str | None:
    """URL publique d'une image (Supabase, static demo, ou /static/uploads/)."""
    if not value:
        return None
    value = str(value).strip()
    if value.startswith('http://') or value.startswith('https://'):
        # URL V2 render ou externe déjà valide
        if '/storage/v1/render/image/public/' in value:
            return value
        key = normalize_image_ref(value)
        if key and key != value:
            return public_url(key)
        if _remote_object_ok(value):
            return value
        return None
    if value.startswith('/static/uploads/'):
        value = value.replace('/static/uploads/', '', 1)
    elif value.startswith('uploads/'):
        value = value.replace('uploads/', '', 1)
    if '/' in value and not value.startswith('uploads/'):
        return url_for('static', filename=value)
    key = value.split('/')[-1] if '/' in value else value
    if remote_enabled():
        remote = _supabase_public_url(key)
        if _remote_object_ok(remote):
            return remote
        local = _local_upload_url(key)
        if local:
            return local
        return None
    local = _local_upload_url(key)
    if local:
        return local
    return url_for('static', filename=f'uploads/{key}')


def img_resolve_config() -> dict:
    """Config JS pour résoudre les clés images côté client (aperçu live)."""
    if remote_enabled():
        base = current_app.config['SUPABASE_URL'].rstrip('/')
        bucket = current_app.config['SUPABASE_STORAGE_BUCKET']
        return {
            'uploadBase': f'{base}/storage/v1/object/public/{bucket}/',
            'staticPrefix': '/static/',
        }
    return {'uploadBase': '/static/uploads/', 'staticPrefix': '/static/'}


def absolute_url(value: str | None) -> str | None:
    """URL absolue (emails, Aria, réseaux sociaux)."""
    u = public_url(value)
    if not u:
        return None
    if u.startswith('http://') or u.startswith('https://'):
        return u
    site = (current_app.config.get('SITE_URL') or '').rstrip('/')
    return f'{site}{u}' if site else u

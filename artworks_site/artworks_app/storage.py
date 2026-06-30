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


def public_url(value: str | None) -> str | None:
    """URL publique d'une image (Supabase ou /static/uploads/)."""
    if not value:
        return None
    value = str(value).strip()
    if value.startswith('http://') or value.startswith('https://'):
        return value
    if '/' in value and not value.startswith('uploads/'):
        return url_for('static', filename=value)
    key = value.split('/')[-1] if '/' in value else value
    if remote_enabled():
        base = current_app.config['SUPABASE_URL'].rstrip('/')
        bucket = current_app.config['SUPABASE_STORAGE_BUCKET']
        return f'{base}/storage/v1/object/public/{bucket}/{key}'
    return url_for('static', filename=f'uploads/{key}')


def absolute_url(value: str | None) -> str | None:
    """URL absolue (emails, Aria, réseaux sociaux)."""
    u = public_url(value)
    if not u:
        return None
    if u.startswith('http://') or u.startswith('https://'):
        return u
    site = (current_app.config.get('SITE_URL') or '').rstrip('/')
    return f'{site}{u}' if site else u

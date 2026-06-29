"""Plateformes sociales — port V2 (Facebook, Instagram, DeviantArt, Pinterest)."""
from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from flask import current_app

from . import oauth as oauth_helpers
from . import tokens as token_store

log = logging.getLogger(__name__)


def _clean_env(raw: str | None) -> str:
    val = (raw or '').strip().strip('\r\n').strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        val = val[1:-1].strip()
    return val


def _env_first(*names: str) -> str:
    for name in names:
        val = _clean_env(os.environ.get(name) or current_app.config.get(name, ''))
        if val:
            return val
    return ''


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _http_get(url: str, *, headers: dict | None = None, timeout: int = 20) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def _http_post_form(url: str, params: dict, *, headers: dict | None = None, timeout: int = 20) -> dict:
    body = urllib.parse.urlencode(params).encode('utf-8')
    h = {'Content-Type': 'application/x-www-form-urlencoded'}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='replace')
        try:
            return json.loads(raw)
        except Exception:
            return {'error': f'http_{e.code}', 'error_description': raw[:500]}


def _http_post_json(url: str, payload: dict, *, headers: dict | None = None, timeout: int = 20) -> dict:
    body = json.dumps(payload).encode('utf-8')
    h = {'Content-Type': 'application/json'}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def _oauth_raise_token_errors(data: dict, *, label: str = 'OAuth') -> None:
    if not isinstance(data, dict):
        raise ValueError(f'{label} : réponse invalide')
    if data.get('error'):
        desc = data.get('error_description') or data.get('error')
        raise ValueError(f'{label} : {desc}')
    if not data.get('access_token'):
        raise ValueError(f'{label} : jeton absent')


class Facebook:
    GRAPH = 'https://graph.facebook.com/v19.0'

    @staticmethod
    def token() -> str:
        return _env_first('FACEBOOK_PAGE_ACCESS_TOKEN', 'FB_PAGE_TOKEN', 'FACEBOOK_PAGE_TOKEN')

    @staticmethod
    def page_id() -> str:
        return _env_first('FACEBOOK_PAGE_ID', 'FB_PAGE_ID')

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.token() and cls.page_id())

    @classmethod
    def status(cls) -> dict:
        if not cls.is_configured():
            return {'configured': False}
        try:
            data = _http_get(
                f'{cls.GRAPH}/{cls.page_id()}?fields=name,fan_count,id&access_token={cls.token()}'
            )
            return {
                'configured': True,
                'page_name': data.get('name'),
                'page_id': data.get('id'),
                'fan_count': data.get('fan_count'),
            }
        except urllib.error.HTTPError as e:
            return {'configured': True, 'error': e.read().decode('utf-8', 'replace')[:200]}
        except Exception as e:
            return {'configured': True, 'error': str(e)[:200]}

    @classmethod
    def publish(cls, *, message: str, link: str = '', image_url: str = '') -> dict:
        if not cls.is_configured():
            return {'ok': False, 'error': 'Facebook non configuré'}
        try:
            if image_url:
                params = {'url': image_url, 'caption': message, 'access_token': cls.token()}
                if link:
                    params['link'] = link
                res = _http_post_form(f'{cls.GRAPH}/{cls.page_id()}/photos', params)
            else:
                params = {'message': message, 'access_token': cls.token()}
                if link:
                    params['link'] = link
                res = _http_post_form(f'{cls.GRAPH}/{cls.page_id()}/feed', params)
            if res.get('error'):
                return {'ok': False, 'error': str(res.get('error'))[:300]}
            post_id = str(res.get('post_id') or res.get('id') or '')
            return {'ok': True, 'post_id': post_id}
        except urllib.error.HTTPError as e:
            return {'ok': False, 'error': f'HTTP {e.code} {e.read().decode("utf-8", "replace")[:300]}'}
        except Exception as e:
            return {'ok': False, 'error': str(e)[:200]}


class Instagram:
    GRAPH = 'https://graph.facebook.com/v19.0'

    @staticmethod
    def token() -> str:
        return _env_first('INSTAGRAM_ACCESS_TOKEN') or Facebook.token()

    @staticmethod
    def user_id() -> str:
        return _env_first('INSTAGRAM_USER_ID', 'IG_BUSINESS_ACCOUNT_ID', 'IG_ACCOUNT_ID')

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.token() and cls.user_id())

    @classmethod
    def status(cls) -> dict:
        if not cls.is_configured():
            return {'configured': False}
        try:
            data = _http_get(
                f'{cls.GRAPH}/{cls.user_id()}?fields=username,name,followers_count,media_count&access_token={cls.token()}'
            )
            return {
                'configured': True,
                'username': data.get('username'),
                'name': data.get('name'),
                'followers_count': data.get('followers_count'),
                'media_count': data.get('media_count'),
            }
        except urllib.error.HTTPError as e:
            return {'configured': True, 'error': e.read().decode('utf-8', 'replace')[:200]}
        except Exception as e:
            return {'configured': True, 'error': str(e)[:200]}

    @classmethod
    def publish(cls, *, caption: str, image_url: str) -> dict:
        if not cls.is_configured():
            return {'ok': False, 'error': 'Instagram non configuré'}
        if not image_url:
            return {'ok': False, 'error': 'Image URL requise'}
        if not image_url.startswith('https://'):
            return {'ok': False, 'error': 'Instagram exige HTTPS'}
        try:
            res = _http_post_form(f'{cls.GRAPH}/{cls.user_id()}/media', {
                'image_url': image_url,
                'caption': caption[:2200],
                'access_token': cls.token(),
            })
            creation_id = res.get('id')
            if not creation_id:
                return {'ok': False, 'error': f'Étape 1 : {res}'}
            res2 = _http_post_form(f'{cls.GRAPH}/{cls.user_id()}/media_publish', {
                'creation_id': creation_id,
                'access_token': cls.token(),
            })
            if res2.get('error'):
                return {'ok': False, 'error': str(res2.get('error'))[:300]}
            return {'ok': True, 'post_id': str(res2.get('id') or '')}
        except urllib.error.HTTPError as e:
            return {'ok': False, 'error': f'HTTP {e.code} {e.read().decode("utf-8", "replace")[:300]}'}
        except Exception as e:
            return {'ok': False, 'error': str(e)[:200]}


class DeviantArt:
    AUTH_URL = 'https://www.deviantart.com/oauth2/authorize'
    TOKEN_URL = 'https://www.deviantart.com/oauth2/token'
    API = 'https://www.deviantart.com/api/v1/oauth2'
    SCOPES = 'basic browse stash gallery'

    @staticmethod
    def client_id() -> str:
        return _env_first('DEVIANTART_CLIENT_ID')

    @staticmethod
    def client_secret() -> str:
        return _env_first('DEVIANTART_CLIENT_SECRET')

    @classmethod
    def redirect_uri(cls) -> str:
        return oauth_helpers.redirect_uri('deviantart')

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.client_id() and cls.client_secret())

    @classmethod
    def begin_authorize(cls) -> tuple[str, str, str]:
        state = oauth_helpers.oauth_state_make('deviantart')
        verifier = oauth_helpers.pkce_verifier()
        challenge = oauth_helpers.pkce_challenge(verifier)
        params = urllib.parse.urlencode({
            'client_id': cls.client_id(),
            'redirect_uri': cls.redirect_uri(),
            'scope': cls.SCOPES,
            'response_type': 'code',
            'state': state,
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
        })
        return f'{cls.AUTH_URL}?{params}', state, verifier

    @classmethod
    def exchange_code(cls, code: str, *, code_verifier: str | None = None) -> dict:
        params = {
            'client_id': cls.client_id(),
            'client_secret': cls.client_secret(),
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': cls.redirect_uri(),
        }
        if code_verifier:
            params['code_verifier'] = code_verifier
        data = _http_post_form(cls.TOKEN_URL, params)
        _oauth_raise_token_errors(data, label='DeviantArt')
        return data

    @classmethod
    def save_tokens(cls, tok: dict) -> None:
        expires_in = int(tok.get('expires_in', 3600))
        expires_at = _iso(_now_utc() + timedelta(seconds=expires_in - 60))
        username = ''
        try:
            who = _http_get(f'{cls.API}/user/whoami?access_token={tok["access_token"]}')
            username = who.get('username', '')
        except Exception:
            pass
        token_store.save_token(
            'deviantart',
            access_token=tok['access_token'],
            refresh_token=tok.get('refresh_token', ''),
            token_expires_at=expires_at,
            account_username=username,
            scopes=cls.SCOPES,
        )

    @classmethod
    def get_valid_token(cls) -> str:
        rec = token_store.get_token('deviantart')
        if not rec:
            return ''
        if rec.get('token_expires_at'):
            try:
                exp = datetime.fromisoformat(rec['token_expires_at'])
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp - _now_utc() < timedelta(minutes=5) and rec.get('refresh_token'):
                    new = _http_post_form(cls.TOKEN_URL, {
                        'client_id': cls.client_id(),
                        'client_secret': cls.client_secret(),
                        'grant_type': 'refresh_token',
                        'refresh_token': rec['refresh_token'],
                    })
                    cls.save_tokens(new)
                    return new['access_token']
            except Exception:
                pass
        return rec['access_token']

    @classmethod
    def is_connected(cls) -> bool:
        return token_store.get_token('deviantart') is not None

    @classmethod
    def status(cls) -> dict:
        rec = token_store.get_token('deviantart')
        if not rec:
            return {'connected': False, 'configured': cls.is_configured()}
        return {'connected': True, 'configured': True, 'username': rec.get('account_username')}

    @classmethod
    def disconnect(cls) -> None:
        token_store.delete_token('deviantart')

    @classmethod
    def fetch_deviation_stats(cls, deviation_id: str) -> dict | None:
        token = cls.get_valid_token()
        if not token or not deviation_id:
            return None
        try:
            data = _http_get(
                f'{cls.API}/deviation/{deviation_id}?access_token={token}'
            )
            return {
                'views': int(data.get('stats', {}).get('views') or data.get('views') or 0),
                'favorites': int(data.get('stats', {}).get('favourites') or data.get('favourites') or 0),
                'url': data.get('url') or '',
            }
        except Exception:
            log.exception('DeviantArt stats fetch failed for %s', deviation_id)
            return None

    @classmethod
    def publish(cls, *, title: str, description: str, image_url: str,
                tags: list[str] | None = None) -> dict:
        token = cls.get_valid_token()
        if not token:
            return {'ok': False, 'error': 'DeviantArt non connecté'}
        if not image_url:
            return {'ok': False, 'error': 'Image requise'}
        try:
            img_bytes = urllib.request.urlopen(image_url, timeout=30).read()
            boundary = '----artworks' + secrets.token_hex(8)
            parts: list[bytes] = []

            def field(name: str, value: str) -> None:
                parts.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode('utf-8')
                )

            field('title', title[:50])
            field('artist_description', description[:500])
            for t in (tags or [])[:10]:
                field('tags[]', t)
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="art.jpg"\r\n'
                f'Content-Type: image/jpeg\r\n\r\n'.encode('utf-8')
            )
            parts.append(img_bytes)
            parts.append(f'\r\n--{boundary}--\r\n'.encode('utf-8'))
            body = b''.join(parts)
            req = urllib.request.Request(
                f'{cls.API}/stash/submit?access_token={token}',
                data=body,
                headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                stash = json.loads(r.read().decode('utf-8'))
            itemid = stash.get('itemid')
            if not itemid:
                return {'ok': False, 'error': f'stash failed: {stash}'}
            pub = _http_post_form(
                f'{cls.API}/stash/publish?access_token={token}',
                {
                    'itemid': itemid,
                    'is_mature': 'false',
                    'agree_submission': 'true',
                    'agree_tos': 'true',
                },
            )
            deviationid = pub.get('deviationid')
            return {
                'ok': True,
                'post_id': str(deviationid or ''),
                'url': pub.get('url', ''),
            }
        except urllib.error.HTTPError as e:
            return {'ok': False, 'error': f'HTTP {e.code} {e.read().decode("utf-8", "replace")[:300]}'}
        except Exception as e:
            return {'ok': False, 'error': str(e)[:200]}


class Pinterest:
    AUTH_URL = 'https://www.pinterest.com/oauth/'
    TOKEN_URL = 'https://api.pinterest.com/v5/oauth/token'
    API = 'https://api.pinterest.com/v5'
    SCOPES = 'user_accounts:read,boards:read,boards:write,pins:read,pins:write'

    @staticmethod
    def client_id() -> str:
        return _env_first('PINTEREST_CLIENT_ID')

    @staticmethod
    def client_secret() -> str:
        return _env_first('PINTEREST_CLIENT_SECRET')

    @classmethod
    def redirect_uri(cls) -> str:
        return oauth_helpers.redirect_uri('pinterest')

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.client_id() and cls.client_secret())

    @classmethod
    def authorize_url(cls, state: str | None = None) -> str:
        st = state or oauth_helpers.oauth_state_make('pinterest')
        params = urllib.parse.urlencode({
            'client_id': cls.client_id(),
            'redirect_uri': cls.redirect_uri(),
            'response_type': 'code',
            'scope': cls.SCOPES,
            'state': st,
        })
        return f'{cls.AUTH_URL}?{params}'

    @classmethod
    def exchange_code(cls, code: str) -> dict:
        creds = base64.b64encode(f'{cls.client_id()}:{cls.client_secret()}'.encode()).decode()
        return _http_post_form(cls.TOKEN_URL, {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': cls.redirect_uri(),
        }, headers={'Authorization': f'Basic {creds}'})

    @classmethod
    def save_tokens(cls, tok: dict) -> None:
        expires_in = int(tok.get('expires_in', 2592000))
        expires_at = _iso(_now_utc() + timedelta(seconds=expires_in - 60))
        username = ''
        try:
            who = _http_get(
                f'{cls.API}/user_account',
                headers={'Authorization': f'Bearer {tok["access_token"]}'},
            )
            username = who.get('username', '')
        except Exception:
            pass
        token_store.save_token(
            'pinterest',
            access_token=tok['access_token'],
            refresh_token=tok.get('refresh_token', ''),
            token_expires_at=expires_at,
            account_username=username,
            scopes=cls.SCOPES,
        )

    @classmethod
    def get_valid_token(cls) -> str:
        rec = token_store.get_token('pinterest')
        if not rec:
            return ''
        if rec.get('token_expires_at'):
            try:
                exp = datetime.fromisoformat(rec['token_expires_at'])
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp - _now_utc() < timedelta(minutes=5) and rec.get('refresh_token'):
                    creds = base64.b64encode(
                        f'{cls.client_id()}:{cls.client_secret()}'.encode()
                    ).decode()
                    new = _http_post_form(cls.TOKEN_URL, {
                        'grant_type': 'refresh_token',
                        'refresh_token': rec['refresh_token'],
                        'scope': cls.SCOPES,
                    }, headers={'Authorization': f'Basic {creds}'})
                    cls.save_tokens(new)
                    return new['access_token']
            except Exception:
                pass
        return rec['access_token']

    @classmethod
    def is_connected(cls) -> bool:
        return token_store.get_token('pinterest') is not None

    @classmethod
    def status(cls) -> dict:
        rec = token_store.get_token('pinterest')
        if not rec:
            return {'connected': False, 'configured': cls.is_configured()}
        return {'connected': True, 'configured': True, 'username': rec.get('account_username')}

    @classmethod
    def disconnect(cls) -> None:
        token_store.delete_token('pinterest')

    @classmethod
    def list_boards(cls) -> list[dict]:
        token = cls.get_valid_token()
        if not token:
            return []
        try:
            data = _http_get(
                f'{cls.API}/boards',
                headers={'Authorization': f'Bearer {token}'},
            )
            return [{'id': b['id'], 'name': b['name']} for b in data.get('items', [])]
        except Exception:
            return []

    @classmethod
    def publish(cls, *, board_id: str, title: str, description: str,
                image_url: str, link: str = '') -> dict:
        token = cls.get_valid_token()
        if not token:
            return {'ok': False, 'error': 'Pinterest non connecté'}
        try:
            res = _http_post_json(f'{cls.API}/pins', {
                'board_id': board_id,
                'title': title[:100],
                'description': description[:500],
                'link': link,
                'media_source': {'source_type': 'image_url', 'url': image_url},
            }, headers={'Authorization': f'Bearer {token}'})
            return {'ok': True, 'post_id': res.get('id', ''), 'url': res.get('link', '')}
        except urllib.error.HTTPError as e:
            return {'ok': False, 'error': f'HTTP {e.code} {e.read().decode("utf-8", "replace")[:300]}'}
        except Exception as e:
            return {'ok': False, 'error': str(e)[:200]}


def platform_status() -> dict:
    return {
        'facebook': Facebook.status(),
        'instagram': Instagram.status(),
        'deviantart': DeviantArt.status(),
        'pinterest': Pinterest.status(),
    }

"""Auto-publication œuvres + logging (port V2 auto_social)."""
from __future__ import annotations

import logging
import threading
from datetime import datetime

from flask import current_app, url_for

from .. import db
from ..models import Artwork, SocialPublishLog, User
from .platforms import DeviantArt, Facebook, Instagram, Pinterest

log = logging.getLogger(__name__)


def _absolute_image_url(artwork: Artwork) -> str:
    from ..storage import absolute_url
    return absolute_url(artwork.image) or ''


def _portfolio_url(user: User) -> str:
    site = (current_app.config.get('SITE_URL') or '').rstrip('/')
    return f'{site}{url_for("main.artist", artist_id=user.id)}'


def _caption(user: User, artwork: Artwork, portfolio_url: str) -> str:
    title = (artwork.title or 'Sans titre').strip()
    technique = (artwork.technique or artwork.medium or '').strip()
    dim = (artwork.dimensions or '').strip()
    artist_name = user.name
    parts = [f'🎨 {title}']
    meta = ' · '.join(p for p in (technique, dim) if p)
    if meta:
        parts.append(meta)
    if artist_name:
        parts.append(f'par {artist_name}')
    parts.append('')
    parts.append(f'👀 Découvrir : {portfolio_url}')
    return '\n'.join(parts)


def log_publish(
    *,
    platform: str,
    post_id: str = '',
    artwork_id: int | None = None,
    social_post_id: int | None = None,
    user_id: int | None = None,
    content_preview: str = '',
    image_url: str = '',
    destination_url: str = '',
    status: str = 'published',
    error: str = '',
) -> None:
    entry = SocialPublishLog(
        platform=platform,
        post_id=post_id or None,
        artwork_id=artwork_id,
        social_post_id=social_post_id,
        user_id=user_id,
        content_preview=(content_preview or '')[:300],
        image_url=image_url or None,
        destination_url=destination_url or None,
        status=status,
        error_message=(error or '')[:500] or None,
    )
    db.session.add(entry)
    db.session.commit()


def publish_artwork_to_deviantart(artwork: Artwork, user: User) -> dict:
    """Publication DeviantArt synchrone — retourne {ok, post_id, url, error}."""
    image_url = _absolute_image_url(artwork)
    if not image_url:
        return {'ok': False, 'error': 'Pas d\'image'}
    if not DeviantArt.is_connected():
        return {'ok': False, 'error': 'DeviantArt non connecté'}
    portfolio_url = _portfolio_url(user)
    caption = _caption(user, artwork, portfolio_url)
    tags = [t for t in (artwork.discipline, artwork.style, artwork.medium) if t]
    r = DeviantArt.publish(
        title=(artwork.title or 'Œuvre')[:50],
        description=caption,
        image_url=image_url,
        tags=tags,
    )
    if r.get('ok'):
        artwork.deviantart_deviation_id = r.get('post_id') or artwork.deviantart_deviation_id
        artwork.deviantart_url = r.get('url') or artwork.deviantart_url
        artwork.social_published_at = datetime.utcnow()
        db.session.commit()
    log_publish(
        platform='deviantart',
        post_id=r.get('post_id', ''),
        artwork_id=artwork.id,
        user_id=user.id,
        content_preview=caption[:200],
        image_url=image_url,
        destination_url=portfolio_url,
        status='published' if r.get('ok') else 'failed',
        error=r.get('error', ''),
    )
    return r


def _do_publish_all(artwork: Artwork, user: User) -> dict:
    """Best-effort sur les 4 plateformes (comme V2)."""
    image_url = _absolute_image_url(artwork)
    portfolio_url = _portfolio_url(user)
    caption = _caption(user, artwork, portfolio_url)
    title = artwork.title or 'Œuvre'
    results: dict = {}

    if Facebook.is_configured():
        try:
            r = Facebook.publish(message=caption, link=portfolio_url, image_url=image_url)
            results['facebook'] = r
            log_publish(
                platform='facebook', post_id=r.get('post_id', ''), artwork_id=artwork.id,
                user_id=user.id, content_preview=caption[:200], image_url=image_url,
                destination_url=portfolio_url, status='published' if r.get('ok') else 'failed',
                error=r.get('error', ''),
            )
        except Exception as e:
            results['facebook'] = {'ok': False, 'error': str(e)[:200]}

    if Instagram.is_configured() and image_url.startswith('https://'):
        try:
            r = Instagram.publish(caption=caption, image_url=image_url)
            results['instagram'] = r
            log_publish(
                platform='instagram', post_id=r.get('post_id', ''), artwork_id=artwork.id,
                user_id=user.id, content_preview=caption[:200], image_url=image_url,
                destination_url=portfolio_url, status='published' if r.get('ok') else 'failed',
                error=r.get('error', ''),
            )
        except Exception as e:
            results['instagram'] = {'ok': False, 'error': str(e)[:200]}

    if DeviantArt.is_connected() and not artwork.deviantart_deviation_id:
        try:
            r = publish_artwork_to_deviantart(artwork, user)
            results['deviantart'] = r
        except Exception as e:
            results['deviantart'] = {'ok': False, 'error': str(e)[:200]}

    board_id = current_app.config.get('PINTEREST_DEFAULT_BOARD_ID', '')
    if board_id and Pinterest.is_connected() and image_url:
        try:
            r = Pinterest.publish(
                board_id=board_id, title=title[:100], description=caption[:500],
                image_url=image_url, link=portfolio_url,
            )
            results['pinterest'] = r
            if r.get('ok'):
                artwork.pinterest_pin_id = r.get('post_id') or artwork.pinterest_pin_id
                db.session.commit()
            log_publish(
                platform='pinterest', post_id=r.get('post_id', ''), artwork_id=artwork.id,
                user_id=user.id, content_preview=caption[:200], image_url=image_url,
                destination_url=portfolio_url, status='published' if r.get('ok') else 'failed',
                error=r.get('error', ''),
            )
        except Exception as e:
            results['pinterest'] = {'ok': False, 'error': str(e)[:200]}

    return results


def publish_artwork_async(artwork: Artwork, user: User) -> None:
    """Thread background — DeviantArt obligatoire, autres best-effort."""
    if not artwork or not user:
        return
    if user.role not in ('artiste', 'galerie'):
        return
    if not artwork.image:
        return

    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            try:
                a = Artwork.query.get(artwork.id)
                u = User.query.get(user.id)
                if not a or not u:
                    return
                res = _do_publish_all(a, u)
                ok_count = sum(1 for r in res.values() if r.get('ok'))
                log.info('Auto-publish artwork %s : %d/%d OK', a.id, ok_count, len(res))
            except Exception:
                log.exception('Auto-publish artwork %s crashed', artwork.id)

    threading.Thread(target=_run, daemon=True).start()

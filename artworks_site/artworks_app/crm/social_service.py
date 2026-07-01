"""Publication posts CRM vers les plateformes."""
from __future__ import annotations

import json
from datetime import datetime

from flask import current_app, url_for

from .. import db
from ..models import SocialPost
from ..social.platforms import DeviantArt, Facebook, Instagram, Pinterest
from ..social.publish import log_publish
from ..social.targeting import build_destination_url, pick_featured_artwork, resolve_target_users


def _absolute_upload(path: str) -> str:
    from ..storage import absolute_url
    return absolute_url(path) or ''


def resolve_post_image(post: SocialPost) -> str:
    if post.image_url:
        return post.image_url if post.image_url.startswith('http') else _absolute_upload(post.image_url)
    users = resolve_target_users(
        mode=post.target_mode,
        segment_id=post.segment_id,
        role=post.target_role,
        user_ids=post.target_user_ids,
    )
    for u in users:
        art = pick_featured_artwork(u)
        if art and art.image:
            return _absolute_upload(art.image)
    return ''


def resolve_post_destination(post: SocialPost) -> str:
    if post.destination_url:
        return post.destination_url
    site = (current_app.config.get('SITE_URL') or '').rstrip('/')
    users = resolve_target_users(
        mode=post.target_mode,
        segment_id=post.segment_id,
        role=post.target_role,
        user_ids=post.target_user_ids,
    )
    if len(users) == 1:
        return build_destination_url(users[0], site)
    return site + url_for('main.explorer')


def publish_social_post(post: SocialPost) -> dict:
    """Publie sur les plateformes cochées. Retourne {platform: result}."""
    platforms = post.platforms or []
    image_url = resolve_post_image(post)
    link = resolve_post_destination(post)
    results: dict = {}

    if 'facebook' in platforms:
        msg = (post.facebook_text or post.subject or '').strip()
        if link and link not in msg:
            msg = f'{msg}\n\n{link}'
        r = Facebook.publish(message=msg, link=link, image_url=image_url)
        results['facebook'] = r
        log_publish(
            platform='facebook', post_id=r.get('post_id', ''), social_post_id=post.id,
            content_preview=msg[:200], image_url=image_url, destination_url=link,
            status='published' if r.get('ok') else 'failed', error=r.get('error', ''),
        )

    if 'instagram' in platforms:
        cap = (post.instagram_text or post.subject or '').strip()
        r = Instagram.publish(caption=cap, image_url=image_url) if image_url else {'ok': False, 'error': 'Image requise'}
        results['instagram'] = r
        log_publish(
            platform='instagram', post_id=r.get('post_id', ''), social_post_id=post.id,
            content_preview=cap[:200], image_url=image_url, destination_url=link,
            status='published' if r.get('ok') else 'failed', error=r.get('error', ''),
        )

    if 'pinterest' in platforms:
        board = current_app.config.get('PINTEREST_DEFAULT_BOARD_ID', '')
        desc = (post.pinterest_text or post.facebook_text or post.subject or '')[:500]
        title = (post.subject or 'Artworks')[:100]
        r = Pinterest.publish(
            board_id=board, title=title, description=desc,
            image_url=image_url, link=link,
        ) if board and image_url else {'ok': False, 'error': 'Board ou image manquant'}
        results['pinterest'] = r
        log_publish(
            platform='pinterest', post_id=r.get('post_id', ''), social_post_id=post.id,
            content_preview=desc[:200], image_url=image_url, destination_url=link,
            status='published' if r.get('ok') else 'failed', error=r.get('error', ''),
        )

    if 'deviantart' in platforms:
        title = (post.deviantart_title or post.subject or '')[:50]
        desc = (post.deviantart_description or post.facebook_text or '')[:500]
        r = DeviantArt.publish(title=title, description=desc, image_url=image_url) if image_url else {'ok': False, 'error': 'Image requise'}
        results['deviantart'] = r
        log_publish(
            platform='deviantart', post_id=r.get('post_id', ''), social_post_id=post.id,
            content_preview=desc[:200], image_url=image_url, destination_url=link,
            status='published' if r.get('ok') else 'failed', error=r.get('error', ''),
        )

    ok = sum(1 for r in results.values() if r.get('ok'))
    post.publish_results_json = json.dumps(results)
    post.published_at = datetime.utcnow()
    post.status = 'published' if ok == len(results) and results else ('partial' if ok else 'failed')
    db.session.commit()
    return results


def target_preview_count(post: SocialPost) -> int:
    return len(resolve_target_users(
        mode=post.target_mode,
        segment_id=post.segment_id,
        role=post.target_role,
        user_ids=post.target_user_ids,
    ))

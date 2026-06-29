"""CRM — réseaux sociaux (posts, OAuth, stats)."""
from __future__ import annotations

import json
from datetime import datetime

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from .. import db
from ..models import SocialPost, SocialPublishLog, User
from ..social.ai import generate_social_post
from ..social.oauth import oauth_state_verify, pkce_clear_cookie, pkce_read_verifier, pkce_set_cookie
from ..social.platforms import DeviantArt, Facebook, Instagram, Pinterest, platform_status
from ..social.stats import sync_all_deviantart_stats
from ..social.targeting import resolve_target_users
from . import bp
from .auth import staff_required
from .forms import SocialAiForm, SocialPostForm
from .social_service import publish_social_post, resolve_post_destination, resolve_post_image, target_preview_count


def _segment_choices():
    from ..models import EmailSegment
    from .segments import segment_count
    choices = [(0, '— Choisir —')]
    for seg in EmailSegment.query.order_by(EmailSegment.name).all():
        n = segment_count(seg.filters)
        label = f'{seg.name} ({n})'
        if seg.is_system:
            label += ' · auto'
        choices.append((seg.id, label))
    return choices


def _client_choices():
    return [
        (u.id, f'{u.display_name or u.username} ({u.role})')
        for u in User.query.filter(User.role.in_(('artiste', 'galerie')), User.is_staff.is_(False))
        .order_by(User.display_name, User.username).all()
    ]


def _bind_social_form(form: SocialPostForm):
    form.segment_id.choices = _segment_choices()
    form.target_user_ids.choices = _client_choices()


def _platforms_from_form(form: SocialPostForm) -> list[str]:
    plats = []
    if form.platform_facebook.data:
        plats.append('facebook')
    if form.platform_instagram.data:
        plats.append('instagram')
    if form.platform_pinterest.data:
        plats.append('pinterest')
    if form.platform_deviantart.data:
        plats.append('deviantart')
    return plats or ['facebook', 'instagram']


def _post_from_form(form: SocialPostForm, post: SocialPost | None = None) -> SocialPost:
    p = post or SocialPost()
    p.name = form.name.data
    p.subject = form.subject.data
    p.keywords = form.keywords.data or ''
    p.tone = form.tone.data or 'inspirant'
    p.destination_url = (form.destination_url.data or '').strip() or None
    p.target_mode = form.target_mode.data or 'role'
    p.segment_id = form.segment_id.data or None if p.target_mode == 'segment' else None
    p.target_role = form.target_role.data if p.target_mode == 'role' else None
    p.target_user_ids = list(form.target_user_ids.data or []) if p.target_mode == 'users' else []
    p.platforms = _platforms_from_form(form)
    p.facebook_text = form.facebook_text.data or ''
    p.instagram_text = form.instagram_text.data or ''
    p.pinterest_text = form.pinterest_text.data or ''
    p.deviantart_title = form.deviantart_title.data or ''
    p.deviantart_description = form.deviantart_description.data or ''
    if not post:
        p.author_id = current_user.id
        db.session.add(p)
    return p


def _form_from_post(form: SocialPostForm, post: SocialPost):
    form.name.data = post.name
    form.subject.data = post.subject
    form.keywords.data = post.keywords
    form.tone.data = post.tone
    form.destination_url.data = post.destination_url or ''
    form.target_mode.data = post.target_mode or 'role'
    form.segment_id.data = post.segment_id or 0
    form.target_role.data = post.target_role or 'artiste'
    form.target_user_ids.data = post.target_user_ids
    plats = post.platforms or []
    form.platform_facebook.data = 'facebook' in plats
    form.platform_instagram.data = 'instagram' in plats
    form.platform_pinterest.data = 'pinterest' in plats
    form.platform_deviantart.data = 'deviantart' in plats
    form.facebook_text.data = post.facebook_text or ''
    form.instagram_text.data = post.instagram_text or ''
    form.pinterest_text.data = post.pinterest_text or ''
    form.deviantart_title.data = post.deviantart_title or ''
    form.deviantart_description.data = post.deviantart_description or ''


@bp.route('/social')
@staff_required
def social_index():
    sync_all_deviantart_stats()
    status = platform_status()
    posts = SocialPost.query.order_by(SocialPost.created_at.desc()).limit(20).all()
    logs = SocialPublishLog.query.order_by(SocialPublishLog.created_at.desc()).limit(30).all()
    return render_template(
        'crm/social_index.html',
        status=status,
        posts=posts,
        logs=logs,
        crm_active='social',
        da_redirect=DeviantArt.redirect_uri(),
        pt_redirect=Pinterest.redirect_uri(),
    )


@bp.route('/social/posts')
@staff_required
def social_posts_list():
    posts = SocialPost.query.order_by(SocialPost.created_at.desc()).all()
    return render_template('crm/social_posts.html', posts=posts, crm_active='social')


@bp.route('/social/posts/new', methods=['GET', 'POST'])
@bp.route('/social/posts/<int:post_id>/edit', methods=['GET', 'POST'])
@staff_required
def social_post_form(post_id=None):
    post = SocialPost.query.get(post_id) if post_id else None
    form = SocialPostForm()
    ai_form = SocialAiForm()
    _bind_social_form(form)
    publish_now = False

    if request.method == 'POST' and form.validate_on_submit():
        publish_now = form.submit_publish.data
        p = _post_from_form(form, post)
        db.session.commit()
        if publish_now:
            results = publish_social_post(p)
            ok = sum(1 for r in results.values() if r.get('ok'))
            flash(f'Publication : {ok}/{len(results)} plateforme(s) OK.', 'success' if ok else 'warning')
            return redirect(url_for('crm.social_post_detail', post_id=p.id))
        flash('Post enregistré.', 'success')
        return redirect(url_for('crm.social_post_form', post_id=p.id))

    if post and request.method == 'GET':
        _form_from_post(form, post)
    elif request.method == 'GET':
        form.platform_facebook.data = True
        form.platform_instagram.data = True

    preview_post = post or SocialPost(
        subject=form.subject.data or 'Aperçu',
        facebook_text=form.facebook_text.data or '',
        instagram_text=form.instagram_text.data or '',
        target_mode=form.target_mode.data or 'role',
        segment_id=form.segment_id.data or None,
        target_role=form.target_role.data,
        target_user_ids=list(form.target_user_ids.data or []),
        destination_url=form.destination_url.data,
    )

    return render_template(
        'crm/social_post_form.html',
        form=form,
        ai_form=ai_form,
        post=post,
        facebook_text=preview_post.facebook_text or preview_post.subject,
        instagram_text=preview_post.instagram_text or preview_post.facebook_text or preview_post.subject,
        image_url=resolve_post_image(preview_post) if (post or form.subject.data) else '',
        destination_url=resolve_post_destination(preview_post) if post else (form.destination_url.data or ''),
        target_count=target_preview_count(preview_post) if (post or form.target_mode.data) else 0,
        crm_active='social',
    )


@bp.route('/social/posts/<int:post_id>')
@staff_required
def social_post_detail(post_id):
    post = SocialPost.query.get_or_404(post_id)
    return render_template(
        'crm/social_post_detail.html',
        post=post,
        target_count=target_preview_count(post),
        preview_image=resolve_post_image(post),
        crm_active='social',
    )


@bp.route('/social/posts/<int:post_id>/publish', methods=['POST'])
@staff_required
def social_post_publish(post_id):
    post = SocialPost.query.get_or_404(post_id)
    results = publish_social_post(post)
    ok = sum(1 for r in results.values() if r.get('ok'))
    flash(f'Publication : {ok}/{len(results)} plateforme(s) OK.', 'success' if ok else 'warning')
    return redirect(url_for('crm.social_post_detail', post_id=post.id))


@bp.route('/social/posts/<int:post_id>/delete', methods=['POST'])
@staff_required
def social_post_delete(post_id):
    post = SocialPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Post supprimé.', 'info')
    return redirect(url_for('crm.social_posts_list'))


@bp.route('/social/api/generate', methods=['POST'])
@staff_required
def social_generate_ai():
    data = request.get_json(silent=True) or {}
    subject = (data.get('subject') or '').strip()
    if len(subject) < 3:
        return jsonify({'error': 'Sujet requis (3 caractères min.)'}), 400
    dest = (data.get('destination_url') or '').strip()
    try:
        texts = generate_social_post(
            subject=subject,
            keywords=(data.get('keywords') or '').strip(),
            tone=(data.get('tone') or 'inspirant'),
            destination_url=dest,
            language=(data.get('language') or 'fr'),
            manual=bool(data.get('manual')),
        )
        return jsonify(texts)
    except Exception as exc:
        return jsonify({'error': str(exc)[:200]}), 500


@bp.route('/social/api/preview', methods=['POST'])
@staff_required
def social_preview_api():
    data = request.get_json(silent=True) or {}
    fb = (data.get('facebook_text') or data.get('subject') or '').strip()
    ig = (data.get('instagram_text') or fb).strip()
    image = (data.get('image_url') or '').strip()
    link = (data.get('destination_url') or '').strip()
    html = render_template(
        'crm/_social_preview_fragment.html',
        facebook_text=fb,
        instagram_text=ig,
        image_url=image,
        destination_url=link,
    )
    return jsonify({'html': html})


@bp.route('/social/api/target-count', methods=['POST'])
@staff_required
def social_target_count_api():
    data = request.get_json(silent=True) or {}
    users = resolve_target_users(
        mode=data.get('target_mode', 'role'),
        segment_id=int(data.get('segment_id') or 0) or None,
        role=data.get('target_role'),
        user_ids=[int(x) for x in (data.get('target_user_ids') or [])],
    )
    return jsonify({'count': len(users), 'names': [u.name for u in users[:8]]})


@bp.route('/social/oauth/<platform>/connect')
@staff_required
def social_oauth_connect(platform):
    if platform == 'deviantart':
        if not DeviantArt.is_configured():
            flash('DEVIANTART_CLIENT_ID / SECRET manquants.', 'error')
            return redirect(url_for('crm.social_index'))
        url, _state, verifier = DeviantArt.begin_authorize()
        resp = redirect(url)
        pkce_set_cookie(resp, 'deviantart', verifier)
        return resp
    if platform == 'pinterest':
        if not Pinterest.is_configured():
            flash('PINTEREST_CLIENT_ID / SECRET manquants.', 'error')
            return redirect(url_for('crm.social_index'))
        from ..social.oauth import oauth_state_make
        st = oauth_state_make('pinterest')
        return redirect(Pinterest.authorize_url(st))
    flash('Plateforme inconnue.', 'error')
    return redirect(url_for('crm.social_index'))


@bp.route('/social/oauth/<platform>/callback')
@staff_required
def social_oauth_callback(platform):
    state = request.args.get('state', '')
    code = request.args.get('code', '')
    if not oauth_state_verify(state, platform):
        flash('OAuth expiré — réessayez.', 'error')
        return redirect(url_for('crm.social_index'))
    try:
        if platform == 'deviantart':
            verifier = pkce_read_verifier('deviantart')
            tok = DeviantArt.exchange_code(code, code_verifier=verifier)
            DeviantArt.save_tokens(tok)
            flash('DeviantArt connecté.', 'success')
            resp = redirect(url_for('crm.social_index'))
            pkce_clear_cookie(resp, 'deviantart')
            return resp
        if platform == 'pinterest':
            tok = Pinterest.exchange_code(code)
            if tok.get('error'):
                raise ValueError(tok.get('error_description') or tok.get('error'))
            Pinterest.save_tokens(tok)
            flash('Pinterest connecté.', 'success')
            return redirect(url_for('crm.social_index'))
    except Exception as exc:
        flash(f'Connexion {platform} échouée : {exc}', 'error')
    return redirect(url_for('crm.social_index'))


@bp.route('/social/oauth/<platform>/disconnect', methods=['POST'])
@staff_required
def social_oauth_disconnect(platform):
    if platform == 'deviantart':
        DeviantArt.disconnect()
    elif platform == 'pinterest':
        Pinterest.disconnect()
    flash(f'{platform.capitalize()} déconnecté.', 'info')
    return redirect(url_for('crm.social_index'))


@bp.route('/social/sync-deviantart', methods=['POST'])
@staff_required
def social_sync_deviantart():
    n = sync_all_deviantart_stats()
    flash(f'Stats DeviantArt mises à jour pour {n} œuvre(s).', 'success')
    return redirect(url_for('crm.social_index'))

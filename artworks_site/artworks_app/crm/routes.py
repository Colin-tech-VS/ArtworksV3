from datetime import datetime

from flask import (abort, flash, jsonify, redirect, render_template, request, url_for)
from flask_login import current_user
from sqlalchemy import func, or_

from .. import db
from ..models import Artwork, CmsPage, EmailCampaign, EmailSegment, EmailTemplate, User
from . import bp
from .analytics import analytics_detail, crm_overview
from .auth import staff_required
from .email_service import (
    build_message_html,
    html_to_text,
    resolve_campaign_recipients,
    send_campaign_to_users,
)
from .forms import (
    CampaignForm, CmsPageForm, CmsPageAiForm, EmailAiForm, EmailTemplateForm,
    SegmentForm, UserAdminForm,
)
from .segments import ROLE_LABELS, segment_count, segment_users


def _slugify(text: str) -> str:
    import re
    s = (text or '').lower().strip()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    return re.sub(r'-+', '-', s).strip('-')[:120]


def _segment_choices():
    choices = [(0, '— Choisir un segment —')]
    for seg in EmailSegment.query.order_by(EmailSegment.name).all():
        n = segment_count(seg.filters)
        label = f'{seg.name} ({n} contacts)'
        if seg.is_system:
            label += ' · auto'
        choices.append((seg.id, label))
    return choices


def _user_choices():
    return [
        (u.id, f'{u.display_name or u.username} ({u.email})')
        for u in User.query.filter(User.is_staff.is_(False), User.role != 'admin')
        .order_by(User.display_name, User.username).all()
    ]


def _preview_user():
    u = User.query.filter(User.is_staff.is_(False), User.role != 'admin').first()
    if u:
        return u
    from .email_branding import _sample_user
    return _sample_user()


def _campaign_recipient_label(campaign: EmailCampaign) -> str:
    mode = campaign.recipient_mode or 'segment'
    if mode == 'role':
        return ROLE_LABELS.get(campaign.recipient_role, campaign.recipient_role or '—')
    if mode == 'users':
        n = len(campaign.recipient_user_ids or [])
        return f'{n} utilisateur(s) sélectionné(s)'
    if campaign.segment:
        return campaign.segment.name
    return '—'


# ---------- Dashboard ----------

@bp.route('/')
@staff_required
def index():
    return render_template('crm/index.html', stats=crm_overview(), crm_active='overview')


@bp.route('/analytics')
@staff_required
def analytics():
    from ..analytics_track import ga4_analytics
    days = request.args.get('days', '30')
    try:
        days_int = int(days)
    except ValueError:
        days_int = 30
    if days_int not in (7, 30, 90):
        days_int = 30
    return render_template(
        'crm/analytics.html',
        stats=ga4_analytics(days_int),
        days=days_int,
        crm_active='analytics',
    )


# ---------- Users ----------

@bp.route('/users')
@staff_required
def users_list():
    role = request.args.get('role', 'all')
    plan = request.args.get('plan', 'all')
    q = request.args.get('q', '').strip()

    query = User.query.filter(User.is_staff.is_(False), User.role != 'admin')
    if role != 'all':
        query = query.filter(User.role == role)
    if plan != 'all':
        query = query.filter(User.subscription_plan == plan)
    if q:
        like = f'%{q}%'
        query = query.filter(or_(
            User.username.ilike(like),
            User.email.ilike(like),
            User.display_name.ilike(like),
        ))

    users = query.order_by(User.id.desc()).limit(200).all()
    artwork_counts = dict(
        db.session.query(Artwork.user_id, func.count(Artwork.id))
        .group_by(Artwork.user_id)
        .all()
    )
    return render_template(
        'crm/users.html',
        users=users,
        artwork_counts=artwork_counts,
        role=role,
        plan=plan,
        q=q,
        role_labels=ROLE_LABELS,
        crm_active='users',
    )


@bp.route('/users/<int:user_id>', methods=['GET', 'POST'])
@staff_required
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    form = UserAdminForm(obj=user)
    if form.validate_on_submit():
        user.display_name = form.display_name.data
        user.email = form.email.data.strip().lower()
        user.role = form.role.data
        user.subscription_plan = form.subscription_plan.data
        user.subscription_status = form.subscription_status.data
        user.is_staff = bool(form.is_staff.data)
        db.session.commit()
        from .auto_segments import classify_user
        classify_user(user)
        flash('Utilisateur mis à jour.', 'success')
        return redirect(url_for('crm.user_detail', user_id=user.id))

    artworks = Artwork.query.filter_by(user_id=user.id).order_by(Artwork.id.desc()).all()
    from .auto_segments import user_segments
    return render_template(
        'crm/user_detail.html',
        user=user,
        form=form,
        artworks=artworks,
        user_segments=user_segments(user),
        crm_active='users',
    )


# ---------- Artworks / Portfolio ----------

@bp.route('/artworks')
@staff_required
def artworks_list():
    status = request.args.get('status', 'all')
    q = request.args.get('q', '').strip()

    query = Artwork.query.join(User)
    if status != 'all':
        query = query.filter(Artwork.status == status)
    if q:
        like = f'%{q}%'
        query = query.filter(or_(
            Artwork.title.ilike(like),
            User.display_name.ilike(like),
            User.username.ilike(like),
        ))

    artworks = query.order_by(Artwork.id.desc()).limit(200).all()
    return render_template(
        'crm/artworks.html',
        artworks=artworks,
        status=status,
        q=q,
        crm_active='artworks',
    )


@bp.route('/artworks/<int:artwork_id>', methods=['POST'])
@staff_required
def artwork_toggle_early(artwork_id):
    artwork = Artwork.query.get_or_404(artwork_id)
    artwork.early_access = not artwork.early_access
    db.session.commit()
    flash('Avant-première mise à jour.', 'success')
    return redirect(url_for('crm.artworks_list'))


# ---------- CMS Pages ----------

@bp.route('/pages')
@staff_required
def pages_list():
    pages = CmsPage.query.order_by(CmsPage.updated_at.desc()).all()
    return render_template('crm/pages.html', pages=pages, crm_active='pages')


@bp.route('/pages/new', methods=['GET', 'POST'])
@bp.route('/pages/<int:page_id>/edit', methods=['GET', 'POST'])
@staff_required
def page_form(page_id=None):
    page = CmsPage.query.get(page_id) if page_id else None
    form = CmsPageForm(obj=page)
    ai_form = CmsPageAiForm()
    if request.method == 'POST' and not form.slug.data and form.title.data:
        form.slug.data = _slugify(form.title.data)

    if form.validate_on_submit():
        if page is None:
            page = CmsPage(author_id=current_user.id)
        page.title = form.title.data
        page.slug = form.slug.data.strip().lower()
        page.excerpt = form.excerpt.data
        page.body = form.body.data
        page.meta_title = form.meta_title.data
        page.meta_description = form.meta_description.data
        page.published = bool(form.published.data)
        page.show_in_nav = bool(form.show_in_nav.data)
        page.updated_at = datetime.utcnow()
        if page.id is None:
            db.session.add(page)
        db.session.commit()
        flash('Page enregistrée.', 'success')
        return redirect(url_for('crm.pages_list'))

    return render_template(
        'crm/page_form.html',
        form=form,
        ai_form=ai_form,
        page=page,
        crm_active='pages',
    )


@bp.route('/pages/generate-ai', methods=['POST'])
@staff_required
def page_generate_ai():
    from ..cms_ai import generate_seo_page
    from ..ai import CuratorialAIError
    ai_form = CmsPageAiForm()
    if not ai_form.validate_on_submit():
        return jsonify({'ok': False, 'error': 'Formulaire invalide — décrivez le sujet (min. 5 caractères).'}), 400
    try:
        data = generate_seo_page(
            topic=ai_form.ai_topic.data,
            keywords=ai_form.ai_keywords.data or '',
            tone=ai_form.ai_tone.data or 'expert',
        )
        return jsonify({'ok': True, 'page': data})
    except CuratorialAIError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400


@bp.route('/pages/<int:page_id>/delete', methods=['POST'])
@staff_required
def page_delete(page_id):
    page = CmsPage.query.get_or_404(page_id)
    db.session.delete(page)
    db.session.commit()
    flash('Page supprimée.', 'success')
    return redirect(url_for('crm.pages_list'))


# ---------- Segments ----------

@bp.route('/segments')
@staff_required
def segments_list():
    from .auto_segments import ensure_system_segments
    ensure_system_segments()
    segments = EmailSegment.query.order_by(EmailSegment.is_system.desc(), EmailSegment.updated_at.desc()).all()
    counts = {s.id: segment_count(s.filters) for s in segments}
    return render_template(
        'crm/segments.html',
        segments=segments,
        counts=counts,
        crm_active='segments',
    )


@bp.route('/segments/reclassify', methods=['POST'])
@staff_required
def segments_reclassify():
    from .auto_segments import reclassify_all_users
    n = reclassify_all_users()
    flash(f'{n} utilisateur(s) reclassés automatiquement.', 'success')
    return redirect(url_for('crm.segments_list'))


@bp.route('/segments/new', methods=['GET', 'POST'])
@bp.route('/segments/<int:segment_id>/edit', methods=['GET', 'POST'])
@staff_required
def segment_form(segment_id=None):
    segment = EmailSegment.query.get(segment_id) if segment_id else None
    if segment and segment.is_system:
        flash('Segment système — classification automatique, non modifiable.', 'warning')
        return redirect(url_for('crm.segment_detail', segment_id=segment.id))
    form = SegmentForm(obj=segment)
    if segment:
        f = segment.filters
        form.role.data = f.get('role', 'all')
        form.plan.data = f.get('plan', 'all')
        form.subscription_status.data = f.get('subscription_status', 'all')
        form.paid_only.data = bool(f.get('paid_only'))
        form.min_artworks.data = f.get('min_artworks') or None
        form.has_stripe.data = bool(f.get('has_stripe'))

    if form.validate_on_submit():
        if segment is None:
            segment = EmailSegment()
        segment.name = form.name.data
        segment.description = form.description.data
        segment.filters = {
            'role': form.role.data,
            'plan': form.plan.data,
            'subscription_status': form.subscription_status.data,
            'paid_only': bool(form.paid_only.data),
            'min_artworks': form.min_artworks.data or None,
            'has_stripe': bool(form.has_stripe.data),
        }
        segment.updated_at = datetime.utcnow()
        if segment.id is None:
            db.session.add(segment)
        db.session.commit()
        flash('Segment enregistré.', 'success')
        return redirect(url_for('crm.segments_list'))

    preview_count = segment_count({
        'role': form.role.data,
        'plan': form.plan.data,
        'subscription_status': form.subscription_status.data,
        'paid_only': bool(form.paid_only.data),
        'min_artworks': form.min_artworks.data,
        'has_stripe': bool(form.has_stripe.data),
    }) if request.method in ('GET', 'POST') else 0

    return render_template(
        'crm/segment_form.html',
        form=form,
        segment=segment,
        preview_count=preview_count,
        crm_active='segments',
    )


@bp.route('/segments/<int:segment_id>')
@staff_required
def segment_detail(segment_id):
    segment = EmailSegment.query.get_or_404(segment_id)
    users = segment_users(segment.filters)[:100]
    total = segment_count(segment.filters)
    return render_template(
        'crm/segment_detail.html',
        segment=segment,
        users=users,
        total=total,
        crm_active='segments',
    )


@bp.route('/segments/<int:segment_id>/delete', methods=['POST'])
@staff_required
def segment_delete(segment_id):
    segment = EmailSegment.query.get_or_404(segment_id)
    if segment.is_system:
        flash('Les segments système ne peuvent pas être supprimés.', 'error')
        return redirect(url_for('crm.segments_list'))
    db.session.delete(segment)
    db.session.commit()
    flash('Segment supprimé.', 'success')
    return redirect(url_for('crm.segments_list'))


# ---------- Email hub ----------

@bp.route('/emails')
@staff_required
def campaigns_list():
    from flask import current_app
    from .email_templates_seed import ensure_default_email_templates
    ensure_default_email_templates()
    campaigns = EmailCampaign.query.order_by(EmailCampaign.created_at.desc()).all()
    templates = EmailTemplate.query.order_by(EmailTemplate.kind, EmailTemplate.name).all()
    return render_template(
        'crm/campaigns.html',
        campaigns=campaigns,
        templates=templates,
        mail_enabled=current_app.config.get('MAIL_ENABLED'),
        crm_active='emails',
    )


@bp.route('/emails/templates')
@staff_required
def templates_list():
    from .email_templates_seed import ensure_default_email_templates
    ensure_default_email_templates()
    templates = EmailTemplate.query.order_by(EmailTemplate.name).all()
    return render_template(
        'crm/email_templates.html',
        templates=templates,
        crm_active='emails',
    )


@bp.route('/emails/templates/<slug>/edit', methods=['GET', 'POST'])
@staff_required
def template_form(slug):
    from .email_templates_seed import ensure_default_email_templates
    ensure_default_email_templates()
    tpl = EmailTemplate.query.filter_by(slug=slug).first_or_404()
    form = EmailTemplateForm(obj=tpl)
    ai_form = EmailAiForm()

    if form.validate_on_submit():
        tpl.name = form.name.data
        tpl.subject = form.subject.data
        tpl.preview_text = form.preview_text.data
        tpl.body_html = form.body_html.data
        tpl.body_text = html_to_text(form.body_html.data)
        tpl.active = bool(form.active.data)
        tpl.auto_send = bool(form.auto_send.data)
        tpl.updated_at = datetime.utcnow()
        tpl.author_id = current_user.id
        db.session.commit()
        flash('Template enregistré.', 'success')
        return redirect(url_for('crm.template_form', slug=tpl.slug))

    preview_html = build_message_html(
        body_html=tpl.body_html or '',
        preview_text=tpl.preview_text or '',
        subject=tpl.subject or '',
        user=_preview_user(),
    )
    return render_template(
        'crm/email_template_form.html',
        form=form,
        ai_form=ai_form,
        template=tpl,
        preview_html=preview_html,
        crm_active='emails',
    )


@bp.route('/emails/templates/<slug>/generate-ai', methods=['POST'])
@staff_required
def template_generate_ai(slug):
    from ..ai import CuratorialAIError
    from .email_ai import generate_email_content

    tpl = EmailTemplate.query.filter_by(slug=slug).first_or_404()
    ai_form = EmailAiForm()
    if not ai_form.validate_on_submit():
        return jsonify({'ok': False, 'error': 'Formulaire invalide'}), 400
    try:
        data = generate_email_content(
            brief=ai_form.ai_brief.data,
            tone=ai_form.ai_tone.data,
            email_type='transactionnel' if tpl.kind == 'transactional' else 'marketing',
        )
    except CuratorialAIError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    preview_html = build_message_html(
        body_html=data['body_html'],
        preview_text=data.get('preview_text', ''),
        subject=data.get('subject', ''),
        user=_preview_user(),
    )
    return jsonify({'ok': True, 'data': data, 'preview_html': preview_html})


@bp.route('/emails/preview', methods=['POST'])
@staff_required
def email_preview_api():
    """Aperçu live (AJAX) — rendu Artworks réel."""
    data = request.get_json(silent=True) or {}
    body = data.get('body_html') or ''
    subject = data.get('subject') or ''
    preview_text = data.get('preview_text') or ''
    user_id = data.get('user_id')
    user = User.query.get(user_id) if user_id else _preview_user()
    html = build_message_html(body_html=body, preview_text=preview_text, subject=subject, user=user)
    subj = html_to_text(subject)  # fallback
    from .email_branding import personalize
    subj = personalize(subject, user)
    return jsonify({'ok': True, 'html': html, 'subject': subj})


@bp.route('/emails/generate-ai', methods=['POST'])
@staff_required
def campaign_generate_ai():
    from ..ai import CuratorialAIError
    from .email_ai import generate_email_content

    ai_form = EmailAiForm()
    if not ai_form.validate_on_submit():
        return jsonify({'ok': False, 'error': 'Formulaire invalide'}), 400
    try:
        data = generate_email_content(
            brief=ai_form.ai_brief.data,
            tone=ai_form.ai_tone.data,
            email_type='marketing',
        )
    except CuratorialAIError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    preview_html = build_message_html(
        body_html=data['body_html'],
        preview_text=data.get('preview_text', ''),
        subject=data.get('subject', ''),
        user=_preview_user(),
    )
    return jsonify({'ok': True, 'data': data, 'preview_html': preview_html})


@bp.route('/emails/new', methods=['GET', 'POST'])
@bp.route('/emails/<int:campaign_id>/edit', methods=['GET', 'POST'])
@staff_required
def campaign_form(campaign_id=None):
    campaign = EmailCampaign.query.get(campaign_id) if campaign_id else None
    if campaign and campaign.status == 'sent':
        flash('Campagne déjà envoyée — lecture seule.', 'error')
        return redirect(url_for('crm.campaign_detail', campaign_id=campaign.id))

    form = CampaignForm(obj=campaign)
    ai_form = EmailAiForm()
    form.segment_id.choices = _segment_choices()
    form.recipient_user_ids.choices = _user_choices()

    if request.method == 'GET' and campaign:
        form.recipient_user_ids.data = campaign.recipient_user_ids
    if request.method == 'GET' and request.args.get('segment'):
        try:
            form.segment_id.data = int(request.args.get('segment'))
            form.recipient_mode.data = 'segment'
        except (TypeError, ValueError):
            pass

    if form.validate_on_submit():
        mode = form.recipient_mode.data
        valid = True
        if mode == 'segment' and not form.segment_id.data:
            form.segment_id.errors.append('Choisissez un segment.')
            valid = False
        if mode == 'users' and not form.recipient_user_ids.data:
            form.recipient_user_ids.errors.append('Sélectionnez au moins un utilisateur.')
            valid = False
        if not valid:
            pass
        else:
            if campaign is None:
                campaign = EmailCampaign(author_id=current_user.id, status='draft')
            campaign.name = form.name.data
            campaign.subject = form.subject.data
            campaign.preview_text = form.preview_text.data
            campaign.recipient_mode = form.recipient_mode.data
            campaign.recipient_role = form.recipient_role.data if form.recipient_mode.data == 'role' else None
            campaign.segment_id = form.segment_id.data or None if form.recipient_mode.data == 'segment' else None
            campaign.recipient_user_ids = form.recipient_user_ids.data if form.recipient_mode.data == 'users' else []
            campaign.body_html = form.body_html.data
            campaign.body_text = form.body_text.data or html_to_text(form.body_html.data)
            campaign.preview_confirmed_at = None
            if campaign.id is None:
                db.session.add(campaign)
            db.session.commit()
            flash('Campagne enregistrée — vérifiez l\'aperçu avant envoi.', 'success')
            return redirect(url_for('crm.campaign_preview_send', campaign_id=campaign.id))

    preview_html = build_message_html(
        body_html=form.body_html.data or (campaign.body_html if campaign else ''),
        preview_text=form.preview_text.data or (campaign.preview_text if campaign else ''),
        subject=form.subject.data or (campaign.subject if campaign else ''),
        user=_preview_user(),
    )
    recipient_preview_count = 0
    if request.method == 'POST' or campaign:
        tmp = campaign or EmailCampaign()
        tmp.recipient_mode = form.recipient_mode.data
        tmp.recipient_role = form.recipient_role.data
        tmp.segment_id = form.segment_id.data or None
        tmp.recipient_user_ids = form.recipient_user_ids.data or []
        if tmp.segment_id:
            tmp.segment = EmailSegment.query.get(tmp.segment_id)
        recipient_preview_count = len(resolve_campaign_recipients(tmp))

    return render_template(
        'crm/campaign_form.html',
        form=form,
        ai_form=ai_form,
        campaign=campaign,
        preview_html=preview_html,
        recipient_preview_count=recipient_preview_count,
        crm_active='emails',
    )


@bp.route('/emails/<int:campaign_id>')
@staff_required
def campaign_detail(campaign_id):
    campaign = EmailCampaign.query.get_or_404(campaign_id)
    recipients = resolve_campaign_recipients(campaign)
    preview_html = build_message_html(
        body_html=campaign.body_html or '',
        preview_text=campaign.preview_text or '',
        subject=campaign.subject or '',
        user=_preview_user(),
    )
    return render_template(
        'crm/campaign_detail.html',
        campaign=campaign,
        recipients=recipients,
        recipient_count=len(recipients),
        recipient_label=_campaign_recipient_label(campaign),
        preview_html=preview_html,
        crm_active='emails',
    )


@bp.route('/emails/<int:campaign_id>/preview-send', methods=['GET', 'POST'])
@staff_required
def campaign_preview_send(campaign_id):
    from flask import current_app

    campaign = EmailCampaign.query.get_or_404(campaign_id)
    if campaign.status == 'sent':
        flash('Campagne déjà envoyée.', 'error')
        return redirect(url_for('crm.campaign_detail', campaign_id=campaign.id))

    recipients = resolve_campaign_recipients(campaign)
    if not recipients:
        flash('Aucun destinataire — configurez segment, groupe ou utilisateurs.', 'error')
        return redirect(url_for('crm.campaign_form', campaign_id=campaign.id))

    preview_html = build_message_html(
        body_html=campaign.body_html or '',
        preview_text=campaign.preview_text or '',
        subject=campaign.subject or '',
        user=_preview_user(),
    )

    if request.method == 'POST' and request.form.get('confirm') == '1':
        if not current_app.config.get('MAIL_ENABLED'):
            flash('Configurez SMTP_HOST / SMTP_USER / SMTP_PASSWORD dans .env.', 'error')
            return redirect(url_for('crm.campaign_preview_send', campaign_id=campaign.id))

        campaign.status = 'sending'
        campaign.recipient_count = len(recipients)
        campaign.preview_confirmed_at = datetime.utcnow()
        db.session.commit()

        sent, failed, errors = send_campaign_to_users(campaign, recipients)
        campaign.sent_count = sent
        campaign.failed_count = failed
        campaign.status = 'sent' if failed == 0 else ('failed' if sent == 0 else 'sent')
        campaign.sent_at = datetime.utcnow()
        db.session.commit()

        if errors:
            flash(f'Envoi terminé : {sent} ok, {failed} échecs. {errors[0]}', 'error')
        else:
            flash(f'Campagne envoyée à {sent} contact(s).', 'success')
        return redirect(url_for('crm.campaign_detail', campaign_id=campaign.id))

    return render_template(
        'crm/campaign_preview_send.html',
        campaign=campaign,
        recipients=recipients,
        recipient_count=len(recipients),
        recipient_label=_campaign_recipient_label(campaign),
        preview_html=preview_html,
        crm_active='emails',
    )


@bp.route('/emails/<int:campaign_id>/send', methods=['POST'])
@staff_required
def campaign_send(campaign_id):
    """Redirige vers l'aperçu obligatoire avant envoi."""
    return redirect(url_for('crm.campaign_preview_send', campaign_id=campaign_id))


@bp.route('/emails/<int:campaign_id>/delete', methods=['POST'])
@staff_required
def campaign_delete(campaign_id):
    campaign = EmailCampaign.query.get_or_404(campaign_id)
    db.session.delete(campaign)
    db.session.commit()
    flash('Campagne supprimée.', 'success')
    return redirect(url_for('crm.campaigns_list'))


# ---------- Pricing ----------

@bp.route('/pricing', methods=['GET', 'POST'])
@staff_required
def pricing():
    from ..models import PlatformSetting
    from ..pricing_store import (
        editable_plans_for_crm,
        get_commission_rate,
        get_plan_prices_overrides,
        set_commission_rate,
        set_plan_prices,
    )

    plans = editable_plans_for_crm()

    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action == 'reset':
            for key in ('commission_rate', 'plan_prices'):
                row = PlatformSetting.query.get(key)
                if row:
                    db.session.delete(row)
            db.session.commit()
            flash('Tarifs réinitialisés aux valeurs par défaut du code.', 'success')
            return redirect(url_for('crm.pricing'))

        try:
            comm_pct = float((request.form.get('commission_percent') or '18').replace(',', '.'))
            if comm_pct < 0 or comm_pct > 50:
                raise ValueError('commission out of range')
            set_commission_rate(comm_pct / 100.0, user_id=current_user.id)

            updates = {}
            for p in plans:
                raw = (request.form.get(p['field_name']) or '').strip().replace(',', '.')
                if not raw:
                    continue
                euros = float(raw)
                if euros < 0:
                    raise ValueError('negative price')
                updates[f"{p['role']}.{p['slug']}"] = int(round(euros * 100))
            set_plan_prices(updates, user_id=current_user.id)
            flash('Tarifs et commission enregistrés — effectifs immédiatement sur le site et Stripe checkout.', 'success')
        except ValueError:
            flash('Valeurs invalides. Commission : 0–50 %. Prix en euros (ex. 9.99).', 'error')
        return redirect(url_for('crm.pricing'))

    commission_row = PlatformSetting.query.get('commission_rate')
    prices_row = PlatformSetting.query.get('plan_prices')
    return render_template(
        'crm/pricing.html',
        plans=plans,
        commission_percent=round(get_commission_rate() * 100, 2),
        overrides=get_plan_prices_overrides(),
        commission_updated=commission_row.updated_at if commission_row else None,
        prices_updated=prices_row.updated_at if prices_row else None,
        crm_active='pricing',
    )


# ---------- Integrations ----------

@bp.route('/integrations')
@staff_required
def integrations():
    from .integrations import integrations_overview
    return render_template(
        'crm/integrations.html',
        overview=integrations_overview(),
        crm_active='integrations',
    )


@bp.route('/integrations/test/<service_id>', methods=['POST'])
@staff_required
def integrations_test(service_id):
    from .integrations import integrations_overview
    overview = integrations_overview()
    item = next((i for i in overview['items'] if i['id'] == service_id), None)
    if not item:
        return jsonify({'ok': False, 'error': 'Service inconnu'}), 404
    ok = item['status'] == 'connected'
    return jsonify({'ok': ok, 'message': item['message'], 'status': item['status']})

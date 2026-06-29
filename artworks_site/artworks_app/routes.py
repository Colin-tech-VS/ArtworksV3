from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app, abort, jsonify)
from .models import Artwork, User, Series, CmsPage
from . import db
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid

bp = Blueprint('main', __name__)


# ---------- helpers ----------
def _save_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    name = f"{uuid.uuid4().hex}_{filename}"
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    try:
        os.makedirs(upload_folder, exist_ok=True)
    except Exception:
        pass
    file_storage.save(os.path.join(upload_folder, name))
    return name


def _series_choices_for(user):
    choices = [(0, '— Aucune série —')]
    for s in user.series:
        choices.append((s.id, s.name))
    return choices


def _bind_discipline(form, current=None):
    from .catalog import DISCIPLINES, select_choices
    form.discipline.choices = select_choices(DISCIPLINES, current, blank_label='— Discipline —')
    if current:
        form.discipline.data = current


def _sync_curatorial_note(user, success_msg):
    """Regénère la note curatoriale après une modification du portfolio/profil."""
    from .curatorial import refresh_curatorial_note
    note, err = refresh_curatorial_note(user, commit=False)
    db.session.commit()
    if err:
        flash(f'{success_msg} Note curatoriale non générée : {err}', 'warning')
    elif err is None and note:
        flash(f'{success_msg} Note curatoriale mise à jour.', 'success')
    else:
        flash(success_msg.rstrip('.') + '.', 'success')


# ---------- public pages ----------
@bp.route('/')
def index():
    from .catalog_display import featured_artworks
    from .entitlements import has_public_portfolio
    from .seo_public import page_meta, site_json_ld, json_ld_script, _site_url
    artworks = Artwork.query.order_by(Artwork.id).all()
    featured = featured_artworks(artworks, limit=8)
    seen = set()
    artists = []
    for a in artworks:
        if a.owner and a.owner.id not in seen and has_public_portfolio(a.owner):
            seen.add(a.owner.id)
            artists.append(a.owner)
    seo = page_meta('home')
    json_ld = json_ld_script(site_json_ld())
    return render_template(
        'index.html', featured=featured, artists=artists[:4],
        total=len(featured), seo=seo, json_ld=json_ld,
        canonical=_site_url() + '/',
    )


@bp.route('/tarifs')
@bp.route('/tarifs/<profil>')
def tarifs(profil='artiste'):
    from .subscriptions import plans_for_role, price_label, ROLE_LABELS, normalize_plan
    from .entitlements import effective_plan

    valid = ('artiste', 'galerie', 'collectionneur')
    if profil not in valid:
        profil = 'artiste'
    plans = plans_for_role(profil)
    intros = {
        'artiste': 'Publiez, vendez et gagnez en visibilité — de la première œuvre au portfolio professionnel.',
        'galerie': 'Cataloguez, vendez en ligne et gérez vos artistes depuis un espace dédié.',
        'collectionneur': 'Explorez, anticipez le marché et construisez votre collection avec confiance.',
    }
    current_slug = None
    if current_user.is_authenticated and current_user.role == profil:
        current_slug = effective_plan(current_user)
    from .seo_public import page_meta, _site_url
    seo = page_meta(f'tarifs_{profil}')
    return render_template(
        'tarifs.html',
        role=profil,
        role_label=ROLE_LABELS.get(profil, profil.capitalize()),
        role_intro=intros.get(profil, ''),
        plans=plans,
        price_label=price_label,
        current_slug=current_slug,
        roles=[(r, ROLE_LABELS[r]) for r in valid],
        seo=seo,
        canonical=_site_url() + url_for('main.tarifs', profil=profil),
    )


def _render_offer(role: str, hero_image: str):
    from .offer_pages import offer_context, OFFER_CONFIG
    from .seo_public import json_ld_script, offer_json_ld

    ctx = offer_context(role)
    cfg = OFFER_CONFIG.get(role, OFFER_CONFIG['artiste'])
    base = request.url_root.rstrip('/')
    ctx['hero_image'] = hero_image
    ctx['canonical_url'] = base + cfg['path']
    ctx['json_ld'] = json_ld_script(offer_json_ld(role, ctx['canonical_url']))
    return render_template('offre.html', **ctx)


@bp.route('/offre')
def offre_artiste():
    return _render_offer(
        'artiste',
        'https://images.unsplash.com/photo-1578301978693-85fa9c0320b9?auto=format&fit=crop&w=1920&q=80',
    )


@bp.route('/offre-galerie')
def offre_galerie():
    return _render_offer(
        'galerie',
        'https://images.unsplash.com/photo-1578301978018-3005759f48f7?auto=format&fit=crop&w=1920&q=80',
    )


@bp.route('/offre-collectionneur')
def offre_collectionneur():
    return _render_offer(
        'collectionneur',
        'https://images.unsplash.com/photo-1578926288207-a90a5366759d?auto=format&fit=crop&w=1920&q=80',
    )


@bp.route('/robots.txt')
def robots_txt():
    from flask import Response
    base = request.url_root.rstrip('/')
    body = (
        'User-agent: *\n'
        'Allow: /\n'
        'Disallow: /dashboard\n'
        'Disallow: /profile/\n'
        'Disallow: /crm/\n'
        f'Sitemap: {base}/sitemap.xml\n'
    )
    return Response(body, mimetype='text/plain')


@bp.route('/sitemap.xml')
def sitemap():
    from flask import Response, render_template
    from .entitlements import has_public_portfolio
    from .seo_public import _site_url

    base = _site_url()
    urls = []
    static_paths = [
        ('/', 'daily', '1.0'),
        ('/explorer', 'daily', '0.9'),
        ('/tarifs', 'weekly', '0.8'),
        ('/offre', 'weekly', '0.9'),
        ('/offre-galerie', 'weekly', '0.8'),
        ('/offre-collectionneur', 'weekly', '0.8'),
    ]
    for path, freq, pri in static_paths:
        urls.append({'loc': base + path, 'changefreq': freq, 'priority': pri})

    for page in CmsPage.query.filter_by(published=True).all():
        urls.append({'loc': base + url_for('main.cms_page', slug=page.slug), 'changefreq': 'monthly', 'priority': '0.6'})

    for user in User.query.filter(User.role.in_(('artiste', 'galerie'))).all():
        if user.role == 'artiste' and not has_public_portfolio(user):
            continue
        urls.append({
            'loc': base + url_for('main.artist', artist_id=user.id),
            'changefreq': 'weekly',
            'priority': '0.7',
        })

    for art in sort_artworks_public():
        urls.append({
            'loc': base + url_for('main.artwork_detail', artwork_id=art.id),
            'changefreq': 'weekly',
            'priority': '0.6',
        })

    xml = render_template('sitemap.xml', urls=urls)
    return Response(xml, mimetype='application/xml')


def sort_artworks_public():
    from .catalog_display import sort_artworks
    return sort_artworks(Artwork.query.all())


@bp.route('/p/<slug>')
def cms_page(slug):
    page = CmsPage.query.filter_by(slug=slug, published=True).first_or_404()
    return render_template('cms_page.html', page=page, active='cms')


@bp.route('/explorer')
def explorer():
    from .catalog_display import sort_artworks
    from .seo_public import page_meta, explorer_json_ld, json_ld_script, _site_url, SITE_NAME
    q = request.args.get('q', '').strip()
    query = Artwork.query
    if q:
        query = query.filter(Artwork.title.contains(q) | Artwork.description.contains(q))
    artworks = sort_artworks(query.all(), current_user if current_user.is_authenticated else None)
    seo = page_meta('explorer')
    if q:
        seo = page_meta('explorer', title=f'« {q} » — Collection art contemporain | {SITE_NAME}',
                        description=f'Résultats pour « {q} » : œuvres curatées disponibles sur {SITE_NAME}.')
    json_ld = json_ld_script(explorer_json_ld(artworks, query=q))
    return render_template(
        'explorer.html', artworks=artworks, q=q, seo=seo, json_ld=json_ld,
        canonical=_site_url() + url_for('main.explorer'),
    )


@bp.route('/artist/<int:artist_id>')
def artist(artist_id):
    from .entitlements import user_entitlements, has_public_portfolio, portfolio_subscription_active
    from .seo_public import artist_meta, artist_json_ld, json_ld_script
    artist = User.query.get_or_404(artist_id)
    ent = user_entitlements(artist)
    is_owner = current_user.is_authenticated and current_user.id == artist.id
    if artist.role in ('artiste', 'galerie'):
        if not portfolio_subscription_active(artist):
            if is_owner:
                return render_template('artist_portfolio_locked.html', artist=artist)
            abort(404)
        if not has_public_portfolio(artist):
            if is_owner:
                return render_template('artist_connect_pending.html', artist=artist)
            abort(404)
    artworks = artist.artworks
    seo = artist_meta(artist)
    json_ld = json_ld_script(artist_json_ld(artist))
    return render_template(
        'artist.html', artist=artist, artworks=artworks, artist_ent=ent,
        seo=seo, json_ld=json_ld,
    )


@bp.route('/artwork/<int:artwork_id>')
def artwork_detail(artwork_id):
    from .catalog_display import artwork_visible_to_viewer, sort_artworks
    from .entitlements import user_entitlements, has_public_portfolio
    from .seo_public import artwork_meta, artwork_json_ld, json_ld_script
    from .monetization import commission_percent_label
    a = Artwork.query.get_or_404(artwork_id)
    if a.owner and a.owner.role in ('artiste', 'galerie') and not has_public_portfolio(a.owner):
        abort(404)
    if not artwork_visible_to_viewer(a, current_user if current_user.is_authenticated else None):
        flash('Cette œuvre est en avant-première réservée aux abonnés Membre et Patron.', 'info')
        return redirect(url_for('main.tarifs', profil='collectionneur'))
    a.view_count = (a.view_count or 0) + 1
    db.session.commit()
    from .analytics_track import track_event
    track_event('artwork_view', path=request.path, title=a.title, artwork_id=a.id)
    owner_ent = user_entitlements(a.owner) if a.owner else {}
    viewer_ent = user_entitlements(current_user) if current_user.is_authenticated else {}
    same_artist = [w for w in (a.owner.artworks if a.owner else []) if w.id != a.id][:4]
    similar = sort_artworks(
        Artwork.query.filter(Artwork.id != a.id, Artwork.user_id != a.user_id).all(),
        current_user if current_user.is_authenticated else None,
    )[:4]
    seo = artwork_meta(a)
    json_ld = json_ld_script(artwork_json_ld(a))
    return render_template(
        'artwork_detail.html', artwork=a,
        same_artist=same_artist, similar=similar,
        owner_ent=owner_ent, user_ent=viewer_ent,
        seo=seo, json_ld=json_ld,
        commission_label=commission_percent_label(),
    )


@bp.route('/artwork/<int:artwork_id>/purchase', methods=['POST'])
def purchase_artwork(artwork_id):
    from .marketplace import create_artwork_checkout, fulfill_artwork_sale
    from .entitlements import user_entitlements, has_public_portfolio
    a = Artwork.query.get_or_404(artwork_id)
    if a.owner and a.owner.role in ('artiste', 'galerie') and not has_public_portfolio(a.owner):
        abort(404)
    if not user_entitlements(a.owner).get('marketplace_enabled') if a.owner else False:
        flash('Cette œuvre n\'est pas disponible à l\'achat en ligne.', 'warning')
        return redirect(url_for('main.artwork_detail', artwork_id=a.id))

    email = (request.form.get('email') or '').strip()
    if current_user.is_authenticated:
        email = current_user.email
    if not email or '@' not in email:
        flash('Indiquez une adresse email valide pour recevoir la confirmation.', 'error')
        return redirect(url_for('main.artwork_detail', artwork_id=a.id))

    success = url_for('main.purchase_success', artwork_id=a.id, _external=True)
    cancel = url_for('main.artwork_detail', artwork_id=a.id, _external=True)
    url, err = create_artwork_checkout(
        artwork=a, buyer_email=email, success_url=success, cancel_url=cancel,
    )
    if url:
        return redirect(url)

    if current_app.config.get('STRIPE_DEMO_MODE') or not current_app.config.get('STRIPE_ENABLED'):
        fulfill_artwork_sale({'metadata': {'kind': 'artworks_sale', 'artwork_id': str(a.id)}})
        flash('Achat simulé (mode démo — Stripe non configuré). Œuvre marquée réservée.', 'warning')
        return redirect(url_for('main.artwork_detail', artwork_id=a.id))

    flash(f'Paiement indisponible : {err}', 'error')
    return redirect(url_for('main.artwork_detail', artwork_id=a.id))


@bp.route('/artwork/<int:artwork_id>/purchase/success')
def purchase_success(artwork_id):
    from .marketplace import fulfill_artwork_sale
    a = Artwork.query.get_or_404(artwork_id)
    session_id = request.args.get('session_id', '')
    if session_id:
        try:
            import stripe
            key = current_app.config.get('STRIPE_SECRET_KEY', '')
            if stripe and key:
                stripe.api_key = key
                sess = stripe.checkout.Session.retrieve(session_id)
                if fulfill_artwork_sale(sess):
                    flash('Merci ! Votre achat est confirmé — l\'artiste vous contactera pour la livraison.', 'success')
                else:
                    flash('Paiement en cours de confirmation…', 'info')
        except Exception:
            flash('Paiement reçu — confirmation en cours.', 'info')
    return redirect(url_for('main.artwork_detail', artwork_id=a.id))


# ---------- dashboard ----------
@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin' or getattr(current_user, 'is_staff', False):
        return redirect(url_for('crm.index'))
    from .dashboard_ctx import profile_completion, dashboard_stats
    from .entitlements import user_entitlements
    import secrets
    artworks = current_user.artworks
    series = current_user.series
    pct, done, total, missing = profile_completion(current_user)
    stats = dashboard_stats(current_user, artworks, series)
    ent = user_entitlements(current_user)
    if ent.get('shareable_wishlist') and not current_user.wishlist_share_token:
        current_user.wishlist_share_token = secrets.token_urlsafe(12)[:32]
        db.session.commit()
    gallery_artists = []
    price_alerts = []
    if current_user.role == 'galerie':
        from .models import GalleryArtist
        gallery_artists = GalleryArtist.query.filter_by(gallery_id=current_user.id).all()
    if current_user.role == 'collectionneur' and ent.get('price_alerts'):
        from .models import PriceAlert
        price_alerts = PriceAlert.query.filter_by(user_id=current_user.id).all()
    if current_user.role in ('artiste', 'galerie'):
        from .social.stats import sync_artwork_deviantart_stats
        for art in artworks:
            if art.deviantart_deviation_id:
                sync_artwork_deviantart_stats(art)
    from .stripe_connect import connect_status, payout_label_for_role
    from . import billing
    return render_template(
        'dashboard.html',
        artworks=artworks,
        series=series,
        profile_pct=pct,
        profile_done=done,
        profile_total=total,
        profile_missing=missing,
        stats=stats,
        ent=ent,
        gallery_artists=gallery_artists,
        price_alerts=price_alerts,
        connect=connect_status(current_user),
        connect_payout_label=payout_label_for_role(current_user.role or ''),
        stripe_ready=billing.stripe_ready(),
    )


@bp.route('/my-artworks')
@login_required
def my_artworks():
    return redirect(url_for('main.dashboard'))


# ---------- artwork CRUD ----------
@bp.route('/artwork/create', methods=['GET', 'POST'])
@login_required
def create_artwork():
    from .forms import ArtworkForm
    from .entitlements import can_publish_artwork, user_entitlements
    form = ArtworkForm()
    _bind_discipline(form)
    form.series_id.choices = _series_choices_for(current_user)
    ent = user_entitlements(current_user)
    ok, limit_msg = can_publish_artwork(current_user)
    if request.method == 'GET' and not ok:
        flash(limit_msg, 'warning')
        return redirect(url_for('main.subscription'))
    if form.validate_on_submit():
        ok, msg = can_publish_artwork(current_user)
        if not ok:
            flash(msg, 'warning')
            return redirect(url_for('main.subscription'))
        a = Artwork(title=form.title.data, description=form.description.data,
                    price=float(form.price.data or 0), owner=current_user,
                    discipline=form.discipline.data or None,
                    medium=form.medium.data or None,
                    dimensions=form.dimensions.data or None,
                    format=form.format.data or None,
                    year=int(form.year.data) if form.year.data else None,
                    status='dispo', created_at=datetime.utcnow(),
                    early_access=bool(request.form.get('early_access')) if ent.get('private_sales') else False)
        sid = form.series_id.data or 0
        if sid:
            s = Series.query.get(sid)
            if s and s.user_id == current_user.id:
                a.series_id = s.id
        name = _save_upload(form.image.data)
        if name:
            a.image = name
        db.session.add(a)
        db.session.commit()
        _sync_curatorial_note(current_user, 'Œuvre publiée.')
        from .social.publish import publish_artwork_async
        publish_artwork_async(a, current_user)
        return redirect(url_for('main.dashboard'))
    return render_template('artwork_form.html', form=form, mode='create', ent=ent, publish_ok=ok)


@bp.route('/artwork/<int:artwork_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_artwork(artwork_id):
    from .forms import ArtworkForm
    from .entitlements import user_entitlements
    a = Artwork.query.get_or_404(artwork_id)
    if a.user_id != current_user.id:
        abort(403)
    ent = user_entitlements(current_user)
    form = ArtworkForm(obj=a)
    _bind_discipline(form, a.discipline)
    form.series_id.choices = _series_choices_for(current_user)
    if request.method == 'GET':
        form.series_id.data = a.series_id or 0
        if a.year:
            form.year.data = str(a.year)
        if a.price is not None:
            form.price.data = a.price
    if form.validate_on_submit():
        a.title = form.title.data
        a.description = form.description.data
        a.price = float(form.price.data or 0)
        a.discipline = form.discipline.data or None
        a.medium = form.medium.data or None
        a.dimensions = form.dimensions.data or None
        a.format = form.format.data or None
        a.year = int(form.year.data) if form.year.data else None
        sid = form.series_id.data or 0
        if sid:
            s = Series.query.get(sid)
            a.series_id = s.id if s and s.user_id == current_user.id else None
        else:
            a.series_id = None
        if ent.get('private_sales'):
            a.early_access = bool(request.form.get('early_access'))
        name = _save_upload(form.image.data)
        if name:
            a.image = name
        _sync_curatorial_note(current_user, 'Œuvre mise à jour.')
        return redirect(url_for('main.dashboard'))
    return render_template('artwork_form.html', form=form, mode='edit', artwork=a, ent=ent)


@bp.route('/artwork/<int:artwork_id>/delete', methods=['POST'])
@login_required
def delete_artwork(artwork_id):
    a = Artwork.query.get_or_404(artwork_id)
    if a.user_id != current_user.id:
        abort(403)
    db.session.delete(a)
    _sync_curatorial_note(current_user, 'Œuvre supprimée.')
    return redirect(url_for('main.dashboard'))


# ---------- series CRUD ----------
@bp.route('/series/create', methods=['GET', 'POST'])
@login_required
def create_series():
    from .forms import SeriesForm
    form = SeriesForm()
    if form.validate_on_submit():
        s = Series(name=form.name.data,
                   description=form.description.data,
                   year=int(form.year.data) if form.year.data else None,
                   owner=current_user)
        name = _save_upload(form.cover.data)
        if name:
            s.cover = name
        db.session.add(s)
        _sync_curatorial_note(current_user, 'Série créée.')
        return redirect(url_for('main.dashboard'))
    return render_template('series_form.html', form=form, mode='create')


@bp.route('/series/<int:series_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_series(series_id):
    from .forms import SeriesForm
    s = Series.query.get_or_404(series_id)
    if s.user_id != current_user.id:
        abort(403)
    form = SeriesForm(obj=s)
    if request.method == 'GET' and s.year:
        form.year.data = str(s.year)
    if form.validate_on_submit():
        s.name = form.name.data
        s.description = form.description.data
        s.year = int(form.year.data) if form.year.data else None
        name = _save_upload(form.cover.data)
        if name:
            s.cover = name
        _sync_curatorial_note(current_user, 'Série mise à jour.')
        return redirect(url_for('main.dashboard'))
    return render_template('series_form.html', form=form, mode='edit', series=s)


@bp.route('/series/<int:series_id>/delete', methods=['POST'])
@login_required
def delete_series(series_id):
    s = Series.query.get_or_404(series_id)
    if s.user_id != current_user.id:
        abort(403)
    for a in list(s.artworks):
        a.series_id = None
    db.session.delete(s)
    _sync_curatorial_note(current_user, 'Série supprimée.')
    return redirect(url_for('main.dashboard'))


# ---------- profile ----------
@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    from .forms import ProfileForm
    form = ProfileForm(obj=current_user)
    _bind_discipline(form, current_user.discipline)
    if form.validate_on_submit():
        current_user.display_name = form.display_name.data or None
        current_user.email = form.email.data
        current_user.discipline = form.discipline.data or None
        current_user.location = form.location.data or None
        current_user.gallery = form.gallery.data or None
        current_user.description = form.description.data or None
        current_user.statement = form.statement.data or None
        current_user.bio = form.bio.data or None
        n = _save_upload(form.avatar.data)
        if n: current_user.avatar = n
        n = _save_upload(form.logo.data)
        if n: current_user.logo = n
        n = _save_upload(form.cover.data)
        if n: current_user.cover = n
        _sync_curatorial_note(current_user, 'Profil mis à jour.')
        return redirect(url_for('main.edit_profile'))
    from .entitlements import curatorial_quota_status
    return render_template('profile_edit.html', form=form, curatorial_quota=curatorial_quota_status(current_user))


@bp.route('/profile/curatorial/regenerate', methods=['POST'])
@login_required
def regenerate_curatorial():
    from .curatorial import refresh_curatorial_note
    note, err = refresh_curatorial_note(current_user)
    if err:
        flash(f'Impossible de générer la note : {err}', 'error')
    else:
        flash('Note curatoriale régénérée.', 'success')
    return redirect(url_for('main.edit_profile'))


@bp.route('/profile/password', methods=['GET', 'POST'])
@login_required
def change_password():
    from .forms import PasswordForm
    form = PasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Mot de passe actuel incorrect.', 'error')
            return redirect(url_for('main.change_password'))
        current_user.set_password(form.password.data)
        db.session.commit()
        flash('Mot de passe modifié.', 'success')
        return redirect(url_for('main.edit_profile'))
    return render_template('password_form.html', form=form)


@bp.route('/profile/subscription')
@login_required
def subscription():
    from .subscriptions import (
        plans_for_role, plan_for_role, normalize_plan, price_label, ROLE_LABELS,
    )
    from . import billing

    role = current_user.role or 'collectionneur'
    current_slug = normalize_plan(role, current_user.subscription_plan)
    if current_slug != (current_user.subscription_plan or 'free'):
        current_user.subscription_plan = current_slug
        db.session.commit()

    plans = plans_for_role(role)
    current_plan = plan_for_role(role, current_slug)
    from .stripe_connect import connect_status, payout_label_for_role
    return render_template(
        'subscription.html',
        plans=plans,
        current_plan=current_plan,
        current_slug=current_slug,
        role_label=ROLE_LABELS.get(role, role.capitalize()),
        price_label=price_label,
        stripe_ready=billing.stripe_ready(),
        connect=connect_status(current_user),
        connect_payout_label=payout_label_for_role(role),
    )


@bp.route('/profile/encaissements')
@login_required
def encaissements():
    from .stripe_connect import connect_status, payout_label_for_role, can_simulate_connect
    from . import billing
    if current_user.role not in ('artiste', 'galerie'):
        flash('Cette page est réservée aux artistes et galeries.', 'info')
        return redirect(url_for('main.dashboard'))
    return render_template(
        'encaissements.html',
        connect=connect_status(current_user),
        connect_payout_label=payout_label_for_role(current_user.role or ''),
        can_simulate_connect=can_simulate_connect(),
        stripe_ready=billing.stripe_ready(),
        dash_active='payouts',
    )


@bp.route('/profile/stripe-connect', methods=['GET', 'POST'])
@login_required
def stripe_connect_start():
    from .stripe_connect import connect_required_for, start_onboarding, connect_status
    st = connect_status(current_user)
    if st.get('needs_subscription'):
        flash('Activez d\'abord un abonnement avec vente en ligne.', 'warning')
        return redirect(url_for('main.subscription'))
    if not connect_required_for(current_user):
        flash('Stripe Connect n\'est pas requis pour votre formule actuelle.', 'info')
        return redirect(url_for('main.encaissements'))
    url, status = start_onboarding(current_user)
    if status == 'ok_demo':
        flash(
            'Compte de paiement activé. Votre portfolio public est maintenant visible sur le site.',
            'success',
        )
        return redirect(url_for('main.encaissements'))
    if status == 'ok' and url:
        return redirect(url)
    flash(status if status not in ('ok', 'ok_demo') else 'Connexion Stripe indisponible.', 'error')
    return redirect(url_for('main.encaissements'))


@bp.route('/profile/stripe-connect/simulate', methods=['POST'])
@login_required
def stripe_connect_simulate():
    from .stripe_connect import can_simulate_connect, demo_connect_user, connect_required_for
    if not can_simulate_connect():
        flash('Simulation non disponible en production.', 'error')
        return redirect(url_for('main.encaissements'))
    if not connect_required_for(current_user):
        flash('Activez d\'abord un abonnement portfolio.', 'warning')
        return redirect(url_for('main.subscription'))
    demo_connect_user(current_user)
    flash('Compte Stripe simulé — portfolio public activé (environnement local).', 'success')
    return redirect(url_for('main.encaissements'))


@bp.route('/profile/stripe-connect/callback')
@login_required
def stripe_connect_callback():
    from .stripe_connect import sync_connect_status, connect_ready
    sync_connect_status(current_user)
    if connect_ready(current_user):
        flash(
            'Compte Stripe connecté — vous pouvez encaisser vos ventes. Portfolio public activé.',
            'success',
        )
    else:
        flash(
            'Onboarding Stripe en cours — complétez les informations pour activer votre portfolio public.',
            'info',
        )
    return redirect(url_for('main.encaissements'))


@bp.route('/profile/stripe-connect/dashboard', methods=['POST'])
@login_required
def stripe_connect_dashboard():
    from .stripe_connect import connect_ready, create_login_link
    if not connect_ready(current_user) or not current_user.stripe_connect_id:
        return redirect(url_for('main.stripe_connect_start'))
    link = create_login_link(current_user.stripe_connect_id)
    if link:
        return redirect(link)
    flash('Dashboard Stripe indisponible.', 'warning')
    return redirect(url_for('main.encaissements'))


@bp.route('/profile/subscription/checkout', methods=['POST'])
@login_required
def subscription_checkout():
    from . import billing
    from .subscriptions import is_paid_plan, normalize_plan, role_plans_catalog

    plan_slug = request.form.get('plan', 'free')
    role = current_user.role or 'collectionneur'
    plan_slug = normalize_plan(role, plan_slug)
    if plan_slug not in role_plans_catalog().get(role, {}):
        flash('Formule invalide pour votre profil.', 'error')
        return redirect(url_for('main.subscription'))

    if not is_paid_plan(role, plan_slug):
        billing.demo_activate_plan(current_user, 'free')
        if current_user.stripe_subscription_id:
            billing.cancel_stripe_subscription(current_user, at_period_end=False)
        flash('Vous êtes sur la formule Découverte.', 'info')
        return redirect(url_for('main.subscription'))

    success = url_for('main.subscription_success', _external=True)
    cancel = url_for('main.subscription', _external=True)
    url = billing.create_checkout_session(current_user, plan_slug,
                                          success_url=success, cancel_url=cancel)
    if url:
        return redirect(url)

    if current_app.config.get('STRIPE_DEMO_MODE') or not current_app.config.get('STRIPE_ENABLED'):
        billing.demo_activate_plan(current_user, plan_slug)
        from .stripe_connect import connect_required_for
        msg = 'Abonnement activé (mode démo).'
        if connect_required_for(current_user):
            msg += ' Connectez Stripe pour encaisser et publier votre portfolio.'
        flash(msg, 'warning')
        return redirect(url_for('main.encaissements') if connect_required_for(current_user) else url_for('main.subscription'))

    flash('Impossible de lancer le paiement Stripe. Réessayez ou contactez le support.', 'error')
    return redirect(url_for('main.subscription'))


@bp.route('/profile/subscription/success')
@login_required
def subscription_success():
    from . import billing
    from .stripe_connect import connect_required_for, connect_ready
    session_id = request.args.get('session_id', '')
    if session_id and billing.fulfill_checkout_session(session_id):
        flash('Abonnement activé — merci pour votre confiance !', 'success')
        if connect_required_for(current_user) and not connect_ready(current_user):
            flash(
                'Dernière étape : connectez Stripe pour encaisser vos ventes et activer votre portfolio public.',
                'info',
            )
            return redirect(url_for('main.encaissements'))
    elif session_id:
        flash('Paiement en cours de confirmation…', 'info')
    return redirect(url_for('main.subscription'))


@bp.route('/profile/subscription/portal', methods=['POST'])
@login_required
def subscription_portal():
    from . import billing
    return_url = url_for('main.subscription', _external=True)
    url = billing.create_portal_session(current_user, return_url=return_url)
    if url:
        return redirect(url)
    flash('Portail de facturation indisponible pour le moment.', 'error')
    return redirect(url_for('main.subscription'))


@bp.route('/profile/subscription/cancel', methods=['POST'])
@login_required
def cancel_subscription():
    from . import billing
    from .subscriptions import normalize_plan

    role = current_user.role or 'collectionneur'
    if normalize_plan(role, current_user.subscription_plan) == 'free':
        flash('Vous êtes déjà sur la formule gratuite.', 'info')
        return redirect(url_for('main.subscription'))

    if current_user.stripe_subscription_id and billing.stripe_ready():
        if billing.cancel_stripe_subscription(current_user, at_period_end=True):
            flash('Votre abonnement sera actif jusqu\'à la fin de la période en cours.', 'warning')
        else:
            flash('Annulation impossible pour le moment. Contactez le support.', 'error')
    else:
        current_user.subscription_status = 'cancelled'
        db.session.commit()
        flash('Abonnement annulé.', 'warning')
    return redirect(url_for('main.subscription'))


@bp.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    from . import billing
    sig = request.headers.get('Stripe-Signature', '')
    ok, msg = billing.handle_webhook(request.get_data(), sig)
    if not ok:
        abort(400 if msg == 'invalid_signature' else 503)
    return '', 200


@bp.route('/dashboard/gallery-artist', methods=['POST'])
@login_required
def add_gallery_artist():
    from .models import GalleryArtist
    from .entitlements import user_entitlements

    if current_user.role != 'galerie':
        abort(403)
    ent = user_entitlements(current_user)
    limit = ent.get('gallery_artist_limit')
    if limit == 0:
        flash('Multi-artistes disponible à partir de Galerie Pro.', 'warning')
        return redirect(url_for('main.subscription'))
    if limit is not None:
        count = GalleryArtist.query.filter_by(gallery_id=current_user.id).count()
        if count >= limit:
            flash(f'Limite de {limit} artistes atteinte. Passez en Premium pour illimité.', 'warning')
            return redirect(url_for('main.subscription'))

    name = (request.form.get('name') or '').strip()
    if not name:
        flash('Nom de l\'artiste requis.', 'error')
        return redirect(url_for('main.dashboard'))
    ga = GalleryArtist(
        gallery_id=current_user.id,
        name=name,
        discipline=(request.form.get('discipline') or '').strip() or None,
        created_at=datetime.utcnow(),
    )
    db.session.add(ga)
    db.session.commit()
    flash(f'Artiste « {name} » ajouté à votre galerie.', 'success')
    return redirect(url_for('main.dashboard'))


@bp.route('/dashboard/gallery-artist/<int:ga_id>/delete', methods=['POST'])
@login_required
def delete_gallery_artist(ga_id):
    from .models import GalleryArtist
    ga = GalleryArtist.query.get_or_404(ga_id)
    if ga.gallery_id != current_user.id:
        abort(403)
    db.session.delete(ga)
    db.session.commit()
    flash('Artiste retiré.', 'info')
    return redirect(url_for('main.dashboard'))


@bp.route('/artwork/<int:artwork_id>/price-alert', methods=['POST'])
@login_required
def price_alert(artwork_id):
    from .models import PriceAlert
    from .entitlements import user_entitlements

    if current_user.role != 'collectionneur':
        abort(403)
    if not user_entitlements(current_user).get('price_alerts'):
        flash('Alertes prix disponibles à partir de la formule Membre.', 'warning')
        return redirect(url_for('main.subscription'))

    a = Artwork.query.get_or_404(artwork_id)
    existing = PriceAlert.query.filter_by(user_id=current_user.id, artwork_id=a.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('Alerte prix retirée.', 'info')
    else:
        db.session.add(PriceAlert(user_id=current_user.id, artwork_id=a.id, created_at=datetime.utcnow()))
        db.session.commit()
        flash('Alerte prix activée — vous serez notifié des changements.', 'success')
    return redirect(url_for('main.artwork_detail', artwork_id=a.id))


@bp.route('/wishlist/<token>')
def public_wishlist(token):
    """Wishlist partageable (collectionneurs Membre / Patron)."""
    user = User.query.filter_by(wishlist_share_token=token).first_or_404()
    from .entitlements import user_entitlements
    if not user_entitlements(user).get('shareable_wishlist'):
        abort(404)
    return render_template('wishlist_public.html', owner=user)


@bp.route('/dashboard/stats/export')
@login_required
def export_stats():
    from .entitlements import user_entitlements
    import csv
    from io import StringIO
    from flask import Response

    ent = user_entitlements(current_user)
    if ent.get('stats_level') != 'advanced':
        flash('Export disponible avec la formule Pro / Premium.', 'warning')
        return redirect(url_for('main.subscription'))

    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(['Titre', 'Prix', 'Vues', 'Statut', 'Discipline'])
    for a in current_user.artworks:
        w.writerow([a.title, a.price or '', a.view_count or 0, a.status or '', a.discipline or ''])
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=stats-artworks.csv'},
    )


# ---------- Aria (chatbot vitrine) ----------


@bp.route('/api/aria/chat', methods=['POST'])
def aria_chat():
    from .aria_assistant import chat, clear_history, aria_enabled

    if not aria_enabled():
        return jsonify({'error': 'Aria n\'est pas disponible pour le moment.'}), 503

    data = request.get_json(silent=True) or {}
    if data.get('reset'):
        clear_history()
        return jsonify({'ok': True})

    message = (data.get('message') or '').strip()
    result = chat(message, reset=bool(data.get('reset_conversation')))
    if result.get('error') and not result.get('reply'):
        status = 429 if 'Limite' in result['error'] else 400
        return jsonify(result), status
    return jsonify(result)

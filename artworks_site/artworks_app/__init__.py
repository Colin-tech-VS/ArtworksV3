from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login = LoginManager()
login.login_view = 'auth.login'


def create_app():
    app = Flask(__name__, static_folder='../static', template_folder='../templates')
    app.config.from_object('config.Config')

    db.init_app(app)
    login.init_app(app)

    # register blueprints
    from .routes import bp as main_bp
    from .auth import bp as auth_bp
    from .crm import bp as crm_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(crm_bp)

    with app.app_context():
        db.create_all()
        try:
            from .crm.auto_segments import ensure_system_segments, reclassify_all_users
            from .crm.email_templates_seed import ensure_default_email_templates
            ensure_system_segments()
            ensure_default_email_templates()
            reclassify_all_users()
        except Exception:
            pass

    from .billing import configure_stripe
    configure_stripe(app)

    from flask_login import current_user
    from .dashboard_ctx import role_meta as _role_meta

    @app.context_processor
    def inject_globals():
        from flask import request
        from .catalog import DISCIPLINES
        ctx = {
            'google_places_key': app.config.get('GOOGLE_PLACES_API_KEY', ''),
            'discipline_options': DISCIPLINES,
            'stripe_publishable_key': app.config.get('STRIPE_PUBLISHABLE_KEY', ''),
            'stripe_enabled': app.config.get('STRIPE_ENABLED') and not app.config.get('STRIPE_DEMO_MODE'),
            'google_oauth_enabled': bool(
                app.config.get('GOOGLE_OAUTH_CLIENT_ID')
                and app.config.get('GOOGLE_OAUTH_CLIENT_SECRET')
            ),
            'current_user': current_user,
        }
        if current_user.is_authenticated:
            ctx['role_meta'] = _role_meta(current_user)
            from .subscriptions import plan_for_role, normalize_plan
            _role = current_user.role or 'collectionneur'
            _slug = normalize_plan(_role, current_user.subscription_plan)
            ctx['user_plan'] = plan_for_role(_role, _slug)
            from .entitlements import user_entitlements, effective_plan
            ctx['user_ent'] = user_entitlements(current_user)
            ctx['effective_plan'] = effective_plan(current_user)
            from .crm.auth import is_staff_user
            ctx['is_staff_user'] = is_staff_user(current_user)
            from .favorites import favorite_ids_for_user, favorite_count_for_user
            ctx['user_favorite_ids'] = favorite_ids_for_user(current_user)
            ctx['user_favorite_count'] = favorite_count_for_user(current_user)
        else:
            ctx['is_staff_user'] = False
            ctx['user_favorite_ids'] = []
            ctx['user_favorite_count'] = 0
        if current_user.is_authenticated and current_user.role in ('artiste', 'galerie'):
            from .stripe_connect import connect_status, payout_label_for_role, can_simulate_connect
            ctx['connect'] = connect_status(current_user)
            ctx['connect_payout_label'] = payout_label_for_role(current_user.role or '')
            ctx['can_simulate_connect'] = can_simulate_connect()
        else:
            ctx['connect'] = {
                'required': False, 'ready': True, 'pending': False,
                'missing': False, 'has_account': False, 'show_section': False,
                'needs_subscription': False, 'needs_connect': False,
                'can_connect': False, 'portfolio_public_blocked': False,
            }
            ctx['connect_payout_label'] = ''
            ctx['can_simulate_connect'] = False
        from .models import CmsPage
        ctx['cms_nav_pages'] = CmsPage.query.filter_by(published=True, show_in_nav=True).order_by(CmsPage.title).all()
        from .pricing_store import pricing_context
        ctx['pricing'] = pricing_context()
        from .aria_assistant import aria_enabled, aria_show_on_vitrine
        ctx['aria_enabled'] = aria_enabled() and aria_show_on_vitrine(request.endpoint, request.blueprint)
        ctx['site_url'] = (app.config.get('SITE_URL') or '').rstrip('/') or 'https://artworksdigital.fr'
        from .storage import img_resolve_config
        ctx['img_resolve'] = img_resolve_config()
        if request.blueprint == 'crm':
            from .crm.crm_ctx import (
                ARTWORK_STATUS_LABELS, CAMPAIGN_STATUS_LABELS, NAV_META,
                PLAN_LABELS, ROLE_LABELS, SUB_STATUS_LABELS, crm_nav_counts,
            )
            ctx.update({
                'crm_counts': crm_nav_counts(),
                'crm_role_labels': ROLE_LABELS,
                'crm_plan_labels': PLAN_LABELS,
                'crm_sub_labels': SUB_STATUS_LABELS,
                'crm_art_labels': ARTWORK_STATUS_LABELS,
                'crm_camp_labels': CAMPAIGN_STATUS_LABELS,
                'crm_nav_meta': NAV_META,
            })
        return ctx

    # --- template helpers ---
    from flask import url_for

    def img_url(value, placeholder='demo/art-01.jpg'):
        """Resolve an artwork/profile image path to a public URL (fallback static si absent)."""
        from .storage import public_url
        return public_url(value) or url_for('static', filename=placeholder)

    app.jinja_env.globals['img_url'] = img_url

    @app.after_request
    def _analytics_track(response):
        from flask import request
        if request.method != 'GET' or response.status_code >= 400:
            return response
        if request.blueprint in ('crm', 'auth') or request.path.startswith('/static'):
            return response
        if request.path.startswith('/webhooks'):
            return response
        if request.path.startswith('/api/aria'):
            return response
        try:
            from .analytics_track import track_event
            track_event('page_view', path=request.path)
        except Exception:
            pass
        return response

    return app

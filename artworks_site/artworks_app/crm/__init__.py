from flask import Blueprint

bp = Blueprint('crm', __name__, url_prefix='/crm')

from . import routes, social_routes  # noqa: E402, F401

from .crm_ctx import (
    ARTWORK_STATUS_LABELS,
    CAMPAIGN_STATUS_LABELS,
    NAV_META,
    PLAN_LABELS,
    ROLE_LABELS,
    SUB_STATUS_LABELS,
    crm_nav_counts,
)


@bp.context_processor
def inject_crm_globals():
    return {
        'crm_counts': crm_nav_counts(),
        'crm_role_labels': ROLE_LABELS,
        'crm_plan_labels': PLAN_LABELS,
        'crm_sub_labels': SUB_STATUS_LABELS,
        'crm_art_labels': ARTWORK_STATUS_LABELS,
        'crm_camp_labels': CAMPAIGN_STATUS_LABELS,
        'crm_nav_meta': NAV_META,
    }

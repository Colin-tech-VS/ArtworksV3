"""CRM analytics aggregates."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func

from ..models import Artwork, EmailCampaign, PriceAlert, User, db
from ..subscriptions import role_plans_catalog


def crm_overview():
    users_total = User.query.filter(User.is_staff.is_(False), User.role != 'admin').count()
    artworks_total = Artwork.query.count()
    views_total = db.session.query(func.coalesce(func.sum(Artwork.view_count), 0)).scalar() or 0
    alerts_total = PriceAlert.query.count()

    by_role = dict(
        db.session.query(User.role, func.count(User.id))
        .filter(User.is_staff.is_(False))
        .group_by(User.role)
        .all()
    )

    by_plan = dict(
        db.session.query(User.subscription_plan, func.count(User.id))
        .filter(User.is_staff.is_(False))
        .group_by(User.subscription_plan)
        .all()
    )

    paid_users = User.query.filter(
        User.is_staff.is_(False),
        User.subscription_plan != 'free',
        User.subscription_status == 'active',
    ).count()

    mrr_cents = 0
    catalog = role_plans_catalog()
    for role, plans in catalog.items():
        role_users = User.query.filter(
            User.role == role,
            User.is_staff.is_(False),
            User.subscription_status == 'active',
        ).all()
        for u in role_users:
            plan = plans.get(u.subscription_plan or 'free', {})
            mrr_cents += plan.get('price_cents', 0) or 0

    top_artworks = (
        Artwork.query.order_by(Artwork.view_count.desc())
        .limit(8)
        .all()
    )

    recent_users = (
        User.query.filter(User.is_staff.is_(False))
        .order_by(User.id.desc())
        .limit(6)
        .all()
    )

    campaigns_sent = EmailCampaign.query.filter_by(status='sent').count()

    return {
        'users_total': users_total,
        'artworks_total': artworks_total,
        'views_total': int(views_total),
        'alerts_total': alerts_total,
        'paid_users': paid_users,
        'mrr_eur': mrr_cents / 100,
        'by_role': by_role,
        'by_plan': by_plan,
        'top_artworks': top_artworks,
        'recent_users': recent_users,
        'campaigns_sent': campaigns_sent,
    }


def analytics_detail():
    overview = crm_overview()

    status_breakdown = dict(
        db.session.query(Artwork.status, func.count(Artwork.id))
        .group_by(Artwork.status)
        .all()
    )

    discipline_breakdown = dict(
        db.session.query(Artwork.discipline, func.count(Artwork.id))
        .filter(Artwork.discipline.isnot(None))
        .group_by(Artwork.discipline)
        .order_by(func.count(Artwork.id).desc())
        .limit(10)
        .all()
    )

    sub_status = dict(
        db.session.query(User.subscription_status, func.count(User.id))
        .filter(User.is_staff.is_(False))
        .group_by(User.subscription_status)
        .all()
    )

    return {**overview, 'status_breakdown': status_breakdown,
            'discipline_breakdown': discipline_breakdown, 'sub_status': sub_status}

"""Analytics events — style GA4 (sessions, pages, sources)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from flask import request, session
from sqlalchemy import func

from . import db
from .models import AnalyticsEvent, Artwork, User


def _session_id():
    sid = session.get('analytics_sid')
    if not sid:
        sid = uuid.uuid4().hex[:16]
        session['analytics_sid'] = sid
    return sid


def track_event(event_type: str, *, path: str | None = None, title: str | None = None,
                artwork_id: int | None = None, meta: dict | None = None):
    from flask_login import current_user
    try:
        ref = (request.referrer or '')[:500]
        source = 'direct'
        if ref:
            if 'google' in ref:
                source = 'google'
            elif 'bing' in ref:
                source = 'bing'
            elif 'instagram' in ref:
                source = 'instagram'
            elif 'facebook' in ref or 'fb.' in ref:
                source = 'facebook'
            elif request.host_url.rstrip('/') not in ref:
                source = 'referral'
            else:
                source = 'internal'
        uid = current_user.id if current_user.is_authenticated else None
        ev = AnalyticsEvent(
            event_type=event_type,
            path=(path or request.path or '/')[:256],
            page_title=(title or '')[:200],
            session_id=_session_id(),
            user_id=uid,
            referrer=ref,
            source=source,
            artwork_id=artwork_id,
            meta_json=__import__('json').dumps(meta or {}),
            created_at=datetime.utcnow(),
        )
        db.session.add(ev)
        db.session.commit()
    except Exception:
        db.session.rollback()


def ga4_analytics(days: int = 30):
    since = datetime.utcnow() - timedelta(days=days)
    since_24h = datetime.utcnow() - timedelta(hours=24)
    since_30m = datetime.utcnow() - timedelta(minutes=30)

    base = AnalyticsEvent.query.filter(AnalyticsEvent.created_at >= since)

    active_now = (
        AnalyticsEvent.query.filter(AnalyticsEvent.created_at >= since_30m)
        .with_entities(AnalyticsEvent.session_id)
        .distinct()
        .count()
    )
    users_24h = (
        AnalyticsEvent.query.filter(AnalyticsEvent.created_at >= since_24h)
        .with_entities(AnalyticsEvent.session_id)
        .distinct()
        .count()
    )
    page_views = base.filter_by(event_type='page_view').count()
    sessions = base.with_entities(AnalyticsEvent.session_id).distinct().count()

    # Daily series
    daily_raw = (
        db.session.query(
            func.date(AnalyticsEvent.created_at),
            func.count(AnalyticsEvent.id),
        )
        .filter(AnalyticsEvent.created_at >= since, AnalyticsEvent.event_type == 'page_view')
        .group_by(func.date(AnalyticsEvent.created_at))
        .all()
    )
    daily = {str(d): cnt for d, cnt in daily_raw}

    # Top pages
    top_pages = (
        db.session.query(AnalyticsEvent.path, func.count(AnalyticsEvent.id).label('cnt'))
        .filter(AnalyticsEvent.created_at >= since, AnalyticsEvent.event_type == 'page_view')
        .group_by(AnalyticsEvent.path)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .limit(12)
        .all()
    )

    # Sources (acquisition)
    sources = dict(
        db.session.query(AnalyticsEvent.source, func.count(AnalyticsEvent.id))
        .filter(AnalyticsEvent.created_at >= since)
        .group_by(AnalyticsEvent.source)
        .all()
    )

    # Events breakdown
    events_by_type = dict(
        db.session.query(AnalyticsEvent.event_type, func.count(AnalyticsEvent.id))
        .filter(AnalyticsEvent.created_at >= since)
        .group_by(AnalyticsEvent.event_type)
        .all()
    )

    # Artwork views from events + legacy view_count
    artwork_views = (
        db.session.query(Artwork.title, Artwork.view_count, Artwork.id)
        .order_by(Artwork.view_count.desc())
        .limit(10)
        .all()
    )

    new_users = User.query.filter(User.is_staff.is_(False), User.role != 'admin').count()

    # Fill missing days for chart
    labels, values = [], []
    for i in range(days):
        d = (datetime.utcnow() - timedelta(days=days - 1 - i)).date()
        labels.append(d.strftime('%d/%m'))
        values.append(daily.get(str(d), daily.get(d, 0)))

    bounce_proxy = 0
    if sessions:
        single_page = (
            db.session.query(AnalyticsEvent.session_id)
            .filter(AnalyticsEvent.created_at >= since, AnalyticsEvent.event_type == 'page_view')
            .group_by(AnalyticsEvent.session_id)
            .having(func.count(AnalyticsEvent.id) == 1)
            .count()
        )
        bounce_proxy = round(single_page / sessions * 100) if sessions else 0

    pages_per_session = round(page_views / sessions, 2) if sessions else 0

    return {
        'days': days,
        'active_now': active_now,
        'users_24h': users_24h,
        'page_views': page_views,
        'sessions': sessions,
        'bounce_rate': bounce_proxy,
        'pages_per_session': pages_per_session,
        'chart_labels': labels,
        'chart_values': values,
        'top_pages': top_pages,
        'sources': sources,
        'events_by_type': events_by_type,
        'artwork_views': artwork_views,
        'users_total': new_users,
    }

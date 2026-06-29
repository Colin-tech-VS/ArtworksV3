"""Tarifs & commission — source live (CRM) avec repli sur les défauts code."""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from . import db

SETTING_COMMISSION = 'commission_rate'
SETTING_PLAN_PRICES = 'plan_prices'


def _default_commission_rate() -> float:
    try:
        from flask import has_app_context, current_app
        if has_app_context():
            return float(current_app.config.get('COMMISSION_RATE', 0.18))
    except (RuntimeError, ImportError, TypeError, ValueError):
        pass
    return 0.18


def _get_row(key: str):
    from .models import PlatformSetting
    return PlatformSetting.query.get(key)


def _read_json(key: str) -> Any | None:
    row = _get_row(key)
    if not row:
        return None
    try:
        return json.loads(row.value_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def get_commission_rate() -> float:
    val = _read_json(SETTING_COMMISSION)
    if val is not None:
        try:
            rate = float(val)
            if 0 <= rate <= 1:
                return rate
        except (TypeError, ValueError):
            pass
    return _default_commission_rate()


def set_commission_rate(rate: float, *, user_id: int | None = None) -> None:
    from datetime import datetime
    from .models import PlatformSetting
    rate = max(0.0, min(1.0, float(rate)))
    row = PlatformSetting.query.get(SETTING_COMMISSION)
    if not row:
        row = PlatformSetting(key=SETTING_COMMISSION)
        db.session.add(row)
    row.value_json = json.dumps(rate)
    row.updated_at = datetime.utcnow()
    row.updated_by_id = user_id
    db.session.commit()


def _plan_key(role: str, slug: str) -> str:
    return f'{role}.{slug}'


def get_plan_prices_overrides() -> dict[str, int]:
    raw = _read_json(SETTING_PLAN_PRICES)
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in raw.items():
        try:
            out[str(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return out


def get_plan_price_cents(role: str, slug: str, *, default: int) -> int:
    key = _plan_key(role, slug)
    override = get_plan_prices_overrides().get(key)
    if override is not None and override >= 0:
        return override
    return default


def set_plan_prices(updates: dict[str, int], *, user_id: int | None = None) -> None:
    from datetime import datetime
    from .models import PlatformSetting
    current = get_plan_prices_overrides()
    for k, v in updates.items():
        try:
            cents = int(v)
        except (TypeError, ValueError):
            continue
        if cents < 0:
            continue
        current[str(k)] = cents
    row = PlatformSetting.query.get(SETTING_PLAN_PRICES)
    if not row:
        row = PlatformSetting(key=SETTING_PLAN_PRICES)
        db.session.add(row)
    row.value_json = json.dumps(current)
    row.updated_at = datetime.utcnow()
    row.updated_by_id = user_id
    db.session.commit()


def commission_percent_label() -> str:
    pct = int(round(get_commission_rate() * 100))
    return f'{pct} %'


def cents_to_euros_label(cents: int) -> str:
    if cents <= 0:
        return 'Gratuit'
    euros = cents / 100
    if euros == int(euros):
        return f'{int(euros)} €'
    return f'{euros:.2f} €'.replace('.', ',')


def apply_commission_placeholders(text: str) -> str:
    return (text or '').replace('{commission}', commission_percent_label())


def finalize_plan(role: str, plan: dict[str, Any]) -> dict[str, Any]:
    """Applique prix live + libellé commission dynamique."""
    from .subscriptions import _PLAN_TEMPLATES

    p = deepcopy(plan)
    slug = p.get('slug') or 'free'
    default_cents = int(_PLAN_TEMPLATES.get(role, {}).get(slug, {}).get('price_cents') or 0)
    p['price_cents'] = get_plan_price_cents(role, slug, default=default_cents)
    p['features'] = [apply_commission_placeholders(f) for f in p.get('features', [])]
    p['missing'] = [apply_commission_placeholders(f) for f in p.get('missing', [])]
    if p.get('tagline'):
        p['tagline'] = apply_commission_placeholders(p['tagline'])
    return p


def role_plans_catalog() -> dict[str, dict[str, dict[str, Any]]]:
    from .subscriptions import _PLAN_TEMPLATES

    catalog = {}
    for role, plans in _PLAN_TEMPLATES.items():
        catalog[role] = {slug: finalize_plan(role, tpl) for slug, tpl in plans.items()}
    return catalog


def editable_plans_for_crm() -> list[dict[str, Any]]:
    """Liste des formules payantes pour l'UI CRM."""
    from .subscriptions import ROLE_LABELS, _PLAN_TEMPLATES

    rows = []
    overrides = get_plan_prices_overrides()
    for role, plans in _PLAN_TEMPLATES.items():
        for slug, tpl in plans.items():
            default = int(tpl.get('price_cents') or 0)
            if default <= 0 and slug == 'free':
                continue
            key = _plan_key(role, slug)
            effective = get_plan_price_cents(role, slug, default=default)
            rows.append({
                'role': role,
                'role_label': ROLE_LABELS.get(role, role),
                'slug': slug,
                'name': tpl.get('name', slug),
                'field_name': f'price_{role}_{slug}',
                'default_cents': default,
                'effective_cents': effective,
                'is_overridden': key in overrides,
                'default_label': cents_to_euros_label(default),
                'effective_label': cents_to_euros_label(effective),
            })
    return rows


def pricing_context() -> dict[str, Any]:
    """Contexte Jinja — prix & commission live."""
    from .subscriptions import plan_for_role

    portfolio = plan_for_role('artiste', 'portfolio')
    return {
        'commission_rate': get_commission_rate(),
        'commission_label': commission_percent_label(),
        'portfolio_price_label': cents_to_euros_label(portfolio['price_cents'] if portfolio else 999),
        'portfolio_price_cents': portfolio['price_cents'] if portfolio else 999,
    }

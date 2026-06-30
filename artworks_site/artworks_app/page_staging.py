"""Brouillons page (Aria + aperçu créateur) — persistés en base utilisateur."""
from __future__ import annotations

import json

from . import db


def load_page_draft(user) -> dict | None:
    raw = getattr(user, 'page_draft_json', None)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def save_page_draft(user, draft: dict) -> None:
    user.page_draft_json = json.dumps(draft, ensure_ascii=False)
    db.session.commit()


def clear_page_draft(user, *, restore_baseline: bool = False) -> None:
    draft = load_page_draft(user)
    if restore_baseline and draft and draft.get('baseline_layout') is not None:
        user.page_layout_json = draft['baseline_layout']
        user.page_published = bool(draft.get('baseline_published', False))
    user.page_draft_json = None
    db.session.commit()


def has_page_draft(user) -> bool:
    draft = load_page_draft(user)
    return bool(draft and isinstance(draft.get('layout'), dict))


def draft_element_count(user) -> int:
    draft = load_page_draft(user)
    if not draft:
        return 0
    layout = draft.get('layout') or {}
    elements = layout.get('elements')
    return len(elements) if isinstance(elements, list) else 0


def load_preview_temp(user) -> dict | None:
    raw = getattr(user, 'page_preview_json', None)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def save_preview_temp(user, temp: dict) -> None:
    user.page_preview_json = json.dumps(temp, ensure_ascii=False)
    db.session.commit()


def clear_preview_temp(user) -> None:
    user.page_preview_json = None
    db.session.commit()


def clear_all_staging(user, *, restore_baseline: bool = False) -> None:
    clear_page_draft(user, restore_baseline=restore_baseline)
    clear_preview_temp(user)

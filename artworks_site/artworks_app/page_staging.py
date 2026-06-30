"""Brouillons page (Aria + aperçu créateur) — stockés en base pour éviter la limite cookie session."""
from __future__ import annotations

import json
from typing import Any

from flask import session

from . import db


def load_page_draft(user) -> dict | None:
    raw = getattr(user, 'page_draft_json', None)
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except (ValueError, TypeError):
            pass
    draft = session.get('page_draft')
    return draft if isinstance(draft, dict) else None


def save_page_draft(user, draft: dict) -> None:
    user.page_draft_json = json.dumps(draft, ensure_ascii=False)
    session.pop('page_draft', None)
    session.modified = True
    db.session.commit()


def clear_page_draft(user, *, restore_baseline: bool = False) -> None:
    draft = load_page_draft(user)
    if restore_baseline and draft and draft.get('baseline_layout') is not None:
        user.page_layout_json = draft['baseline_layout']
        user.page_published = bool(draft.get('baseline_published', False))
    user.page_draft_json = None
    session.pop('page_draft', None)
    session.modified = True
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
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except (ValueError, TypeError):
            pass
    temp = session.get('page_preview_temp')
    return temp if isinstance(temp, dict) else None


def save_preview_temp(user, temp: dict) -> None:
    user.page_preview_json = json.dumps(temp, ensure_ascii=False)
    session.pop('page_preview_temp', None)
    session.modified = True
    db.session.commit()


def clear_preview_temp(user) -> None:
    user.page_preview_json = None
    session.pop('page_preview_temp', None)
    session.modified = True
    db.session.commit()


def clear_all_staging(user, *, restore_baseline: bool = False) -> None:
    clear_page_draft(user, restore_baseline=restore_baseline)
    clear_preview_temp(user)

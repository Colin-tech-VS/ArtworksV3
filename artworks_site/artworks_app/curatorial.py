"""Régénération automatique de la note curatoriale."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import current_app

from .ai import CuratorialAIError, generate_curatorial_note

_log = logging.getLogger(__name__)


def refresh_curatorial_note(user, *, commit=True):
    """Regénère et enregistre la note curatoriale pour un utilisateur.

    Retourne (note, error_message). error_message est None en cas de succès.
    """
    from .entitlements import can_regenerate_curatorial, record_curatorial_use

    ok, err = can_regenerate_curatorial(user)
    if not ok:
        return None, err

    if not current_app.config.get('MISTRAL_API_KEY'):
        return None, 'MISTRAL_API_KEY non configurée.'

    artworks = list(user.artworks)
    series = list(user.series)

    try:
        note = generate_curatorial_note(user, artworks, series)
    except CuratorialAIError as e:
        _log.warning('Curatorial note failed for user %s: %s', user.id, e)
        return None, str(e)
    except Exception as e:
        _log.exception('Unexpected curatorial error for user %s', user.id)
        return None, 'Erreur lors de la génération de la note curatoriale.'

    note = (note or '').strip()
    if not note:
        return None, 'La note générée est vide.'

    user.curatorial_note = note
    user.curatorial_note_at = datetime.utcnow()
    record_curatorial_use(user)

    if commit:
        from . import db
        db.session.commit()

    return note, None

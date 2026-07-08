"""Génération de contenus email via Mistral (CRM)."""
from __future__ import annotations

import json
import re

from ..ai import chat_completions, CuratorialAIError

_EMAIL_SYSTEM = (
    'Tu es rédacteur email marketing pour Artworks Digital, marketplace d\'art contemporain pour artistes, galeries et collectionneurs. '
    'Rédige des emails HTML concis, élégants, compatibles clients mail. '
    'Utilise des balises simples : h1, p, ul/li, strong, em. Style éditorial haut de gamme. '
    'Variables de personnalisation autorisées : {{name}}, {{email}}, {{username}}, {{role}}, {{role_label}}, {{plan}}. '
    'Réponds UNIQUEMENT en JSON valide avec les clés : '
    'subject (≤ 80 car.), preview_text (preheader ≤ 120 car.), body_html (corps HTML sans wrapper).'
)


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return json.loads(text)


def generate_email_content(*, brief: str, tone: str = 'editorial', email_type: str = 'marketing') -> dict:
    brief = (brief or '').strip()
    if len(brief) < 5:
        raise CuratorialAIError('Décrivez le contenu de l\'email (minimum 5 caractères).')
    user_msg = (
        f'Type : {email_type}\n'
        f'Brief : {brief}\n'
        f'Ton : {tone}\n'
        'Génère un email Artworks prêt à envoyer.'
    )
    raw = chat_completions(
        [
            {'role': 'system', 'content': _EMAIL_SYSTEM},
            {'role': 'user', 'content': user_msg},
        ],
        temperature=0.5,
        max_tokens=1800,
        model=None,
        timeout=60,
    )
    try:
        data = _parse_json(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise CuratorialAIError('Réponse IA illisible — réessayez.') from exc
    return {
        'subject': (data.get('subject') or 'Message Artworks')[:200],
        'preview_text': (data.get('preview_text') or '')[:200],
        'body_html': data.get('body_html') or data.get('body') or '',
    }

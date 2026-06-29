"""Génération de pages CMS SEO via Mistral."""
from __future__ import annotations

import json
import re

from .ai import chat_completions, CuratorialAIError

_SEO_SYSTEM = (
    'Tu es expert SEO et rédacteur web pour Artworks Salon, plateforme d\'art contemporain '
    'orientée galeries et collectionneurs. '
    'Objectif unique : référencement naturel maximal (Google, Bing) et conversion éditoriale. '
    'Règles strictes : '
    '1) Contenu original, sémantique riche, mots-clés intégrés naturellement (pas de bourrage). '
    '2) Structure HTML sémantique : un seul <h1>, sous-titres <h2>/<h3>, paragraphes <p>, listes <ul> si pertinent. '
    '3) Meta title ≤ 60 caractères, meta description 140–160 caractères, incitatifs au clic. '
    '4) Slug URL court, minuscules, tirets, sans accents. '
    '5) Excerpt = chapô 150–200 caractères pour snippet. '
    '6) Ton : expert, accessible, crédible — art contemporain, collection, artistes, galeries. '
    '7) Pas de fausses promesses, pas de prix inventés, pas de noms d\'artistes fictifs. '
    '8) Inclure des ancres internes suggérées en commentaire HTML <!-- lien: /explorer -->. '
    'Réponds UNIQUEMENT en JSON valide avec les clés : '
    'title, slug, excerpt, meta_title, meta_description, body_html '
    '(body_html = contenu HTML complet de la page, 400–900 mots selon le brief).'
)


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return json.loads(text)


def generate_seo_page(*, topic: str, keywords: str = '', tone: str = 'expert', lang: str = 'fr') -> dict:
    topic = (topic or '').strip()
    if len(topic) < 5:
        raise CuratorialAIError('Décrivez le sujet de la page (minimum 5 caractères).')
    kw = (keywords or '').strip()
    user_msg = (
        f'Langue : {lang}\n'
        f'Sujet / brief : {topic}\n'
        f'Mots-clés SEO cibles : {kw or "(déduire du sujet — art contemporain, marketplace, collection)"}\n'
        f'Ton : {tone}\n'
        'Génère une page optimisée SEO pour Artworks.'
    )
    raw = chat_completions(
        [
            {'role': 'system', 'content': _SEO_SYSTEM},
            {'role': 'user', 'content': user_msg},
        ],
        temperature=0.45,
        max_tokens=2800,
        model=None,
        timeout=90,
    )
    try:
        data = _parse_json(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise CuratorialAIError('Réponse IA illisible — réessayez avec un brief plus court.') from exc
    slug = re.sub(r'[^a-z0-9-]', '', (data.get('slug') or '').lower().strip())
    slug = re.sub(r'-+', '-', slug).strip('-')[:120]
    if not slug:
        slug = re.sub(r'[^a-z0-9]+', '-', topic.lower())[:80].strip('-')
    return {
        'title': (data.get('title') or topic)[:200],
        'slug': slug,
        'excerpt': (data.get('excerpt') or '')[:500],
        'meta_title': (data.get('meta_title') or data.get('title') or topic)[:200],
        'meta_description': (data.get('meta_description') or '')[:320],
        'body': data.get('body_html') or data.get('body') or '',
    }

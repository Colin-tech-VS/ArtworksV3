"""Génération textes posts sociaux via Mistral (port V2 generate_social_post)."""
from __future__ import annotations

from ..ai import chat_completions, CuratorialAIError

_LANG_LABEL = {'fr': 'français', 'en': 'English', 'ja': '日本語', 'ko': '한국어'}


def generate_social_post(
    *,
    subject: str,
    keywords: str = '',
    tone: str = 'inspirant',
    destination_url: str = '',
    language: str = 'fr',
    manual: bool = False,
) -> dict:
    lang = (language or 'fr').lower()
    if lang not in ('fr', 'en', 'ja', 'ko'):
        lang = 'fr'
    if manual:
        base = subject.strip()
        if destination_url:
            base = f'{base}\n\n{destination_url}'
        return {
            'facebook_text': base,
            'instagram_text': base,
            'pinterest_text': base[:500],
            'deviantart_title': subject[:50],
            'deviantart_description': base[:500],
        }

    site = (
        'Artworks Digital — marketplace d\'art contemporain pour artistes, galeries et collectionneurs. '
        'Portfolio payant, commission 18% à la vente.'
    )

    sys_fb = (
        'Tu es community manager Artworks. Post Facebook engageant, 200-400 caractères, '
        f'ton {tone}, langue {_LANG_LABEL.get(lang, lang)}. '
        'Hook accrocheur, 1-2 emojis, 2-3 hashtags, CTA vers le lien. '
        'Renvoie UNIQUEMENT le texte du post.'
    )
    user_fb = f'Contexte : {site}\nSujet : {subject}\n'
    if keywords:
        user_fb += f'Mots-clés : {keywords}\n'
    if destination_url:
        user_fb += f'Lien CTA : {destination_url}\n'

    sys_ig = (
        'Tu es community manager Instagram Artworks. Caption originale, '
        f'ton {tone}, langue {_LANG_LABEL.get(lang, lang)}. '
        'Hook ligne 1, 2-3 phrases, 18-25 hashtags, termine par 📌 Lien en bio. '
        'Renvoie UNIQUEMENT la caption.'
    )
    user_ig = f'Contexte : {site}\nSujet : {subject}\n'
    if keywords:
        user_ig += f'Mots-clés : {keywords}\n'

    try:
        fb = chat_completions(
            [{'role': 'system', 'content': sys_fb}, {'role': 'user', 'content': user_fb}],
            temperature=0.85, max_tokens=250, timeout=45,
        ).strip().strip('"').strip('«»')
    except CuratorialAIError:
        fb = f'🎨 {subject}\n\n👉 {destination_url}\n\n#art #artworks'

    try:
        ig = chat_completions(
            [{'role': 'system', 'content': sys_ig}, {'role': 'user', 'content': user_ig}],
            temperature=0.9, max_tokens=500, timeout=45,
        ).strip().strip('"').strip('«»')
    except CuratorialAIError:
        ig = f'🎨 {subject}\n\n📌 Lien en bio\n\n#art #contemporaryart #artworks'

    pt = fb[:500]
    return {
        'facebook_text': fb,
        'instagram_text': ig,
        'pinterest_text': pt,
        'deviantart_title': subject[:50],
        'deviantart_description': fb[:500],
    }

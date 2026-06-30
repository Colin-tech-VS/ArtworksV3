"""Construction déterministe de pages (mode intelligent) — sans dépendre du LLM."""
from __future__ import annotations

import re

from .page_blocks import strip_markdown_for_display

_SENTENCE_RE = re.compile(r'[^.!?]+[.!?]+|[^.!?]+$')


def _first_sentences(text: str, n: int = 2, *, max_len: int = 320) -> str:
    t = strip_markdown_for_display(text)
    if not t:
        return ''
    parts = [s.strip() for s in _SENTENCE_RE.findall(t) if s.strip()]
    out = ' '.join(parts[:n])
    if len(out) > max_len:
        out = out[: max_len - 1].rsplit(' ', 1)[0] + '…'
    return out


def _heading(text: str, *, size: int = 36, align: str = 'left') -> dict:
    return {
        'type': 'heading',
        'text': strip_markdown_for_display(text)[:140],
        'font': 'display',
        'size': size,
        'align': align,
        'color': '#1a2832',
    }


def _text(text: str, *, size: int = 16, align: str = 'left') -> dict:
    return {
        'type': 'text',
        'text': strip_markdown_for_display(text)[:1200],
        'font': 'serif',
        'size': size,
        'align': align,
        'color': '#3d4f58',
    }


def _button(label: str, href: str, *, bg: str = '#b8734a') -> dict:
    return {
        'type': 'button',
        'text': strip_markdown_for_display(label)[:80],
        'href': href,
        'bg': bg,
        'color': '#ffffff',
        'font': 'sans',
        'size': 15,
    }


def _cover_block(user) -> dict | None:
    from .aria_tools import _image_url
    for field in ('cover', 'logo', 'avatar'):
        url = _image_url(getattr(user, field, None))
        if url:
            return {'type': 'image', 'src': url, 'width': 880, 'height': 360}
    return None


def _artwork_images(page_data: dict) -> list[str]:
    urls = [u for u in (page_data.get('artwork_images') or []) if u]
    if urls:
        return urls[:6]
    for art in page_data.get('artworks') or []:
        img = art.get('image') if isinstance(art, dict) else None
        if img:
            urls.append(img)
    return urls[:6]


def _profile_bits(page_data: dict) -> tuple[str, str, str, str]:
    profile = page_data.get('profile') or {}
    name = (profile.get('display_name') or '').strip() or 'Ma galerie'
    discipline = (profile.get('discipline') or '').strip()
    location = (profile.get('location') or '').strip()
    bio = (profile.get('bio') or profile.get('statement') or '').strip()
    return name, discipline, location, bio


def build_selling_page_blocks(user, page_data: dict) -> list[dict]:
    """Page commerciale : accroche, sélection œuvres, appels à l'action."""
    name, discipline, location, bio = _profile_bits(page_data)
    images = _artwork_images(page_data)
    arts = page_data.get('artworks') or []
    page_url = page_data.get('page_url') or f'/artist/{user.id}'

    if bio:
        accroche = _first_sentences(bio, 2, max_len=300)
    else:
        bits = [b for b in (discipline, location) if b]
        accroche = (
            f'Découvrez une sélection exigeante{" — " + ", ".join(bits) if bits else ""}. '
            'Chaque œuvre est choisie pour sa singularité et sa qualité de fabrication.'
        )

    blocks: list[dict] = []
    cover = _cover_block(user)
    if cover:
        blocks.append(cover)

    blocks.append(_heading(name, size=44, align='center'))
    subtitle = ' · '.join(x for x in (discipline, location) if x)
    if subtitle:
        blocks.append(_text(subtitle, size=15, align='center'))
    blocks.append(_text(accroche, size=18, align='center'))
    blocks.append({'type': 'divider'})
    blocks.append(_heading('Notre sélection', size=34))
    if arts:
        sel = (
            f'{len(arts)} œuvre{"s" if len(arts) > 1 else ""} disponible{"s" if len(arts) > 1 else ""}. '
            'Certificat d\'authenticité et accompagnement personnalisé pour chaque acquisition.'
        )
    else:
        sel = (
            'Publiez vos œuvres depuis le tableau de bord pour les afficher ici. '
            'En attendant, parcourez le catalogue Artworks.'
        )
    blocks.append(_text(sel))
    if images:
        blocks.append({'type': 'gallery', 'images': images, 'width': 880, 'height': 400})
    blocks.append({'type': 'divider'})
    blocks.append(_heading('Acquérir une œuvre', size=34))
    blocks.append(_text(
        'Parcourez le catalogue en ligne, demandez des informations ou organisez une visite privée. '
        'Nous répondons sous 48 h.'
    ))
    blocks.append(_button('Voir le catalogue', '/explorer'))
    blocks.append(_button('Ma page publique', page_url, bg='#1a2832'))
    email = (getattr(user, 'email', None) or '').strip()
    if email:
        blocks.append(_button('Nous contacter', f'mailto:{email}', bg='#1a2832'))
    return blocks


def build_presentation_page_blocks(user, page_data: dict) -> list[dict]:
    """Page centrée présentation / bio."""
    name, discipline, location, bio = _profile_bits(page_data)
    images = _artwork_images(page_data)[:3]
    page_url = page_data.get('page_url') or f'/artist/{user.id}'

    if bio:
        body = strip_markdown_for_display(bio)[:2000]
    else:
        body = (
            f'{name} présente ici une sélection d\'œuvres contemporaines. '
            f'{"Spécialité : " + discipline + ". " if discipline else ""}'
            f'{"Basé à " + location + ". " if location else ""}'
            'Complétez votre bio dans le profil pour personnaliser ce texte.'
        )

    blocks: list[dict] = []
    cover = _cover_block(user)
    if cover:
        blocks.append(cover)
    blocks.append(_heading(name, size=46, align='center'))
    if discipline or location:
        blocks.append(_text(' · '.join(x for x in (discipline, location) if x), align='center'))
    blocks.append({'type': 'divider'})
    blocks.append(_heading('Présentation', size=32))
    for para in re.split(r'\n{2,}', body):
        para = para.strip()
        if para:
            blocks.append(_text(para))
    if images:
        blocks.append({'type': 'divider'})
        blocks.append(_heading('Œuvres récentes', size=30))
        blocks.append({'type': 'gallery', 'images': images, 'width': 860, 'height': 360})
    blocks.append({'type': 'divider'})
    blocks.append(_button('Découvrir les œuvres', page_url))
    return blocks


def build_seo_page_blocks(user, page_data: dict) -> list[dict]:
    """Page avec textes orientés référencement naturel (sans keyword stuffing)."""
    name, discipline, location, bio = _profile_bits(page_data)
    images = _artwork_images(page_data)
    discipline_l = (discipline or 'art contemporain').lower()
    loc_bit = f' à {location}' if location else ''

    title = f'{name} — {discipline or "Art contemporain"}{loc_bit}'
    intro = (
        f'{name} propose des œuvres de {discipline_l}{loc_bit}. '
        'Achat d\'art en ligne, certificat d\'authenticité, livraison sécurisée et conseil curatoral.'
    )
    if bio:
        intro = _first_sentences(bio, 1, max_len=220) + ' ' + intro

    blocks: list[dict] = []
    blocks.append(_heading(title, size=40, align='center'))
    blocks.append(_text(intro, align='center'))
    blocks.append({'type': 'divider'})
    blocks.append(_heading(f'Œuvres {discipline_l}{loc_bit}', size=32))
    blocks.append(_text(
        f'Collection d\'œuvres originales : peinture, photographie et créations contemporaines. '
        f'Prix affichés, disponibilité en temps réel, paiement sécurisé sur Artworks.'
    ))
    if images:
        blocks.append({'type': 'gallery', 'images': images[:5], 'width': 880, 'height': 380})
    blocks.append({'type': 'divider'})
    blocks.append(_heading('Acheter une œuvre en ligne', size=30))
    blocks.append(_text(
        'Sélection curatorale, transparence des prix et accompagnement pour collectionneurs et galeries. '
        'Contactez-nous pour une visite ou une réservation.'
    ))
    blocks.append(_button('Parcourir la collection', '/explorer'))
    page_url = page_data.get('page_url') or f'/artist/{user.id}'
    blocks.append(_button('Page artiste', page_url, bg='#1a2832'))
    return blocks

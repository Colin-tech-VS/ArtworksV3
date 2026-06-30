"""Modèle partagé des blocs de page (mode créateur + mode intelligent Aria).

Un même schéma d'élément est utilisé par :
- l'éditeur canvas (mode créateur, JS) ;
- les outils Aria (mode intelligent, qui *applique* réellement) ;
- le rendu de la page publique (artist.html).

Chaque élément : {id, type, x, y, w, h, text|src|href|images, style{...}}.
"""
from __future__ import annotations

import re

# Types de blocs autorisés
ALLOWED_TYPES = ('heading', 'text', 'button', 'image', 'divider', 'slider', 'gallery')

# Polices proposées (clé -> pile CSS) — Webflow-like
FONT_STACKS = {
    'sans': "'Outfit', 'Helvetica Neue', Arial, sans-serif",
    'serif': "'Cormorant Garamond', Georgia, 'Times New Roman', serif",
    'display': "'Cormorant Garamond', Georgia, serif",
    'mono': "'SFMono-Regular', Consolas, monospace",
}
ALLOWED_WEIGHTS = (300, 400, 500, 600, 700, 800)
ALLOWED_ALIGN = ('left', 'center', 'right')
_HEX_RE = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$')

CANVAS_W = 960  # largeur de référence du canvas

# Palette éditoriale galerie (mode intelligent Aria)
GALLERY_THEME: dict[str, dict] = {
    'heading': {'font': 'display', 'size': 42, 'weight': 600, 'color': '#1a2832', 'align': 'center'},
    'text': {'font': 'serif', 'size': 18, 'weight': 400, 'color': '#3d4f58', 'align': 'left'},
    'button': {'font': 'sans', 'size': 15, 'weight': 600, 'bg': '#b8734a', 'color': '#ffffff', 'align': 'center'},
    'divider': {'color': '#c9b8a8'},
}

_EMOJI_RE = re.compile(
    '['
    '\U0001F300-\U0001FAFF'
    '\U00002700-\U000027BF'
    '\U0001F600-\U0001F64F'
    '\u2600-\u26FF'
    '\u2700-\u27BF'
    ']+',
    flags=re.UNICODE,
)


def _num(v, lo, hi, default=0):
    try:
        v = int(float(v))
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def _safe_url(value: str) -> str:
    """N'autorise que http(s) ou chemins internes relatifs."""
    src = str(value or '').strip()[:512]
    if src and not (src.startswith('http://') or src.startswith('https://') or src.startswith('/')):
        return ''
    return src


def sanitize_style(style) -> dict:
    if not isinstance(style, dict):
        return {}
    out = {}
    color = str(style.get('color') or '').strip()
    if _HEX_RE.match(color):
        out['color'] = color
    bg = str(style.get('bg') or '').strip()
    if _HEX_RE.match(bg):
        out['bg'] = bg
    font = str(style.get('font') or '').strip().lower()
    if font in FONT_STACKS:
        out['font'] = font
    if style.get('size') is not None:
        out['size'] = _num(style.get('size'), 8, 160, 0) or None
        if not out['size']:
            out.pop('size')
    weight = style.get('weight')
    try:
        if weight is not None and int(weight) in ALLOWED_WEIGHTS:
            out['weight'] = int(weight)
    except (TypeError, ValueError):
        pass
    align = str(style.get('align') or '').strip().lower()
    if align in ALLOWED_ALIGN:
        out['align'] = align
    if style.get('radius') is not None:
        out['radius'] = _num(style.get('radius'), 0, 200, 0)
    return out


def style_to_css(style: dict) -> str:
    """Convertit un dict style sanitisé en CSS inline (visuel uniquement)."""
    if not isinstance(style, dict):
        return ''
    parts = []
    if style.get('color'):
        parts.append(f"color:{style['color']}")
    if style.get('bg'):
        parts.append(f"background:{style['bg']}")
    if style.get('font') in FONT_STACKS:
        parts.append(f"font-family:{FONT_STACKS[style['font']]}")
    if style.get('size'):
        parts.append(f"font-size:{style['size']}px")
        if style.get('font') in ('serif', 'display'):
            parts.append('line-height:1.45')
        else:
            parts.append('line-height:1.6')
    if style.get('weight'):
        parts.append(f"font-weight:{style['weight']}")
    if style.get('align'):
        parts.append(f"text-align:{style['align']}")
    if style.get('radius'):
        parts.append(f"border-radius:{style['radius']}px;overflow:hidden")
    return ';'.join(parts)


def strip_markdown_for_display(text: str) -> str:
    """Texte affichable : sans markdown, emojis ni balises."""
    t = str(text or '').replace('\r\n', '\n')
    t = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', t)
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
    t = re.sub(r'__([^_]+)__', r'\1', t)
    t = re.sub(r'\*([^*\n]+)\*', r'\1', t)
    t = re.sub(r'_([^_\n]+)_', r'\1', t)
    t = re.sub(r'^#{1,6}\s*', '', t, flags=re.M)
    t = re.sub(r'^[-*•]\s+', '', t, flags=re.M)
    t = _EMOJI_RE.sub('', t)
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def _merge_block_style(etype: str, style: dict | None) -> dict:
    base = dict(GALLERY_THEME.get(etype, {}))
    if isinstance(style, dict):
        base.update({k: v for k, v in style.items() if v not in (None, '')})
    return base


def _infer_block_from_line(line: str) -> dict | None:
    raw = line.strip()
    if not raw:
        return None
    cleaned = strip_markdown_for_display(raw)
    if not cleaned or len(cleaned) < 2:
        return None
    if re.match(r'^#{1,3}\s', raw):
        return {'type': 'heading', 'text': cleaned, 'style': dict(GALLERY_THEME['heading'])}
    if len(cleaned) <= 72 and (cleaned.endswith(':') or ' – ' in cleaned or ' - ' in cleaned):
        return {'type': 'heading', 'text': cleaned.rstrip(':'), 'style': {**GALLERY_THEME['heading'], 'size': 28}}
    if raw.startswith(('- ', '* ', '• ')):
        return {'type': 'text', 'text': '· ' + cleaned, 'style': dict(GALLERY_THEME['text'])}
    return {'type': 'text', 'text': cleaned, 'style': dict(GALLERY_THEME['text'])}


def expand_messy_text_block(block: dict) -> list[dict]:
    """Découpe un bloc texte/heading trop long ou markdowné en blocs propres."""
    text = str(block.get('text') or '').replace('\r\n', '\n')
    if not text.strip():
        return []
    text = re.sub(r'([.!?])([A-ZÀ-Ü])', r'\1\n\n\2', text)
    text = re.sub(r'([a-zàâäéèêëïîôùûüç\)])([A-ZÀ-Ü])', r'\1\n\n\2', text)
    out: list[dict] = []
    for para in re.split(r'\n{2,}', text):
        para = para.strip()
        if not para:
            continue
        title_split = re.match(r'^(.{6,100}?)\s*[–—\-]\s*(.+)$', para, re.S)
        if title_split and len(title_split.group(2)) > 20:
            h = strip_markdown_for_display(title_split.group(1))
            body = strip_markdown_for_display(title_split.group(2))
            if h:
                out.append({'type': 'heading', 'text': h, 'style': dict(GALLERY_THEME['heading'])})
            if body:
                out.append({'type': 'text', 'text': body, 'style': dict(GALLERY_THEME['text'])})
            continue
        lines = [ln.strip() for ln in para.split('\n') if ln.strip()]
        if len(lines) == 1:
            item = _infer_block_from_line(lines[0])
            if item:
                if block.get('type') == 'heading' and item['type'] == 'text':
                    item = {'type': 'heading', 'text': item['text'], 'style': dict(GALLERY_THEME['heading'])}
                out.append(item)
            continue
        for ln in lines:
            item = _infer_block_from_line(ln)
            if item:
                out.append(item)
    return out


def prepare_aria_blocks(blocks: list) -> list[dict]:
    """Normalise les blocs envoyés par Aria avant mise en page."""
    prepared: list[dict] = []
    for raw in blocks or []:
        if not isinstance(raw, dict):
            continue
        etype = raw.get('type')
        if etype not in ALLOWED_TYPES:
            continue
        b = dict(raw)
        if etype in ('heading', 'text', 'button') and b.get('text'):
            messy = (
                '**' in b['text'] or '__' in b['text']
                or _EMOJI_RE.search(b['text'])
                or '\n\n' in b['text']
                or re.search(r'^#{1,3}\s', b['text'], re.M)
                or re.search(r'^[-*•]\s', b['text'], re.M)
                or len(b['text']) > 420
            )
            if messy:
                prepared.extend(expand_messy_text_block(b))
                continue
            b['text'] = strip_markdown_for_display(b['text'])
            if etype == 'button':
                b['text'] = b['text'][:80]
        if etype == 'button' and b.get('text'):
            b['style'] = _merge_block_style('button', b.get('style'))
            if not b.get('href'):
                b['href'] = '/explorer'
        if etype == 'heading' and b.get('text'):
            b['style'] = _merge_block_style('heading', b.get('style'))
        if etype == 'text' and b.get('text'):
            b['style'] = _merge_block_style('text', b.get('style'))
        if etype == 'divider':
            b['style'] = _merge_block_style('divider', b.get('style'))
        prepared.append(b)
    return prepared


def sanitize_element(el) -> dict | None:
    """Nettoie/borne un élément (anti-XSS, valeurs aberrantes)."""
    if not isinstance(el, dict):
        return None
    etype = el.get('type')
    if etype not in ALLOWED_TYPES:
        return None

    out = {
        'id': str(el.get('id') or '')[:40],
        'type': etype,
        'x': _num(el.get('x'), 0, 4000),
        'y': _num(el.get('y'), 0, 40000),
        'w': _num(el.get('w'), 0, 4000),
    }
    style = sanitize_style(el.get('style'))
    if style:
        out['style'] = style

    if etype == 'image':
        out['h'] = _num(el.get('h'), 0, 6000)
        out['src'] = _safe_url(el.get('src'))
    elif etype in ('slider', 'gallery'):
        out['h'] = _num(el.get('h'), 0, 6000)
        imgs = el.get('images')
        clean = []
        if isinstance(imgs, list):
            for u in imgs[:12]:
                s = _safe_url(u)
                if s:
                    clean.append(s)
        out['images'] = clean
    elif etype == 'divider':
        out['h'] = _num(el.get('h'), 1, 200) or 2
    elif etype == 'button':
        out['text'] = strip_markdown_for_display(el.get('text') or '')[:300]
        out['href'] = _safe_url(el.get('href'))
    else:  # heading / text
        out['text'] = strip_markdown_for_display(el.get('text') or '')[:3000]
    return out


def layout_height(elements: list) -> int:
    """Hauteur de canvas nécessaire pour afficher tous les éléments."""
    bottom = 0
    for el in elements or []:
        try:
            y = float(el.get('y') or 0)
            h = float(el.get('h') or 0)
        except (TypeError, ValueError):
            continue
        if not h:
            h = {'heading': 60, 'button': 48, 'divider': 24}.get(el.get('type'), 44)
        bottom = max(bottom, y + h)
    return int(bottom) + 60


# --------------------------------------------------------------------------
# Arrangement vertical : utilisé par Aria (mode intelligent) pour transformer
# une liste ordonnée de blocs simples en layout positionné (colonne centrée).
# --------------------------------------------------------------------------
def _estimate_height(etype: str, b: dict, w: int) -> int:
    if etype == 'heading':
        size = (b.get('style') or {}).get('size') or 40
        return int(size * 1.6) + 12
    if etype == 'button':
        return 52
    if etype == 'divider':
        return 28
    if etype == 'image':
        return _num(b.get('h'), 60, 6000, 360)
    if etype in ('slider', 'gallery'):
        return _num(b.get('h'), 120, 6000, 380)
    # text : estimation selon la longueur
    text = str(b.get('text') or '')
    chars_per_line = max(20, int(w / 9))
    lines = max(1, -(-len(text) // chars_per_line))  # ceil
    return min(1200, 24 + lines * 26)


def arrange_vertical(blocks: list, *, width: int = CANVAS_W) -> list:
    """Empile des blocs simples en une colonne centrée, calcule x/y/w/h.

    Chaque bloc d'entrée : {type, text|src|images, width?, height?, style?}.
    Retourne des éléments sanitisés prêts à être stockés / rendus."""
    blocks = prepare_aria_blocks(blocks)
    out = []
    y = 64
    gap = 44
    seq = 0
    default_w = {
        'heading': 760, 'text': 720, 'button': 280, 'image': 640,
        'slider': 880, 'gallery': 880, 'divider': 640,
    }
    for raw in blocks:
        if not isinstance(raw, dict):
            continue
        etype = raw.get('type')
        if etype not in ALLOWED_TYPES:
            continue
        w = _num(raw.get('width') or raw.get('w'), 80, width, default_w.get(etype, 720))
        x = max(0, round((width - w) / 2))
        style = _merge_block_style(etype, raw.get('style') if isinstance(raw.get('style'), dict) else None)
        h = _estimate_height(etype, {**raw, 'style': style}, w)
        el = {
            'id': f'aria{seq}',
            'type': etype,
            'x': x, 'y': y, 'w': w,
            'style': style,
        }
        if etype == 'image':
            el['h'] = h
            el['src'] = raw.get('src')
        elif etype in ('slider', 'gallery'):
            el['h'] = _num(raw.get('height'), 200, 6000, 400)
            el['images'] = raw.get('images')
        elif etype == 'divider':
            el['h'] = _num(raw.get('height'), 1, 200, 1)
        elif etype == 'button':
            el['text'] = raw.get('text')
            el['href'] = raw.get('href')
        else:
            el['text'] = raw.get('text')
        clean = sanitize_element(el)
        if clean:
            out.append(clean)
            y += h + gap
            seq += 1
    return out


def elements_to_blocks(elements: list) -> list[dict]:
    """Reconvertit des éléments layout en blocs simples pour Aria (refonte in-place)."""
    blocks: list[dict] = []
    for el in elements or []:
        if not isinstance(el, dict):
            continue
        etype = el.get('type')
        if etype not in ALLOWED_TYPES:
            continue
        b: dict = {'type': etype}
        if el.get('text'):
            b['text'] = el.get('text')
        if el.get('href'):
            b['href'] = el.get('href')
        if el.get('src'):
            b['src'] = el.get('src')
        if el.get('images'):
            b['images'] = list(el.get('images') or [])
        if el.get('w'):
            b['width'] = el.get('w')
        if el.get('h') and etype in ('image', 'slider', 'gallery'):
            b['height'] = el.get('h')
        style = el.get('style')
        if isinstance(style, dict) and style:
            b['style'] = dict(style)
        blocks.append(b)
    return blocks

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
    'sans': "'Helvetica Neue', Arial, sans-serif",
    'serif': "Georgia, 'Times New Roman', serif",
    'display': "'Playfair Display', Georgia, serif",
    'mono': "'SFMono-Regular', Consolas, monospace",
}
ALLOWED_WEIGHTS = (300, 400, 500, 600, 700, 800)
ALLOWED_ALIGN = ('left', 'center', 'right')
_HEX_RE = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$')

CANVAS_W = 960  # largeur de référence du canvas


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
    if style.get('weight'):
        parts.append(f"font-weight:{style['weight']}")
    if style.get('align'):
        parts.append(f"text-align:{style['align']}")
    if style.get('radius'):
        parts.append(f"border-radius:{style['radius']}px;overflow:hidden")
    return ';'.join(parts)


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
        out['text'] = str(el.get('text') or '')[:300]
        out['href'] = _safe_url(el.get('href'))
    else:  # heading / text
        out['text'] = str(el.get('text') or '')[:3000]
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
    out = []
    y = 48
    gap = 30
    seq = 0
    default_w = {
        'heading': 720, 'text': 720, 'button': 240, 'image': 560,
        'slider': 860, 'gallery': 860, 'divider': 720,
    }
    for raw in (blocks or []):
        if not isinstance(raw, dict):
            continue
        etype = raw.get('type')
        if etype not in ALLOWED_TYPES:
            continue
        w = _num(raw.get('width') or raw.get('w'), 80, width, default_w.get(etype, 720))
        x = max(0, round((width - w) / 2))
        h = _estimate_height(etype, raw, w)
        el = {
            'id': f'aria{seq}',
            'type': etype,
            'x': x, 'y': y, 'w': w,
            'style': raw.get('style') if isinstance(raw.get('style'), dict) else None,
        }
        if etype == 'image':
            el['h'] = h
            el['src'] = raw.get('src')
        elif etype in ('slider', 'gallery'):
            el['h'] = h
            el['images'] = raw.get('images')
        elif etype == 'divider':
            el['h'] = _num(raw.get('height'), 1, 200, 2)
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

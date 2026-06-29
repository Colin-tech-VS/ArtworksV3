"""Catalogues contrôlés — disciplines art contemporain (Artworks)."""

from __future__ import annotations

# Disciplines / pratiques artistiques contemporaines
DISCIPLINES: list[str] = [
    'Peinture',
    'Dessin',
    'Sculpture',
    'Photographie',
    'Photographie argentique',
    'Photographie numérique',
    'Art numérique',
    'Installation',
    'Performance',
    'Vidéo art',
    'Art sonore',
    'Art textile',
    'Céramique',
    'Gravure',
    'Lithographie',
    'Sérigraphie',
    'Collage',
    'Mixed media',
    'Techniques mixtes',
    'Street art',
    'Art urbain',
    'Art brut',
    'Calligraphie',
    'Land art',
    'Art conceptuel',
    'Body art',
    'Édition / Multiples',
    'Fresque / Murale',
    'Verre',
    'Bronze',
    'Modelage',
    'Design',
    'Architecture',
    'NFT / Crypto-art',
    'Art contemporain pluridisciplinaire',
    'Estampe',
    'Tapisserie',
    'Arts décoratifs',
    'Art éphémère',
    'Art public',
    'Scénographie',
]

# Styles (complément optionnel pour filtres futurs)
ART_STYLES: list[str] = [
    'Abstraction',
    'Figuratif',
    'Art contemporain',
    'Art conceptuel',
    'Art numérique',
    'Minimalisme',
    'Expressionnisme',
    'Surréalisme',
    'Pop art',
    'Street art',
    'Art brut',
    'Photographie d\'art',
    'Installation',
    'Art textile',
    'Art vidéo',
    'Néo-classique',
    'Collage',
    'Mixed media',
    'Géométrique',
    'Color field',
]


def select_choices(items: list[str], current: str | None = None, blank_label: str = '— Sélectionner —'):
    """Choices WTForms SelectField avec valeur actuelle hors liste."""
    out = [('', blank_label)]
    seen = set()
    if current and (c := current.strip()) and c not in items:
        out.append((c, f'{c} (actuel)'))
        seen.add(c)
    for item in items:
        if item in seen:
            continue
        out.append((item, item))
        seen.add(item)
    return out

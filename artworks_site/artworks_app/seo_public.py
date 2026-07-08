"""SEO public — meta, Open Graph et JSON-LD par type de client et par page."""
from __future__ import annotations

import json

from flask import url_for

from .entitlements import user_entitlements

SITE_NAME = 'Artworks Digital'


def _site_url() -> str:
    from flask import current_app
    return (current_app.config.get('SITE_URL') or '').rstrip('/') or 'https://artworksdigital.fr'


def _abs_image(value: str | None, placeholder: str = 'demo/art-01.jpg') -> str:
    """URL absolue d'une image (œuvre/profil) pour Open Graph & JSON-LD."""
    from .storage import absolute_url
    return absolute_url(value or placeholder) or f'{_site_url()}/static/{placeholder}'


def seo_level(user) -> str:
    ent = user_entitlements(user)
    if ent.get('seo_level') == 'max':
        return 'max'
    if ent.get('seo_profile'):
        return 'basic'
    return 'none'


def _artist_tarifs_description() -> str:
    from .subscriptions import plan_for_role, price_label
    from .pricing_store import commission_percent_label
    pf = plan_for_role('artiste', 'portfolio')
    price = price_label(pf) if pf else '9,99 €'
    comm = commission_percent_label()
    return (
        f'Activez votre portfolio public SEO ({price}/mois), vendez vos œuvres en ligne '
        f'avec {comm} de commission à la vente. Visibilité Google pour artistes contemporains.'
    )


def page_meta(page_key: str, **overrides) -> dict:
    """Meta SEO par page — audience acheteur/collectionneur vs artiste."""
    pages = {
        'home': {
            'title': f'Marketplace d\'art contemporain — Œuvres originales | {SITE_NAME}',
            'description': (
                'Achetez et vendez de l\'art contemporain en ligne. Œuvres originales de '
                'artistes et galeries, outils pour collectionneurs. Peinture, photo, sculpture — '
                'paiement sécurisé Stripe, SEO optimisé pour artistes, galeries et collectionneurs.'
            ),
            'keywords': (
                'marketplace art contemporain, acheter oeuvre originale, vendre art en ligne, '
                'galerie art en ligne, artiste contemporain, collectionneur art, art contemporain france'
            ),
            'robots': 'index, follow',
            'og_type': 'website',
        },
        'explorer': {
            'title': f'Catalogue d\'œuvres — Art contemporain à vendre | {SITE_NAME}',
            'description': (
                'Parcourez des centaines d\'œuvres originales : peinture, photographie, sculpture. '
                'Filtrez par artiste, galerie, discipline et prix. Achetez en ligne ou contactez le vendeur.'
            ),
            'keywords': (
                'catalogue art contemporain, oeuvres à vendre, peinture originale, '
                'sculpture contemporaine, art en ligne, collection art'
            ),
            'robots': 'index, follow',
            'og_type': 'website',
        },
        'tarifs_artiste': {
            'title': f'Artiste — Publier & vendre vos œuvres en ligne | {SITE_NAME}',
            'description': _artist_tarifs_description(),
            'keywords': (
                'portfolio artiste seo, vendre oeuvre en ligne, marketplace artiste, '
                'site web artiste, visibilité google artiste'
            ),
            'robots': 'index, follow',
            'og_type': 'website',
        },
        'tarifs_galerie': {
            'title': f'Galerie — Catalogue multi-artistes & ventes en ligne | {SITE_NAME}',
            'description': (
                'Galeries d\'art : page publique SEO, artistes rattachés, marketplace intégrée '
                'et CRM collectionneurs. Formules Pro et Premium sans engagement.'
            ),
            'keywords': (
                'galerie art en ligne, vendre art galerie, catalogue galerie seo, '
                'crm collectionneur art, marketplace galerie'
            ),
            'robots': 'index, follow',
            'og_type': 'website',
        },
        'tarifs_collectionneur': {
            'title': f'Collectionneur — Alertes prix & collection d\'art | {SITE_NAME}',
            'description': (
                'Collectionneurs : explorateur gratuit, alertes prix sur les œuvres, '
                'wishlist privée, avant-premières 48 h et accompagnement curatoral Patron.'
            ),
            'keywords': (
                'collectionneur art contemporain, alerte prix oeuvre, wishlist art, '
                'acheter art en ligne, collection art privée'
            ),
            'robots': 'index, follow',
            'og_type': 'website',
        },
    }
    meta = dict(pages.get(page_key, pages['home']))
    meta.update({k: v for k, v in overrides.items() if v})
    return meta


def render_meta_tags(meta: dict, *, canonical: str | None = None) -> str:
    """Génère les balises meta HTML pour un template."""
    parts = [
        f'<meta name="description" content="{meta["description"]}">',
        f'<meta name="robots" content="{meta.get("robots", "index, follow")}">',
    ]
    if meta.get('keywords'):
        parts.append(f'<meta name="keywords" content="{meta["keywords"]}">')
    parts.extend([
        f'<meta property="og:title" content="{meta["title"]}">',
        f'<meta property="og:description" content="{meta["description"]}">',
        f'<meta property="og:type" content="{meta.get("og_type", "website")}">',
        f'<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{meta["title"]}">',
        f'<meta name="twitter:description" content="{meta["description"]}">',
    ])
    if canonical:
        parts.append(f'<link rel="canonical" href="{canonical}">')
    return '\n'.join(parts)


def site_json_ld() -> dict:
    base = _site_url()
    return {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': SITE_NAME,
        'alternateName': 'Artworks',
        'url': base,
        'description': (
            'Marketplace d\'art contemporain — œuvres originales, artistes, galeries '
            'et collectionneurs. Achat et vente en ligne avec SEO optimisé.'
        ),
        'potentialAction': {
            '@type': 'SearchAction',
            'target': {'@type': 'EntryPoint', 'urlTemplate': f'{base}/explorer?q={{search_term_string}}'},
            'query-input': 'required name=search_term_string',
        },
        'publisher': {
            '@type': 'Organization',
            'name': SITE_NAME,
            'url': base,
            'description': 'Écosystème art contemporain pour artistes, galeries et collectionneurs.',
        },
    }


def explorer_json_ld(artworks, *, query: str = '') -> dict:
    base = _site_url()
    items = []
    for a in artworks[:24]:
        items.append({
            '@type': 'ListItem',
            'position': len(items) + 1,
            'url': base + url_for('main.artwork_detail', artwork_id=a.id),
            'name': a.title,
        })
    data = {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        'name': f'Catalogue art contemporain — {SITE_NAME}',
        'url': base + url_for('main.explorer'),
        'description': 'Œuvres originales disponibles à l\'achat — peinture, photo, sculpture.',
        'isPartOf': {'@type': 'WebSite', 'name': SITE_NAME, 'url': base},
    }
    if query:
        data['about'] = query
    if items:
        data['mainEntity'] = {'@type': 'ItemList', 'itemListElement': items}
    return data


def artist_meta(artist) -> dict:
    ent = user_entitlements(artist)
    name = artist.display_name or artist.username or 'Artiste'
    discipline = artist.discipline or 'art contemporain'
    desc = (artist.description or artist.statement or
            f'Achetez les œuvres originales de {name}, {discipline}. '
            f'Paiement sécurisé sur {SITE_NAME}.')
    desc = (desc or '')[:320]
    if ent.get('seo_level') == 'max':
        title = f'{name} — Œuvres originales {discipline} | Artiste | {SITE_NAME}'
    elif ent.get('seo_profile'):
        title = f'{name} — Artiste {discipline} | Acheter art contemporain'
    else:
        title = f'{name} | {SITE_NAME}'
    return {
        'title': title[:200],
        'description': desc,
        'robots': 'index, follow' if ent.get('seo_profile') else 'noindex, nofollow',
        'og_type': 'profile',
        'image': _abs_image(getattr(artist, 'cover', None) or getattr(artist, 'avatar', None)),
        'url': _site_url() + url_for('main.artist', artist_id=artist.id),
    }


def artist_json_ld(artist) -> dict | None:
    if seo_level(artist) == 'none':
        return None
    name = artist.display_name or artist.username
    url = _site_url() + url_for('main.artist', artist_id=artist.id)
    data = {
        '@context': 'https://schema.org',
        '@type': 'Person',
        'name': name,
        'url': url,
        'jobTitle': artist.discipline or 'Artiste contemporain',
    }
    if artist.location:
        data['address'] = {'@type': 'PostalAddress', 'addressLocality': artist.location}
    if seo_level(artist) == 'max' and artist.artworks:
        data['makesOffer'] = [
            {
                '@type': 'Offer',
                'itemOffered': {
                    '@type': 'VisualArtwork',
                    'name': a.title,
                    'url': _site_url() + url_for('main.artwork_detail', artwork_id=a.id),
                },
            }
            for a in artist.artworks[:12]
        ]
    return data


def artwork_json_ld(artwork) -> dict:
    owner = artwork.owner
    url = _site_url() + url_for('main.artwork_detail', artwork_id=artwork.id)
    data = {
        '@context': 'https://schema.org',
        '@type': 'VisualArtwork',
        'name': artwork.title,
        'url': url,
        'image': _abs_image(artwork.image),
        'artMedium': artwork.technique or artwork.medium or 'Mixed media',
    }
    if artwork.year:
        data['dateCreated'] = str(artwork.year)
    if owner:
        data['creator'] = {'@type': 'Person', 'name': owner.display_name or owner.username}
    if artwork.price and artwork.status != 'reserve':
        data['offers'] = {
            '@type': 'Offer',
            'price': str(int(artwork.price)),
            'priceCurrency': 'EUR',
            'availability': 'https://schema.org/InStock',
            'url': url,
        }
    return data


def artwork_meta(artwork) -> dict:
    owner_name = artwork.owner.name if artwork.owner else 'Artiste'
    price_bit = ''
    if artwork.price and artwork.status != 'reserve':
        price_bit = f' — {int(artwork.price):,} €'.replace(',', ' ')
    title = f'{artwork.title}{price_bit} — {owner_name} | Œuvre originale | {SITE_NAME}'
    medium = artwork.technique or artwork.medium or 'art contemporain'
    desc = (artwork.description or
            f'Œuvre originale « {artwork.title} » ({medium}) par {owner_name}. '
            f'Achat sécurisé en ligne sur {SITE_NAME}.')[:320]
    out = {
        'title': title[:200],
        'description': desc,
        'robots': 'index, follow',
        'og_type': 'product',
        'image': _abs_image(artwork.image),
        'url': _site_url() + url_for('main.artwork_detail', artwork_id=artwork.id),
        'keywords': f'acheter {artwork.title}, oeuvre originale, {medium}, art contemporain',
    }
    if artwork.price and artwork.status != 'reserve':
        out['price'] = str(int(artwork.price))
        out['currency'] = 'EUR'
        out['availability'] = 'in stock'
    return out


def json_ld_script(data: dict | list | None) -> str:
    if not data:
        return ''
    return f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>'


def offer_json_ld(role: str, page_url: str) -> dict:
    from .subscriptions import ROLE_LABELS, plans_for_role
    audience = {
        'artiste': 'artistes contemporains souhaitant publier et vendre en ligne',
        'galerie': 'galeries d\'art et commissaires',
        'collectionneur': 'collectionneurs et acheteurs d\'art',
    }
    name = f'Offre {ROLE_LABELS.get(role, role)} — {SITE_NAME}'
    offers = []
    for p in plans_for_role(role):
        if int(p.get('price_cents') or 0) <= 0:
            continue
        offers.append({
            '@type': 'Offer',
            'name': p['name'],
            'price': str(int(p['price_cents']) / 100),
            'priceCurrency': 'EUR',
            'url': page_url,
        })
    data = {
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        'name': name,
        'url': page_url,
        'description': f'Offre {SITE_NAME} pour {audience.get(role, role)}.',
        'isPartOf': {'@type': 'WebSite', 'name': SITE_NAME, 'url': _site_url()},
    }
    if offers:
        data['offers'] = offers
    return data

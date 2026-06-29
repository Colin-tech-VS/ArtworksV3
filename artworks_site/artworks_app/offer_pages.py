"""Pages offre publiques — SEO et contenu par type de client (sans offre « site web »)."""
from __future__ import annotations

from .monetization import commission_percent_label
from .subscriptions import ROLE_LABELS, plans_for_role, price_label, plan_for_role

_COMM = commission_percent_label()

OFFER_CONFIG = {
    'artiste': {
        'route_name': 'main.offre_artiste',
        'path': '/offre',
        'breadcrumb': 'Offre artiste',
        'hero_eyebrow': 'Portfolio Marketplace',
        'hero_title': 'Publiez, vendez et soyez trouvé sur Google',
        'hero_lead': (
            f'Portfolio public optimisé SEO, vente en ligne Stripe et commission '
            f'{_COMM} uniquement à la vente — sans offre site web séparée.'
        ),
        'seo_title': 'Portfolio artiste — Publier, vendre & référencement Google | Artworks',
        'seo_description': (
            'Artiste contemporain : activez votre portfolio public SEO (9,99 €/mois), '
            'vendez vos œuvres en ligne avec 18 % de commission uniquement à la vente. '
            'Visibilité Google, note curatoriale IA, stats de vues.'
        ),
        'seo_keywords': (
            'portfolio artiste, vendre oeuvre en ligne, seo artiste google, '
            'marketplace art, référencement portfolio artiste, art contemporain'
        ),
        'faq': [
            (
                'Pourquoi le portfolio n\'est-il plus gratuit ?',
                'Le portfolio public inclut l\'hébergement, le SEO Google, la marketplace '
                'Stripe et le support — un abonnement modeste garantit un catalogue de qualité '
                f'et une commission {_COMM} uniquement quand vous vendez.',
            ),
            (
                'Quand la commission est-elle prélevée ?',
                f'Uniquement lors d\'une vente conclue via Artworks ({_COMM}, frais Stripe inclus). '
                'Aucune commission si vous ne vendez pas.',
            ),
            (
                'Puis-je préparer mon profil sans payer ?',
                'Oui : l\'inscription est gratuite. Vous configurez votre espace, puis activez '
                'Portfolio Marketplace quand vous êtes prêt à publier.',
            ),
        ],
    },
    'galerie': {
        'route_name': 'main.offre_galerie',
        'path': '/offre-galerie',
        'breadcrumb': 'Offre galerie',
        'hero_eyebrow': 'Espace galerie curatoriale',
        'hero_title': 'Exposez vos artistes et vendez en ligne',
        'hero_lead': (
            'Page galerie SEO, artistes rattachés, marketplace et outils de suivi — '
            f'commission {_COMM} sur les ventes plateforme.'
        ),
        'seo_title': 'Galerie d\'art en ligne — Catalogue & ventes | Artworks',
        'seo_description': (
            'Galeries : page publique SEO, multi-artistes, marketplace Stripe, '
            'matching collectionneurs. Formules Pro et Premium pour vendre en ligne.'
        ),
        'seo_keywords': (
            'galerie art en ligne, vendre art en ligne, catalogue galerie, '
            'marketplace galerie, crm collectionneur'
        ),
        'faq': [
            (
                'La formule Découverte suffit-elle pour démarrer ?',
                'Oui : 5 œuvres et une page galerie publique. Passez en Pro pour la marketplace '
                'et jusqu\'à 15 artistes.',
            ),
            (
                'Comment fonctionne la commission ?',
                f'{_COMM} sur les ventes conclues via Artworks, prélevée automatiquement '
                'lors du paiement Stripe.',
            ),
        ],
    },
    'collectionneur': {
        'route_name': 'main.offre_collectionneur',
        'path': '/offre-collectionneur',
        'breadcrumb': 'Offre collectionneur',
        'hero_eyebrow': 'Club collectionneur',
        'hero_title': 'Anticipez le marché et collectionnez avec méthode',
        'hero_lead': (
            'Alertes prix, accès avant-première 48 h, wishlist partageable et sessions '
            'curatoriales pour les collectionneurs exigeants.'
        ),
        'seo_title': 'Acheter de l\'art contemporain — Alertes & avant-première | Artworks',
        'seo_description': (
            'Collectionneurs et acheteurs : explorateur gratuit, alertes prix, '
            'accès avant-première 48 h aux nouvelles œuvres, wishlist privée et '
            'accompagnement curatoral Patron.'
        ),
        'seo_keywords': (
            'acheter art contemporain, collectionneur art, alerte prix oeuvre, '
            'wishlist art privée, investir art'
        ),
        'faq': [
            (
                'L\'explorateur est-il gratuit ?',
                'Oui : favoris illimités et profil collectionneur sans abonnement.',
            ),
            (
                'Qu\'apporte l\'accès avant-première ?',
                'Les Membres et Patrons voient les nouvelles œuvres 48 h avant les visiteurs '
                'non abonnés — idéal pour les pièces recherchées.',
            ),
        ],
    },
}


def offer_context(role: str) -> dict:
    role = role or 'artiste'
    cfg = OFFER_CONFIG.get(role, OFFER_CONFIG['artiste'])
    plans = plans_for_role(role)
    from .pricing_store import commission_percent_label
    from .subscriptions import plan_for_role, price_label
    comm = commission_percent_label()
    ctx = {
        **cfg,
        'role': role,
        'role_label': ROLE_LABELS.get(role, role.capitalize()),
        'plans': plans,
        'price_label': price_label,
        'commission_label': comm,
        'siblings': [
            (r, ROLE_LABELS[r], OFFER_CONFIG[r]['path'])
            for r in ('artiste', 'galerie', 'collectionneur')
            if r in OFFER_CONFIG
        ],
    }
    if role == 'artiste':
        pf = plan_for_role('artiste', 'portfolio')
        pf_price = price_label(pf) if pf else '9,99 €'
        ctx['seo_description'] = (
            f'Artiste contemporain : activez votre portfolio public SEO ({pf_price}/mois), '
            f'vendez vos œuvres en ligne avec {comm} de commission uniquement à la vente. '
            f'Visibilité Google, note curatoriale IA, stats de vues.'
        )
    return ctx

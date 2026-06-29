"""Modèles transactionnels Artworks par défaut (éditables depuis le CRM)."""
from __future__ import annotations

from datetime import datetime

from ..models import EmailTemplate, db

_BRAND = 'Artworks'
_HEADING = 'font-family:Georgia,serif;font-size:26px;font-weight:400;margin:0 0 20px;color:#1a2832;'
_FOOTER = 'color:#5a636c;font-size:14px;'

DEFAULT_TEMPLATES = [
    {
        'slug': 'welcome_artiste',
        'name': 'Bienvenue — Artiste',
        'subject': 'Bienvenue sur Artworks, {{name}}',
        'preview_text': 'Votre espace artiste est prêt — publiez vos œuvres dès maintenant.',
        'body_html': f'''
<h1 style="{_HEADING}">Bienvenue, {{{{name}}}}</h1>
<p>Votre compte <strong>Artiste</strong> sur {_BRAND} est activé. Vous pouvez dès à présent :</p>
<ul style="padding-left:20px;line-height:1.8;">
<li>Publier et mettre en vente vos œuvres</li>
<li>Construire votre portfolio en ligne</li>
<li>Accéder aux outils de visibilité et d'analyse</li>
</ul>
<p style="margin-top:24px;">Nous sommes ravis de vous accompagner dans votre parcours artistique.</p>
<p style="{_FOOTER}">L'équipe {_BRAND}</p>
''',
    },
    {
        'slug': 'welcome_galerie',
        'name': 'Bienvenue — Galerie',
        'subject': 'Bienvenue sur Artworks, {{name}}',
        'preview_text': 'Votre espace galerie est prêt — gérez vos artistes et votre catalogue.',
        'body_html': f'''
<h1 style="{_HEADING}">Bienvenue, {{{{name}}}}</h1>
<p>Votre compte <strong>Galerie</strong> est activé. {_BRAND} vous permet de :</p>
<ul style="padding-left:20px;line-height:1.8;">
<li>Présenter votre programme et vos artistes</li>
<li>Gérer un catalogue multi-artistes</li>
<li>Toucher une audience de collectionneurs qualifiés</li>
</ul>
<p style="margin-top:24px;">Notre équipe reste disponible pour vous accompagner.</p>
<p style="{_FOOTER}">L'équipe {_BRAND}</p>
''',
    },
    {
        'slug': 'welcome_collectionneur',
        'name': 'Bienvenue — Collectionneur',
        'subject': 'Bienvenue sur Artworks, {{name}}',
        'preview_text': 'Explorez l\'art contemporain et constituez votre collection.',
        'body_html': f'''
<h1 style="{_HEADING}">Bienvenue, {{{{name}}}}</h1>
<p>Votre compte <strong>Collectionneur</strong> est activé. Découvrez dès maintenant :</p>
<ul style="padding-left:20px;line-height:1.8;">
<li>Des œuvres sélectionnées par des galeries et artistes de confiance</li>
<li>Votre liste de favoris et alertes prix</li>
<li>Des contenus curatoriaux exclusifs</li>
</ul>
<p style="margin-top:24px;">Bonne exploration !</p>
<p style="{_FOOTER}">L'équipe {_BRAND}</p>
''',
    },
    {
        'slug': 'subscription_activated',
        'name': 'Abonnement activé',
        'subject': 'Votre abonnement Artworks est actif',
        'preview_text': 'Merci pour votre confiance — votre formule est maintenant active.',
        'body_html': f'''
<h1 style="{_HEADING}">Abonnement activé</h1>
<p>Bonjour {{{{name}}}},</p>
<p>Votre abonnement <strong>{{{{plan}}}}</strong> est maintenant <strong>actif</strong>. Toutes les fonctionnalités associées à votre formule sont débloquées.</p>
<p style="margin-top:20px;">Merci de faire partie de la communauté {_BRAND}.</p>
''',
    },
    {
        'slug': 'subscription_cancelled',
        'name': 'Annulation d\'abonnement',
        'subject': 'Confirmation d\'annulation de votre abonnement',
        'preview_text': 'Votre abonnement Artworks a été annulé — détails ci-dessous.',
        'body_html': f'''
<h1 style="{_HEADING}">Abonnement annulé</h1>
<p>Bonjour {{{{name}}}},</p>
<p>Nous confirmons l'annulation de votre abonnement {_BRAND}. Vous conservez l'accès à votre compte ; les avantages premium prendront fin à la date prévue de votre période en cours.</p>
<p style="margin-top:20px;">Nous espérons vous revoir bientôt sur la plateforme.</p>
<p style="{_FOOTER}">L'équipe {_BRAND}</p>
''',
    },
    {
        'slug': 'subscription_past_due',
        'name': 'Paiement en échec',
        'subject': 'Action requise — problème de paiement',
        'preview_text': 'Mettez à jour votre moyen de paiement pour conserver votre abonnement.',
        'body_html': f'''
<h1 style="{_HEADING}">Paiement en attente</h1>
<p>Bonjour {{{{name}}}},</p>
<p>Nous n'avons pas pu traiter votre dernier paiement. Pour éviter toute interruption de service, veuillez mettre à jour votre moyen de paiement depuis votre espace compte.</p>
<p style="margin-top:20px;">Si vous avez des questions, notre équipe est à votre disposition.</p>
''',
    },
]


def ensure_default_email_templates() -> int:
    created = 0
    for spec in DEFAULT_TEMPLATES:
        tpl = EmailTemplate.query.filter_by(slug=spec['slug']).first()
        is_new = tpl is None
        if is_new:
            tpl = EmailTemplate(
                slug=spec['slug'],
                name=spec['name'],
                kind='transactional',
                subject=spec['subject'],
                preview_text=spec.get('preview_text', ''),
                body_html=spec['body_html'].strip(),
                auto_send=True,
                active=True,
            )
            db.session.add(tpl)
            created += 1
        tpl.updated_at = datetime.utcnow()
    db.session.commit()
    return created

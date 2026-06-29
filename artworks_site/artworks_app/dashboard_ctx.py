"""Shared dashboard copy and profile completion helpers."""

ROLE_META = {
    'artiste': {
        'label': 'Artiste',
        'eyebrow': 'Espace artiste',
        'welcome': 'Votre portfolio',
        'tagline': 'Publiez vos œuvres, structurez vos séries et présentez votre univers.',
        'works_title': 'Mon portfolio',
        'works_sub': 'Cartels, tarifs, formats et statuts de disponibilité.',
        'series_sub': 'Regroupez vos pièces par projet, période ou thématique.',
        'publish': 'Publier une œuvre',
        'empty_works': 'Votre portfolio est vide — ajoutez votre première œuvre.',
        'empty_series': 'Créez une série pour structurer votre production.',
        'profile_hint': 'Statement, bio et photo de profil renforcent votre visibilité.',
    },
    'galerie': {
        'label': 'Galerie',
        'eyebrow': 'Espace galerie',
        'welcome': 'Votre galerie',
        'tagline': 'Exposez vos artistes, pilotez vos ventes et fidélisez vos collectionneurs.',
        'works_title': 'Catalogue',
        'works_sub': 'Œuvres exposées, prix, formats et disponibilité.',
        'series_sub': 'Expositions, accrochages et collections thématiques.',
        'publish': 'Ajouter au catalogue',
        'empty_works': 'Votre catalogue est vide — référencez une première œuvre.',
        'empty_series': 'Organisez vos expositions en séries curatoriales.',
        'profile_hint': 'Logo, description et note curatoriale valorisent votre page publique.',
    },
    'collectionneur': {
        'label': 'Collectionneur',
        'eyebrow': 'Espace collectionneur',
        'welcome': 'Ma collection',
        'tagline': 'Construisez votre collection avec méthode — favoris, alertes et wishlist curatoriale.',
        'works_title': 'Mes acquisitions',
        'works_sub': 'Œuvres de votre collection — détails, prix et format.',
        'series_sub': 'Classez vos pièces par thème, période ou artiste.',
        'publish': 'Référencer une œuvre',
        'empty_works': 'Aucune œuvre référencée — commencez votre inventaire.',
        'empty_series': 'Créez des séries pour organiser votre collection.',
        'profile_hint': 'Localisation et biographie aident les galeries à vous connaître.',
    },
    'admin': {
        'label': 'Administrateur',
        'eyebrow': 'Administration',
        'welcome': 'CRM Artworks',
        'tagline': 'Gestion de la plateforme — accédez au CRM pour piloter le site.',
        'works_title': '—',
        'works_sub': '',
        'series_sub': '',
        'publish': 'Ouvrir le CRM',
        'empty_works': '',
        'empty_series': '',
        'profile_hint': '',
    },
}

_PROFILE_CHECKS = {
    'artiste': [
        ('display_name', 'Nom affiché'),
        ('avatar', 'Photo de profil'),
        ('discipline', 'Discipline'),
        ('description', 'Description'),
        ('statement', 'Statement'),
    ],
    'galerie': [
        ('display_name', 'Nom affiché'),
        ('logo', 'Logo'),
        ('gallery', 'Nom de la galerie'),
        ('description', 'Description'),
        ('curatorial_note', 'Note curatoriale (auto)'),
    ],
    'collectionneur': [
        ('display_name', 'Nom affiché'),
        ('avatar', 'Photo de profil'),
        ('location', 'Localisation'),
        ('description', 'Description'),
        ('bio', 'Biographie'),
    ],
}


def role_meta(user):
    role = (user.role if user else None) or 'collectionneur'
    if role == 'admin' or getattr(user, 'is_staff', False) and role == 'admin':
        return ROLE_META['admin']
    return ROLE_META.get(role, ROLE_META['collectionneur'])


def profile_completion(user):
    role = user.role or 'collectionneur'
    checks = _PROFILE_CHECKS.get(role, _PROFILE_CHECKS['collectionneur'])
    missing = []
    done = 0
    for field, label in checks:
        if getattr(user, field, None):
            done += 1
        else:
            missing.append(label)
    total = len(checks)
    pct = int(done / total * 100) if total else 100
    return pct, done, total, missing


def dashboard_stats(user, artworks, series):
    dispo = sum(1 for a in artworks if (a.status or 'dispo') != 'reserve')
    reserve = len(artworks) - dispo
    total_value = sum(a.price or 0 for a in artworks)
    total_views = sum(a.view_count or 0 for a in artworks)
    return {
        'artworks_count': len(artworks),
        'series_count': len(series),
        'dispo_count': dispo,
        'reserve_count': reserve,
        'total_value': total_value,
        'total_views': total_views,
    }

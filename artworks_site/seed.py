from artworks_app import create_app, db
from artworks_app.models import User, Artwork
from datetime import datetime

app = create_app()

ARTISTS = {
    'camille': dict(
        username='camille', display_name='Camille Vasseur', email='camille@artworks.test',
        discipline='Peinture abstraite · Huile', location='Marseille, France', gallery='Galerie Lumen',
        avatar='demo/artist-profile.jpg', cover='demo/banner.jpg', since=2009, followers=2140, expos=17,
        statement="Je peins ce qui brûle juste avant de disparaître. La couleur n'est pas un décor : c'est une température, une matière qui se souvient du feu et de la terre.\n"
                  "Chaque toile commence par un effacement. J'applique, je gratte, je recommence — jusqu'à ce que la surface respire d'elle-même.",
        bio="Née à Marseille en 1981, Camille Vasseur développe depuis quinze ans une peinture abstraite gestuelle où dominent les terres brûlées et les ocres. Diplômée des Beaux-Arts de Marseille, elle expose régulièrement en France et en Italie. Représentée par la Galerie Lumen depuis 2018, elle partage son atelier entre Marseille et la campagne provençale.",
    ),
    'theo': dict(
        username='theo', display_name='Théo Lambert', email='theo@artworks.test',
        discipline='Color field · Acrylique', location='Nantes, France', gallery='Studio Méridien',
        avatar='demo/artist-02.jpg', cover='demo/banner.jpg', since=2014, followers=980, expos=8,
        statement="Je cherche l'horizon : cette ligne où deux couleurs se rencontrent sans jamais se toucher.",
        bio="Théo Lambert peint de grands aplats où la lumière semble retenue. Son travail, proche du color field, explore la lenteur et la profondeur des transitions chromatiques.",
    ),
    'ines': dict(
        username='ines', display_name='Inès Caron', email='ines@artworks.test',
        discipline='Photographie argentique', location='Paris, France', gallery='Maison d’Art',
        avatar='demo/artist-03.jpg', cover='demo/banner.jpg', since=2016, followers=1320, expos=11,
        statement="Le silence a une texture. Je la cherche dans le grain de l'argentique.",
        bio="Inès Caron photographie le vide et la matière en noir et blanc. Chaque tirage argentique est réalisé à la main dans son atelier parisien.",
    ),
    'marius': dict(
        username='marius', display_name='Marius Hadi', email='marius@artworks.test',
        discipline='Abstraction géométrique', location='Lyon, France', gallery='Collectif Éclat',
        avatar='demo/artist-04.jpg', cover='demo/banner.jpg', since=2012, followers=1750, expos=14,
        statement="La géométrie est une émotion qui a trouvé sa forme.",
        bio="Marius Hadi compose des architectures de couleurs où l'équilibre tient à un fil. Son vocabulaire géométrique puise dans le Bauhaus et la musique.",
    ),
    'salome': dict(
        username='salome', display_name='Salomé Drift', email='salome@artworks.test',
        discipline='Peinture abstraite · Huile', location='Arles, France', gallery='Galerie Lumen',
        avatar='demo/artist-01.jpg', cover='demo/banner.jpg', since=2011, followers=1490, expos=12,
        statement="Je laboure la toile comme on retourne une terre : pour ce qu'elle garde en mémoire.",
        bio="Salomé Drift travaille la matière épaisse et les terres. Ses paysages abstraits évoquent la campagne provençale et ses sillons.",
    ),
    'elena': dict(
        username='elena', display_name='Élena Roux', email='elena@artworks.test',
        discipline='Figuration', location='Bordeaux, France', gallery='Atelier Nova',
        avatar='demo/artist-02.jpg', cover='demo/banner.jpg', since=2015, followers=1100, expos=9,
        statement="Je peins des présences à la lisière de la lumière.",
        bio="Élena Roux est une peintre figurative dont les intérieurs et portraits jouent sur le clair-obscur et l'intimité.",
    ),
    'nova': dict(
        username='nova', display_name='Atelier Nova', email='nova@artworks.test',
        discipline='Sculpture · Bronze', location='Genève, Suisse', gallery='Atelier Nova',
        avatar='demo/artist-03.jpg', cover='demo/banner.jpg', since=2008, followers=2300, expos=21,
        statement="Le bronze est une attente qui prend forme.",
        bio="Atelier Nova réunit deux sculpteurs autour de formes organiques en bronze patiné, entre figure et abstraction.",
    ),
}

# (artist_key, title, price, image, discipline, style, medium, technique, dims, size, color, status, year)
WORKS = [
    ('camille', 'Embrasement', 4200, 'demo/art-01.jpg', 'peinture', 'abstrait', 'huile', 'Huile sur toile de lin', '120 × 90 × 4 cm', 'grand', 'terra', 'dispo', 2024),
    ('theo', 'Marée basse', 3100, 'demo/art-02.jpg', 'peinture', 'abstrait', 'acrylique', 'Acrylique sur toile', '100 × 140 cm', 'grand', 'bleu', 'dispo', 2023),
    ('ines', 'Silence n°7', 1950, 'demo/art-03.jpg', 'photo', 'figuratif', 'photo', 'Tirage argentique sur papier baryté', '60 × 80 cm', 'moyen', 'nb', 'dispo', 2024),
    ('marius', 'Géométrie douce', 2700, 'demo/art-04.jpg', 'peinture', 'geometrique', 'acrylique', 'Acrylique sur bois', '80 × 80 cm', 'moyen', 'terra', 'dispo', 2023),
    ('salome', 'Terres labourées', 5400, 'demo/art-05.jpg', 'peinture', 'abstrait', 'huile', 'Huile et pigments sur toile', '90 × 130 cm', 'grand', 'terre', 'dispo', 2022),
    ('elena', 'Femme à la fenêtre', 3800, 'demo/art-06.jpg', 'peinture', 'figuratif', 'huile', 'Huile sur toile', '65 × 80 cm', 'moyen', 'terre', 'dispo', 2024),
    ('nova', 'Veille', 7200, 'demo/art-07.jpg', 'sculpture', 'abstrait', 'bronze', 'Bronze patiné, pièce unique', 'H. 48 cm', 'grand', 'nb', 'reserve', 2023),
    ('marius', 'Carnaval', 2300, 'demo/art-08.jpg', 'peinture', 'abstrait', 'acrylique', 'Acrylique sur toile', '80 × 80 cm', 'moyen', 'terra', 'dispo', 2024),
    ('camille', 'Aube rouge', 3600, 'demo/art-09.jpg', 'peinture', 'abstrait', 'huile', 'Huile sur toile de lin', '70 × 95 cm', 'grand', 'terra', 'dispo', 2023),
    ('ines', 'Horizon', 1700, 'demo/art-10.jpg', 'photo', 'figuratif', 'photo', 'Tirage argentique sur papier baryté', '50 × 70 cm', 'moyen', 'clair', 'dispo', 2024),
    ('marius', 'Contrepoint', 2900, 'demo/art-11.jpg', 'peinture', 'geometrique', 'acrylique', 'Acrylique sur toile', '75 × 100 cm', 'moyen', 'bleu', 'dispo', 2023),
    ('salome', 'Sillage', 1450, 'demo/art-12.jpg', 'peinture', 'abstrait', 'huile', 'Huile sur toile', '60 × 40 cm', 'petit', 'clair', 'dispo', 2024),
]

with app.app_context():
    db.drop_all()
    db.create_all()

    users = {}
    for key, data in ARTISTS.items():
        u = User(role='artiste', **data)
        u.set_password('password')
        u.subscription_plan = 'pro' if key == 'camille' else 'portfolio'
        u.subscription_status = 'active'
        u.subscription_since = datetime.utcnow()
        u.stripe_connect_id = f'acct_demo_seed_{key}'
        u.stripe_connect_charges_enabled = True
        u.stripe_connect_payouts_enabled = True
        u.stripe_connected_at = datetime.utcnow()
        db.session.add(u)
        users[key] = u
    db.session.flush()

    for (akey, title, price, image, disc, style, medium, tech, dims, size, color, status, year) in WORKS:
        framing = 'Non encadrée — châssis prêt à accrocher' if medium != 'bronze' else 'Socle inclus'
        a = Artwork(
            title=title, price=price, image=image, owner=users[akey],
            discipline=disc, style=style, medium=medium, technique=tech,
            dimensions=dims, size=size, color=color, status=status, year=year,
            signed=True, certificate=True, condition='Excellent — œuvre neuve',
            framing=framing, created_at=datetime.utcnow(),
            description="Œuvre originale, pièce unique. Vendue avec certificat d'authenticité signé par l'artiste.",
        )
        db.session.add(a)

    db.session.commit()
    print('DB initialisée :', User.query.count(), 'artistes /', Artwork.query.count(), 'œuvres.')
    print('Connexion de démonstration : camille / password')

"""Idempotent schema migration: adds new columns/tables without dropping data."""
from artworks_app import create_app, db
from sqlalchemy import text, inspect

app = create_app()

USER_COLS = {
    'description': 'TEXT',
    'curatorial_note': 'TEXT',
    'curatorial_note_at': 'DATETIME',
    'logo': 'VARCHAR(256)',
    'subscription_plan': "VARCHAR(32) DEFAULT 'free'",
    'subscription_status': "VARCHAR(20) DEFAULT 'active'",
    'subscription_since': 'DATETIME',
    'subscription_period_end': 'DATETIME',
    'stripe_customer_id': 'VARCHAR(64)',
    'stripe_subscription_id': 'VARCHAR(64)',
    'stripe_connect_id': 'VARCHAR(64)',
    'stripe_connect_charges_enabled': 'INTEGER DEFAULT 0',
    'stripe_connect_payouts_enabled': 'INTEGER DEFAULT 0',
    'stripe_connected_at': 'DATETIME',
    'curatorial_quota_month': 'VARCHAR(7)',
    'curatorial_quota_used': 'INTEGER DEFAULT 0',
    'wishlist_share_token': 'VARCHAR(32)',
    'is_staff': 'INTEGER DEFAULT 0',
    'google_sub': 'VARCHAR(64)',
    'page_mode': "VARCHAR(16) DEFAULT 'redacteur'",
    'page_layout_json': 'TEXT',
    'page_published': 'INTEGER DEFAULT 0',
}

ARTWORK_COLS = {
    'series_id': 'INTEGER',
    'format': 'VARCHAR(32)',
    'view_count': 'INTEGER DEFAULT 0',
    'early_access': 'INTEGER DEFAULT 0',
    'deviantart_deviation_id': 'VARCHAR(64)',
    'deviantart_url': 'VARCHAR(512)',
    'deviantart_views': 'INTEGER DEFAULT 0',
    'deviantart_favorites': 'INTEGER DEFAULT 0',
    'pinterest_pin_id': 'VARCHAR(64)',
    'pinterest_saves': 'INTEGER DEFAULT 0',
    'pinterest_impressions': 'INTEGER DEFAULT 0',
    'social_published_at': 'DATETIME',
}


def add_missing(table, cols):
    insp = inspect(db.engine)
    existing = {c['name'] for c in insp.get_columns(table)}
    # Quote identifiers so reserved words (e.g. Postgres "user") don't break DDL.
    # Each column is added in its own transaction so one failure can't roll back the rest.
    preparer = db.engine.dialect.identifier_preparer
    qtable = preparer.quote(table)
    for name, ddl in cols.items():
        if name not in existing:
            qname = preparer.quote(name)
            with db.engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE {qtable} ADD COLUMN {qname} {ddl}'))
            print(f'  + {table}.{name}')


def fix_postgres_sequences():
    """Réaligne les séquences d'auto-incrément PostgreSQL sur MAX(id).

    Après l'import des données V2 -> V3 avec des IDs explicites, les séquences
    SERIAL ne sont pas avancées : le prochain INSERT (création de compte,
    classification segment, etc.) entre en collision de clé primaire et provoque
    une IntegrityError -> erreur 500 à l'inscription, ou « identifiant déjà pris »
    côté Aria. On resynchronise chaque séquence liée à une colonne « id »."""
    if db.engine.dialect.name != 'postgresql':
        return
    insp = inspect(db.engine)
    fixed = 0
    with db.engine.begin() as conn:
        for table in insp.get_table_names():
            cols = {c['name'] for c in insp.get_columns(table)}
            if 'id' not in cols:
                continue
            seq = conn.execute(
                text("SELECT pg_get_serial_sequence(:t, 'id')"),
                {'t': table},
            ).scalar()
            if not seq:
                continue
            # setval(seq, MAX(id)) ; is_called=true => prochain nextval = MAX(id)+1.
            # Sur table vide -> setval(seq, 1, false) => prochain nextval = 1.
            conn.execute(text(
                f'SELECT setval(:seq, '
                f'(SELECT COALESCE(MAX(id), 1) FROM "{table}"), '
                f'(SELECT COUNT(*) > 0 FROM "{table}"))'
            ), {'seq': seq})
            fixed += 1
    if fixed:
        print(f'  ~ {fixed} séquence(s) PostgreSQL resynchronisée(s)')


SEGMENT_COLS = {
    'slug': 'VARCHAR(64)',
    'is_system': 'INTEGER DEFAULT 0',
}

CAMPAIGN_COLS = {
    'recipient_mode': "VARCHAR(20) DEFAULT 'segment'",
    'recipient_role': 'VARCHAR(20)',
    'recipient_user_ids_json': "TEXT DEFAULT '[]'",
    'preview_confirmed_at': 'DATETIME',
}

with app.app_context():
    db.create_all()  # creates new tables (e.g. series) if missing
    add_missing('user', USER_COLS)
    add_missing('artwork', ARTWORK_COLS)
    add_missing('email_segment', SEGMENT_COLS)
    add_missing('email_campaign', CAMPAIGN_COLS)
    fix_postgres_sequences()

    # Artistes demo avec œuvres → portfolio actif (catalogue public visible)
    from artworks_app.models import User
    from datetime import datetime
    seed_artists = {'camille', 'theo', 'ines', 'marius', 'salome', 'elena', 'nova'}
    upgraded = 0
    for u in User.query.filter_by(role='artiste').all():
        if u.artworks and u.subscription_plan in (None, 'free', 'essentiel', ''):
            if u.username in seed_artists or len(u.artworks) >= 1:
                u.subscription_plan = 'pro' if u.username == 'camille' else 'portfolio'
                u.subscription_status = 'active'
                if not u.subscription_since:
                    u.subscription_since = datetime.utcnow()
                upgraded += 1
    if upgraded:
        db.session.commit()
        print(f'  + {upgraded} artiste(s) -> portfolio/pro (catalogue public)')

    from artworks_app.stripe_connect import connect_required_for, connect_ready, demo_connect_user
    connect_up = 0
    for u in User.query.filter(User.role.in_(('artiste', 'galerie'))).all():
        if connect_required_for(u) and not connect_ready(u):
            if u.username in seed_artists or app.config.get('STRIPE_DEMO_MODE'):
                demo_connect_user(u)
                connect_up += 1
    if connect_up:
        print(f'  + {connect_up} compte(s) Stripe Connect demo (encaissement)')

    print('Migration done.')

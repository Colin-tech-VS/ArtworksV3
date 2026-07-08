#!/usr/bin/env python3
"""
Migration Artworks Digital V2 (staging-artworks-digital / artworksdigital) → Artworks V3.

Lit la base V2 en lecture seule (V2_DATABASE_URL) et écrit dans la base V3 (DATABASE_URL).
Mode --dry-run par défaut : aucune écriture sans --execute.

Usage (depuis la racine du dépôt) :
  cd artworks_site
  set V2_DATABASE_URL=postgresql://...   # Supabase V2 / staging
  set DATABASE_URL=postgresql://...      # Supabase V3
  python ../scripts/migrate_v2_to_v3.py --dry-run
  python ../scripts/migrate_v2_to_v3.py --execute --only users,artworks,analytics
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Permettre l'import du package Flask depuis artworks_site/
SITE_ROOT = Path(__file__).resolve().parents[1] / 'artworks_site'
sys.path.insert(0, str(SITE_ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from artworks_app import create_app, db
from artworks_app.models import (
    AnalyticsEvent,
    Artwork,
    ArtworkFavorite,
    GalleryArtist,
    PriceAlert,
    Series,
    User,
)


def _slugify(value: str, fallback: str = 'user') -> str:
    s = re.sub(r'[^a-z0-9]+', '-', (value or '').lower()).strip('-')
    return (s[:60] or fallback).strip('-')


def _v2_engine():
    url = os.environ.get('V2_DATABASE_URL', '').strip()
    if not url:
        raise SystemExit(
            'V2_DATABASE_URL manquant. Récupérez l\'URI PostgreSQL du projet '
            'staging-artworks-digital (Supabase → Database → Connection string).'
        )
    return create_engine(url, pool_pre_ping=True)


def _ensure_migration_map(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS _v2_migration_map (
            id BIGSERIAL PRIMARY KEY,
            entity_type VARCHAR(64) NOT NULL,
            v2_source VARCHAR(64) NOT NULL,
            v2_id VARCHAR(128) NOT NULL,
            v3_table VARCHAR(64) NOT NULL,
            v3_id INTEGER NOT NULL,
            migrated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (entity_type, v2_source, v2_id)
        )
    """))


def _get_map(conn, entity_type: str, v2_source: str, v2_id: str) -> int | None:
    row = conn.execute(
        text("""
            SELECT v3_id FROM _v2_migration_map
            WHERE entity_type = :et AND v2_source = :src AND v2_id = :vid
        """),
        {'et': entity_type, 'src': v2_source, 'vid': str(v2_id)},
    ).fetchone()
    return int(row[0]) if row else None


def _set_map(conn, entity_type: str, v2_source: str, v2_id: str, v3_table: str, v3_id: int):
    conn.execute(
        text("""
            INSERT INTO _v2_migration_map (entity_type, v2_source, v2_id, v3_table, v3_id)
            VALUES (:et, :src, :vid, :tbl, :id)
            ON CONFLICT (entity_type, v2_source, v2_id) DO NOTHING
        """),
        {'et': entity_type, 'src': v2_source, 'vid': str(v2_id), 'tbl': v3_table, 'id': v3_id},
    )


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        text("SELECT to_regclass(:t)"),
        {'t': f'public.{table}'},
    ).fetchone()
    return row and row[0] is not None


def migrate_users(v2_conn, session, *, dry_run: bool) -> dict[str, int]:
    """Artistes, galeries, fans/collectionneurs V2 → User V3."""
    stats = {'artists': 0, 'galleries': 0, 'collectors': 0, 'skipped': 0}
    id_map: dict[str, int] = {}

    if _table_exists(v2_conn, 'artists'):
        rows = v2_conn.execute(text("""
            SELECT id, slug, email, full_name, bio, discipline, location,
                   avatar_url, cover_url, password_hash, google_sub,
                   stripe_customer_id, stripe_connect_id, created_at
            FROM artists ORDER BY id
        """)).mappings().all()
        for r in rows:
            v2_id = str(r['id'])
            existing = _get_map(v2_conn, 'user', 'artists', v2_id)
            if existing:
                id_map[f'artist:{v2_id}'] = existing
                stats['skipped'] += 1
                continue
            username = _slugify(r.get('slug') or r.get('email', '').split('@')[0], f'artiste-{v2_id}')
            if session.query(User).filter((User.username == username) | (User.email == r['email'])).first():
                stats['skipped'] += 1
                continue
            user = User(
                username=username,
                email=r['email'],
                password_hash=r.get('password_hash'),
                google_sub=r.get('google_sub'),
                role='artiste',
                display_name=r.get('full_name') or username,
                discipline=r.get('discipline'),
                location=r.get('location'),
                bio=r.get('bio'),
                avatar=r.get('avatar_url'),
                cover=r.get('cover_url'),
                stripe_customer_id=r.get('stripe_customer_id'),
                stripe_connect_id=r.get('stripe_connect_id'),
                subscription_plan='portfolio',
            )
            if not dry_run:
                session.add(user)
                session.flush()
                _set_map(v2_conn, 'user', 'artists', v2_id, 'user', user.id)
                id_map[f'artist:{v2_id}'] = user.id
            stats['artists'] += 1

    if _table_exists(v2_conn, 'galleries'):
        rows = v2_conn.execute(text("""
            SELECT id, slug, email, name, description, logo_url, cover_url,
                   password_hash, stripe_customer_id, created_at
            FROM galleries ORDER BY id
        """)).mappings().all()
        for r in rows:
            v2_id = str(r['id'])
            existing = _get_map(v2_conn, 'user', 'galleries', v2_id)
            if existing:
                id_map[f'gallery:{v2_id}'] = existing
                stats['skipped'] += 1
                continue
            username = _slugify(r.get('slug') or r.get('name', ''), f'galerie-{v2_id}')
            if session.query(User).filter((User.username == username) | (User.email == r['email'])).first():
                stats['skipped'] += 1
                continue
            user = User(
                username=username,
                email=r['email'],
                password_hash=r.get('password_hash'),
                role='galerie',
                display_name=r.get('name') or username,
                description=r.get('description'),
                logo=r.get('logo_url'),
                cover=r.get('cover_url'),
                stripe_customer_id=r.get('stripe_customer_id'),
                subscription_plan='pro',
            )
            if not dry_run:
                session.add(user)
                session.flush()
                _set_map(v2_conn, 'user', 'galleries', v2_id, 'user', user.id)
                id_map[f'gallery:{v2_id}'] = user.id
            stats['galleries'] += 1

    if _table_exists(v2_conn, 'fans'):
        rows = v2_conn.execute(text("""
            SELECT id, email, name, password_hash, google_sub, created_at
            FROM fans ORDER BY id
        """)).mappings().all()
        for r in rows:
            v2_id = str(r['id'])
            existing = _get_map(v2_conn, 'user', 'fans', v2_id)
            if existing:
                stats['skipped'] += 1
                continue
            username = _slugify(r.get('email', '').split('@')[0], f'collector-{v2_id}')
            if session.query(User).filter((User.username == username) | (User.email == r['email'])).first():
                stats['skipped'] += 1
                continue
            user = User(
                username=username,
                email=r['email'],
                password_hash=r.get('password_hash'),
                google_sub=r.get('google_sub'),
                role='collectionneur',
                display_name=r.get('name') or username,
                subscription_plan='free',
            )
            if not dry_run:
                session.add(user)
                session.flush()
                _set_map(v2_conn, 'user', 'fans', v2_id, 'user', user.id)
            stats['collectors'] += 1

    return stats


def migrate_artworks(v2_conn, session, *, dry_run: bool) -> dict[str, int]:
    stats = {'artworks': 0, 'series': 0, 'skipped': 0}
    series_cache: dict[str, int] = {}

    if not _table_exists(v2_conn, 'artworks'):
        return stats

    rows = v2_conn.execute(text("""
        SELECT id, artist_id, title, description, price, image_url, image_path,
               year, technique, medium, dimensions, status, group_name,
               view_count, created_at
        FROM artworks ORDER BY id
    """)).mappings().all()

    for r in rows:
        v2_id = str(r['id'])
        if _get_map(v2_conn, 'artwork', 'artworks', v2_id):
            stats['skipped'] += 1
            continue
        owner_id = _get_map(v2_conn, 'user', 'artists', str(r['artist_id']))
        if not owner_id:
            stats['skipped'] += 1
            continue

        series_id = None
        group = (r.get('group_name') or '').strip()
        if group:
            key = f'{owner_id}:{group}'
            if key not in series_cache and not dry_run:
                s = Series(name=group, user_id=owner_id)
                session.add(s)
                session.flush()
                series_cache[key] = s.id
                stats['series'] += 1
            series_id = series_cache.get(key)

        image = r.get('image_url') or r.get('image_path')
        artwork = Artwork(
            title=r['title'] or f'Œuvre {v2_id}',
            description=r.get('description'),
            price=float(r['price']) if r.get('price') else None,
            image=image,
            user_id=owner_id,
            series_id=series_id,
            year=r.get('year'),
            technique=r.get('technique'),
            medium=r.get('medium'),
            dimensions=r.get('dimensions'),
            status=r.get('status') or 'dispo',
            view_count=int(r.get('view_count') or 0),
            created_at=r.get('created_at') or datetime.utcnow(),
        )
        if not dry_run:
            session.add(artwork)
            session.flush()
            _set_map(v2_conn, 'artwork', 'artworks', v2_id, 'artwork', artwork.id)
        stats['artworks'] += 1

    return stats


def migrate_analytics(v2_conn, session, *, dry_run: bool) -> dict[str, int]:
    stats = {'events': 0, 'skipped': 0}
    for table in ('analytics_events', 'page_views', 'events'):
        if not _table_exists(v2_conn, table):
            continue
        rows = v2_conn.execute(text(f"""
            SELECT id, event_type, path, page_title, session_id, user_id,
                   referrer, source, artwork_id, meta, created_at
            FROM {table} ORDER BY id
        """)).mappings().all()
        for r in rows:
            v2_id = str(r['id'])
            if _get_map(v2_conn, 'analytics', table, v2_id):
                stats['skipped'] += 1
                continue
            user_id = None
            if r.get('user_id'):
                user_id = _get_map(v2_conn, 'user', 'artists', str(r['user_id']))
            artwork_id = None
            if r.get('artwork_id'):
                artwork_id = _get_map(v2_conn, 'artwork', 'artworks', str(r['artwork_id']))
            ev = AnalyticsEvent(
                event_type=r.get('event_type') or 'page_view',
                path=r.get('path'),
                page_title=r.get('page_title'),
                session_id=r.get('session_id'),
                user_id=user_id,
                referrer=r.get('referrer'),
                source=r.get('source') or 'direct',
                artwork_id=artwork_id,
                meta_json=r.get('meta') or '{}',
                created_at=r.get('created_at') or datetime.utcnow(),
            )
            if not dry_run:
                session.add(ev)
                session.flush()
                _set_map(v2_conn, 'analytics', table, v2_id, 'analytics_event', ev.id)
            stats['events'] += 1
        break
    return stats


def migrate_favorites(v2_conn, session, *, dry_run: bool) -> dict[str, int]:
    stats = {'favorites': 0, 'skipped': 0}
    if not _table_exists(v2_conn, 'favorites'):
        return stats
    rows = v2_conn.execute(text("""
        SELECT id, fan_id, artwork_id, created_at FROM favorites ORDER BY id
    """)).mappings().all()
    for r in rows:
        user_id = _get_map(v2_conn, 'user', 'fans', str(r['fan_id']))
        artwork_id = _get_map(v2_conn, 'artwork', 'artworks', str(r['artwork_id']))
        if not user_id or not artwork_id:
            stats['skipped'] += 1
            continue
        if session.query(ArtworkFavorite).filter_by(user_id=user_id, artwork_id=artwork_id).first():
            stats['skipped'] += 1
            continue
        if not dry_run:
            session.add(ArtworkFavorite(user_id=user_id, artwork_id=artwork_id, created_at=r.get('created_at')))
        stats['favorites'] += 1
    return stats


STEPS = {
    'users': migrate_users,
    'artworks': migrate_artworks,
    'analytics': migrate_analytics,
    'favorites': migrate_favorites,
}


def main():
    parser = argparse.ArgumentParser(description='Migration V2 → V3 Artworks Digital')
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='Simulation sans écriture (défaut)')
    parser.add_argument('--execute', action='store_true',
                        help='Exécuter réellement la migration')
    parser.add_argument('--only', default='users,artworks,analytics,favorites',
                        help='Étapes séparées par des virgules')
    args = parser.parse_args()
    dry_run = not args.execute
    steps = [s.strip() for s in args.only.split(',') if s.strip() in STEPS]

    if dry_run:
        print('=== MODE DRY-RUN (ajoutez --execute pour écrire) ===')

    v2_engine = _v2_engine()
    app = create_app()
    with app.app_context():
        with v2_engine.connect() as v2_conn:
            _ensure_migration_map(v2_conn)
            v2_conn.commit()
            session = db.session
            for step in steps:
                print(f'\n--- {step} ---')
                result = STEPS[step](v2_conn, session, dry_run=dry_run)
                print(result)
            if not dry_run:
                session.commit()
                v2_conn.commit()
                print('\n✓ Migration terminée.')
            else:
                session.rollback()
                print('\n(dry-run — aucune donnée écrite)')


if __name__ == '__main__':
    main()

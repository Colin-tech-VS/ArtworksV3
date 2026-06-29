#!/usr/bin/env python3
"""Inspecte la base V2 (Scalingo artworksdigital) — comptage tables clés pour migration V3.

Usage:
  set V2_DATABASE_URL=postgres://...
  python scripts/v2_db_inspect.py

Ou via Scalingo:
  scalingo --app artworksdigital env-get SCALINGO_POSTGRESQL_URL
"""
from __future__ import annotations

import os
import sys

TABLES = (
    'artists', 'artworks', 'galleries', 'gallery_paintings', 'gallery_artist_partnerships',
    'favorites', 'marketplace_orders', 'orders', 'fans', 'messages',
    'community_posts', 'social_post_tracking', 'stripe_events',
)


def main() -> int:
    dsn = os.environ.get('V2_DATABASE_URL') or os.environ.get('DATABASE_URL')
    if not dsn:
        print('Définissez V2_DATABASE_URL (URL Postgres artworksdigital).', file=sys.stderr)
        return 1
    try:
        import psycopg2
    except ImportError:
        print('pip install psycopg2-binary', file=sys.stderr)
        return 1

    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    print('=== Artworks Digital V2 — inventaire ===\n')
    for table in TABLES:
        try:
            cur.execute(f'SELECT COUNT(*) FROM {table}')
            n = cur.fetchone()[0]
            print(f'  {table:32} {n:>8}')
        except Exception as exc:
            conn.rollback()
            print(f'  {table:32} (absent ou erreur: {exc})')
    cur.execute(
        "SELECT signup_kind, COUNT(*) FROM artists GROUP BY signup_kind ORDER BY 2 DESC"
    )
    print('\n--- artists par signup_kind ---')
    for kind, n in cur.fetchall():
        print(f'  {kind or "?":20} {n}')
    cur.execute(
        "SELECT subscription_plan, COUNT(*) FROM artists GROUP BY subscription_plan ORDER BY 2 DESC LIMIT 15"
    )
    print('\n--- artists par subscription_plan ---')
    for plan, n in cur.fetchall():
        print(f'  {plan or "?":20} {n}')
    conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

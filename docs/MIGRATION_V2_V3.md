# Migration V2 → V3 — Artworks Digital

## Contexte

| Environnement | App / DB | Rôle |
|---------------|----------|------|
| **V2 prod** | Scalingo `artworksdigital` | Clients actuels (artistes, galeries, collectionneurs V2) |
| **V2 staging** | Dépôt `Colin-tech-VS/staging-artworks-digital` | Environnement de test / données de référence |
| **V3 prod** | Scalingo `artworksv3` | Nouvelle plateforme (ce dépôt) |
| **V3 DB cible** | **Supabase** (PostgreSQL) | Base unique V3 — remplace SQLite en local |

V3 utilise SQLAlchemy (`artworks_app/models.py`) avec un schéma unifié `User` + `Artwork` + CRM.

V2 utilise un schéma multi-tenant (`artists`, `galleries`, tables séparées) — voir `Artworks Digital V2/db.py` ou le dépôt staging.

## Étape 1 — Supabase (V3)

1. Créer un projet sur [supabase.com](https://supabase.com) : **ArtworksV3**
2. Région : `eu-west-1` (proche Scalingo osc-fr1)
3. Récupérer **Database → Connection string → URI** (mode Session, port 5432)
4. Format : `postgresql://postgres.[ref]:[password]@aws-0-eu-west-1.pooler.supabase.com:5432/postgres`
5. Sur Scalingo `artworksv3` :
   ```bash
   scalingo --app artworksv3 env-set DATABASE_URL="postgresql://..."
   ```
6. Au premier déploiement, l'app exécute `db.create_all()` + `migrate.py` (colonnes idempotentes).

### Activer l'extension utile (SQL Editor Supabase)

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

Exécuter aussi `docs/supabase_v3_bootstrap.sql` pour la table `_v2_migration_map`.

## Étape 2 — Récupérer la base V2 (staging ou prod)

Le dépôt [staging-artworks-digital](https://github.com/Colin-tech-VS/staging-artworks-digital) est privé — accès requis.

**Option A — URI Supabase V2 directement**

Base V2 prod de référence : Supabase `onifrjiwbsjnhejtmrpq` (fév. 2026).

```bash
# Récupérer l'URI dans Supabase → Project Settings → Database
export V2_DATABASE_URL="postgresql://postgres.[ref]:[password]@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
```

**Option B — Dump PostgreSQL complet**

```bash
pg_dump "$V2_DATABASE_URL" --no-owner --no-acl -F c -f v2_backup.dump
pg_restore -d "$DATABASE_URL" --no-owner --no-acl v2_backup.dump  # optionnel, tables brutes
```

> Pour V3, préférer le script de migration structuré (mapping entités) plutôt qu'un restore brut.

## Inventaire V2 (référence — fév. 2026)

| Table | ~Lignes |
|-------|---------|
| artists | 137 |
| artworks | 633 |
| galleries | 2 |
| fans | 33 |
| marketplace_orders | 3 |

## Étape 3 — Mapping entités

| V2 | V3 `User` | Notes |
|----|-----------|-------|
| `artists` (signup_kind=portfolio) | `role=artiste` | `slug` → `username`, `full_name` → `display_name` |
| `galleries` | `role=galerie` | Partenariats → `GalleryArtist` |
| `fans` / comptes collectionneur V2 | `role=collectionneur` | À confirmer selon tables actives |
| `artworks` (artist_id) | `Artwork` (owner_id) | Images : copier vers Supabase Storage `artworks-uploads` |
| `gallery_paintings` | `Artwork` (owner=galerie) | Lien artiste via métadonnées |
| `analytics_events` / `page_views` | `AnalyticsEvent` | Historique analytics |
| `favorites` | `ArtworkFavorite` | Favoris collectionneurs |
| Abonnements Stripe V2 | `subscription_plan`, `stripe_customer_id` | Réconciliation manuelle ou webhook |

Tables V3 sans équivalent direct V2 (à créer vides) : CRM emails, `SocialPost`, `CmsPage`, segments.

## Étape 4 — Script de migration

Fichier : `scripts/migrate_v2_to_v3.py`

```bash
cd artworks_site
export V2_DATABASE_URL="postgresql://..."   # source V2 / staging
export DATABASE_URL="postgresql://..."      # cible V3 Supabase

# Simulation (défaut)
python ../scripts/migrate_v2_to_v3.py --dry-run

# Exécution réelle
python ../scripts/migrate_v2_to_v3.py --execute

# Étapes partielles
python ../scripts/migrate_v2_to_v3.py --execute --only users,artworks
python ../scripts/migrate_v2_to_v3.py --execute --only analytics,favorites
```

**Fonctionnalités :**
- Lecture seule sur `V2_DATABASE_URL`
- Écriture sur `DATABASE_URL` (Supabase V3)
- Table `_v2_migration_map` (v2_table, v2_id → v3_user_id / v3_artwork_id)
- Mode `--dry-run` par défaut
- Idempotent : ignore les entités déjà migrées

**Ordre recommandé :**
1. Users (artistes → galeries → collectionneurs)
2. Series (depuis `group_name` V2)
3. Artworks + fichiers images
4. Analytics + favoris / alertes prix
5. Stripe IDs (customer, connect) — phase manuelle validée

### Migration des images

Les URLs/paths V2 doivent être copiés vers le bucket Supabase `artworks-uploads` :

```bash
# À adapter selon votre stockage V2 (Supabase Storage ou static Scalingo)
python scripts/migrate_v2_images.py --dry-run   # (à créer si besoin)
```

## Étape 5 — Cutover production

1. Maintenance V2 (bannière)
2. Migration delta finale (`--execute`)
3. DNS `artworksdigital.fr` → app `artworksv3`
4. Mettre à jour OAuth redirects (Google, DeviantArt, Pinterest) vers domaine V3
5. Webhooks Stripe → endpoint V3

## Variables à aligner post-migration

- `SITE_URL` = URL publique V3 (`https://artworksdigital.fr`)
- `SITE_NAME` = `Artworks Digital`
- `GOOGLE_OAUTH_*` : ajouter callback prod dans Google Console
- `DEVIANTART_REDIRECT_URI` / `PINTEREST_REDIRECT_URI` → `/crm/social/oauth/.../callback`
- `STRIPE_WEBHOOK_SECRET` : nouveau endpoint webhook V3

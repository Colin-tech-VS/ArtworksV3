# Migration V2 → V3 — Artworks Salon

## Contexte

| Environnement | App / DB | Rôle |
|---------------|----------|------|
| **V2 prod** | Scalingo `artworksdigital` | Clients actuels (artistes, galeries, collectionneurs V2) |
| **V3 prod** | Scalingo `artworksv3` | Nouvelle plateforme (ce dépôt) |
| **V3 DB cible** | **Supabase** (PostgreSQL) | Base unique V3 — remplace SQLite en local |

V3 utilise SQLAlchemy (`artworks_app/models.py`) avec un schéma unifié `User` + `Artwork` + CRM.

V2 utilise un schéma multi-tenant (`artists`, `galleries`, tables séparées) — voir `Artworks Digital V2/db.py`.

## Étape 1 — Supabase (V3)

1. Créer un projet sur [supabase.com](https://supabase.com) : **ArtworksV3**
2. Région : `eu-west-1` (proche Scalingo osc-fr1)
3. Récupérer **Database → Connection string → URI** (mode Session, port 5432)
4. Format : `postgresql://postgres.[ref]:[password]@aws-0-eu-west-1.pooler.supabase.com:5432/postgres`
5. Sur Scalingo `artworksv3` :
   ```bash
   scalingo --app artworksv3 env-set DATABASE_URL="postgresql://..."
   ```
6. Au premier déploiement, l’app exécute `db.create_all()` + `migrate.py` (colonnes idempotentes).

### Activer l’extension utile (SQL Editor Supabase)

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

## Inventaire V2 (référence — fév. 2026)

| Table | ~Lignes |
|-------|---------|
| artists | 137 |
| artworks | 633 |
| galleries | 2 |
| fans | 33 |
| marketplace_orders | 3 |

Base V2 : Supabase `onifrjiwbsjnhejtmrpq`. V3 : nouveau projet **ArtworksV3** (voir `SUPABASE_V3_SETUP.md`).

## Étape 3 — Mapping entités (plan de migration)

| V2 | V3 `User` | Notes |
|----|-----------|-------|
| `artists` (signup_kind=portfolio) | `role=artiste` | `slug` → `username`, `full_name` → `display_name` |
| `galleries` | `role=galerie` | Partenariats → `GalleryArtist` |
| `fans` / comptes collectionneur V2 | `role=collectionneur` | À confirmer selon tables actives |
| `artworks` (artist_id) | `Artwork` (owner_id) | Images : copier vers `static/uploads` ou S3 |
| `gallery_paintings` | `Artwork` (owner=galerie) | Lien artiste via métadonnées |
| Abonnements Stripe V2 | `subscription_plan`, `stripe_customer_id` | Réconciliation manuelle ou webhook |

Tables V3 sans équivalent direct V2 (à créer vides) : CRM emails, `SocialPost`, `CmsPage`, segments.

## Étape 4 — Script de migration (à venir)

Fichier prévu : `scripts/migrate_v2_users.py`

- Lecture seule sur `V2_DATABASE_URL`
- Écriture sur `DATABASE_URL` (Supabase V3)
- Table `_v2_migration_map` (v2_table, v2_id → v3_user_id / v3_artwork_id)
- Mode `--dry-run` par défaut

**Ordre recommandé :**
1. Users (artistes → galeries → collectionneurs)
2. Series (depuis `group_name` V2)
3. Artworks + fichiers images
4. Favoris / alertes prix
5. Stripe IDs (customer, connect) — phase manuelle validée

## Étape 5 — Cutover production

1. Maintenance V2 (bannière)
2. Migration delta finale
3. DNS `artworksdigital.fr` → app `artworksv3`
4. Mettre à jour OAuth redirects (Google, DeviantArt, Pinterest) vers domaine V3
5. Webhooks Stripe → endpoint V3

## Variables à aligner post-migration

- `SITE_URL` = URL publique V3
- `GOOGLE_OAUTH_*` : ajouter callback prod dans Google Console
- `DEVIANTART_REDIRECT_URI` / `PINTEREST_REDIRECT_URI` → `/crm/social/oauth/.../callback`
- `STRIPE_WEBHOOK_SECRET` : nouveau endpoint webhook V3

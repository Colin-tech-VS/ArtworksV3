# Artworks V3 — Artworks Digital

Marketplace d'art contemporain (artistes, galeries & collectionneurs). Code applicatif dans `artworks_site/`.

## Local

```bash
cd artworks_site
pip install -r requirements.txt
python migrate.py
python run.py 8080
```

## Déploiement Scalingo (`artworksv3`)

- **Procfile** à la racine (buildpack Python)
- **Autodeploy** : branche `main` du dépôt GitHub `Colin-tech-VS/ArtworksV3`

```powershell
# Après scalingo login
.\scripts\scalingo_env_sync.ps1
scalingo --app artworksv3 env-set DATABASE_URL="postgresql://..."
scalingo --app artworksv3 integrations github create Colin-tech-VS/ArtworksV3 branch=main
```

## Base de données

- **Prod V3** : Supabase PostgreSQL (`DATABASE_URL`)
- **Migration depuis V2 / staging** : voir [docs/MIGRATION_V2_V3.md](docs/MIGRATION_V2_V3.md)

```bash
# Simulation migration V2 → V3
cd artworks_site
set V2_DATABASE_URL=postgresql://...   # staging-artworks-digital / artworksdigital
set DATABASE_URL=postgresql://...      # Supabase ArtworksV3
python ../scripts/migrate_v2_to_v3.py --dry-run
python ../scripts/migrate_v2_to_v3.py --execute
```

## Google OAuth

Callbacks autorisés :
- Local : `http://127.0.0.1:8080/auth/google/callback`
- Prod : `https://artworksv3.osc-fr1.scalingo.io/auth/google/callback`

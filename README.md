# Artworks V3 — Salon Collection

Plateforme galeries & collectionneurs (Flask). Code applicatif dans `artworks_site/`.

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
- **Migration clients V2** : voir [docs/MIGRATION_V2_V3.md](docs/MIGRATION_V2_V3.md)

## Google OAuth

Callbacks autorisés :
- Local : `http://127.0.0.1:8080/auth/google/callback`
- Prod : `https://artworksv3.osc-fr1.scalingo.io/auth/google/callback`

# Supabase V3 — création du projet

## Pourquoi un projet séparé ?

La V2 (`artworksdigital`) utilise déjà Supabase :

- Projet : `onifrjiwbsjnhejtmrpq` (région EU)
- ~137 artistes, 633 œuvres (inventaire mars 2026)

La **V3** doit avoir sa **propre base PostgreSQL** pour ne pas mélanger schémas V2/V3 pendant la migration.

## Créer le projet (dashboard)

1. [supabase.com/dashboard](https://supabase.com/dashboard) → **New project**
2. Nom : **ArtworksV3**
3. Région : **West EU (Ireland)** — proche Scalingo `osc-fr1`
4. Mot de passe DB : générer et sauvegarder (gestionnaire de mots de passe)
5. Une fois prêt : **Project Settings → Database → Connection string → URI** (mode Session, port 5432)

## Bootstrap SQL

Dans **SQL Editor**, exécuter le fichier :

`docs/supabase_v3_bootstrap.sql`

## Lier à Scalingo `artworksv3`

```powershell
$sc = ".\tools\scalingo147\scalingo_1.47.0_windows_amd64\scalingo.exe"
& $sc --app artworksv3 env-set DATABASE_URL="postgresql://postgres.[ref]:[password]@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
```

Puis redéployer :

```powershell
& $sc --app artworksv3 integration-link-manual-deploy main
```

## État actuel (transition)

En attendant le projet Supabase V3 dédié, l’app `artworksv3` utilise un **PostgreSQL Scalingo** (`postgresql-starter-512`) provisionné automatiquement. Remplacez `DATABASE_URL` par Supabase quand le projet est prêt.

## Inventaire V2 (référence migration)

| Table | Lignes |
|-------|--------|
| artists | 137 |
| artworks | 633 |
| galleries | 2 |
| fans (collectionneurs) | 33 |
| marketplace_orders | 3 |
| messages | 12 |

Voir `artworks_site/scripts/v2_db_inspect.py` pour rejouer l’inventaire.

# Supabase V3 — guide complet

Checklist pour connecter **ArtworksV3** (base PostgreSQL + stockage images).

---

## 1. Créer le projet

1. Aller sur [supabase.com/dashboard](https://supabase.com/dashboard)
2. **New project**
3. **Nom** : `ArtworksV3`
4. **Région** : West EU (Ireland) — proche Scalingo `osc-fr1`
5. **Mot de passe DB** : générer et sauvegarder dans un gestionnaire de mots de passe

Attendre que le projet soit prêt (~2 min).

---

## 2. Bootstrap SQL (base de données)

1. **SQL Editor** → New query
2. Coller et exécuter le contenu de `docs/supabase_v3_bootstrap.sql`
3. Vérifier : pas d'erreur rouge

> Les tables applicatives (`user`, `artwork`, etc.) sont aussi créées par Flask au premier démarrage (`db.create_all`). Le bootstrap ajoute l'extension `pg_trgm` et la table de migration V2→V3.

---

## 3. Récupérer les identifiants

### Base PostgreSQL

**Project Settings → Database → Connection string**

- Mode : **URI**
- Type : **Session** (port **5432**) ou **Transaction** (port **6543** pooler)
- Copier l'URL du type :
  ```
  postgresql://postgres.[ref]:[MOT_DE_PASSE]@aws-0-eu-west-1.pooler.supabase.com:5432/postgres
  ```

### API (stockage images)

**Project Settings → API**

| Champ | Usage |
|-------|--------|
| **Project URL** | `SUPABASE_URL` → `https://[ref].supabase.co` |
| **service_role** (secret) | `SUPABASE_SERVICE_KEY` — **jamais** côté navigateur |

---

## 4. Créer le bucket Storage (images persistantes)

Sans ça, les images disparaissent à chaque deploy Scalingo.

1. **Storage → New bucket**
2. **Name** : `artworks-uploads`
3. Cocher **Public bucket**
4. Create

Si les uploads échouent, exécuter dans SQL Editor (décommenter le bloc Storage dans `supabase_v3_bootstrap.sql`) :

```sql
INSERT INTO storage.buckets (id, name, public)
VALUES ('artworks-uploads', 'artworks-uploads', true)
ON CONFLICT (id) DO UPDATE SET public = true;

CREATE POLICY "Public read artworks-uploads"
ON storage.objects FOR SELECT
USING (bucket_id = 'artworks-uploads');
```

> L'écriture se fait via la clé `service_role` côté serveur Flask — pas besoin de policy INSERT publique.

---

## 5. Variables Scalingo (production)

```powershell
$sc = ".\tools\scalingo147\scalingo_1.47.0_windows_amd64\scalingo.exe"

& $sc --app artworksv3 env-set `
  DATABASE_URL="postgresql://postgres.[ref]:[MOT_DE_PASSE]@aws-0-eu-west-1.pooler.supabase.com:5432/postgres" `
  SUPABASE_URL="https://[ref].supabase.co" `
  SUPABASE_SERVICE_KEY="eyJhbGciOi..." `
  SUPABASE_STORAGE_BUCKET="artworks-uploads" `
  SITE_URL="https://artworksv3.osc-fr1.scalingo.io"
```

Puis redéployer :

```powershell
& $sc --app artworksv3 integration-link-manual-deploy main
```

Vérifier :

```powershell
& $sc --app artworksv3 env
```

---

## 6. Variables locales (développement)

Créer ou compléter `artworks_site/.env` :

```env
DATABASE_URL=postgresql://postgres.[ref]:[MOT_DE_PASSE]@aws-0-eu-west-1.pooler.supabase.com:5432/postgres
SUPABASE_URL=https://[ref].supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOi...
SUPABASE_STORAGE_BUCKET=artworks-uploads
SITE_URL=http://127.0.0.1:8080
SECRET_KEY=votre-cle-dev
```

Sans `SUPABASE_*` : les uploads restent dans `static/uploads/` (OK en local, perdus au redeploy Scalingo).

---

## 7. Tests après configuration

| Test | Comment |
|------|---------|
| Base OK | L'app démarre sans erreur DB ; login / dashboard fonctionne |
| Storage OK | Uploader une image œuvre → URL du type `https://[ref].supabase.co/storage/v1/object/public/artworks-uploads/...` |
| Persistant | Redéployer Scalingo → l'image est toujours visible |

---

## 8. État actuel (transition)

Tant que `DATABASE_URL` pointe encore vers le PostgreSQL Scalingo (`postgresql-starter-512`), remplacez-le par Supabase quand le projet est prêt.

Les images déjà perdues lors d'un deploy précédent ne sont pas récupérables — il faudra les re-uploader.

---

## Inventaire V2 (référence migration)

| Table | Lignes |
|-------|--------|
| artists | 137 |
| artworks | 633 |
| galleries | 2 |
| fans | 33 |
| marketplace_orders | 3 |
| messages | 12 |

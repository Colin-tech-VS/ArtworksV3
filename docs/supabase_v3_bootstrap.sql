-- Schéma Supabase V3 — exécuter dans SQL Editor après création du projet ArtworksV3
-- L'app Flask crée aussi les tables via SQLAlchemy (db.create_all + migrate.py)

CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Table de mapping migration V2 → V3 (future)
CREATE TABLE IF NOT EXISTS _v2_migration_map (
    id BIGSERIAL PRIMARY KEY,
    entity_type VARCHAR(64) NOT NULL,
    v2_source VARCHAR(64) NOT NULL,
    v2_id VARCHAR(128) NOT NULL,
    v3_table VARCHAR(64) NOT NULL,
    v3_id INTEGER NOT NULL,
    migrated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (entity_type, v2_source, v2_id)
);

CREATE INDEX IF NOT EXISTS idx_v2_migration_v3 ON _v2_migration_map (v3_table, v3_id);

COMMENT ON TABLE _v2_migration_map IS 'Correspondance IDs Artworks Digital V2 → Artworks V3';

-- ---------------------------------------------------------------------------
-- Storage : bucket public pour les uploads (images œuvres, avatars, etc.)
-- Créer d'abord le bucket "artworks-uploads" (Public) dans Storage → New bucket
-- Puis exécuter ce bloc si les uploads échouent en prod.
-- ---------------------------------------------------------------------------

-- INSERT INTO storage.buckets (id, name, public)
-- VALUES ('artworks-uploads', 'artworks-uploads', true)
-- ON CONFLICT (id) DO UPDATE SET public = true;

-- CREATE POLICY "Public read artworks-uploads"
-- ON storage.objects FOR SELECT
-- USING (bucket_id = 'artworks-uploads');

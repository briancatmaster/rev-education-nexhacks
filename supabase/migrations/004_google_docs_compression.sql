-- Migration: Add compression metadata for Google Docs materials
-- Safe to run after the base Google Docs table exists.

DO $$
BEGIN
  IF to_regclass('public.google_docs_materials') IS NOT NULL THEN
    ALTER TABLE google_docs_materials
      ADD COLUMN IF NOT EXISTS content_snippet TEXT,
      ADD COLUMN IF NOT EXISTS compressed_storage_bucket TEXT DEFAULT 'compressed_documents',
      ADD COLUMN IF NOT EXISTS compressed_storage_path TEXT,
      ADD COLUMN IF NOT EXISTS original_tokens INTEGER,
      ADD COLUMN IF NOT EXISTS compressed_tokens INTEGER,
      ADD COLUMN IF NOT EXISTS compression_ratio FLOAT,
      ADD COLUMN IF NOT EXISTS ttc_processed BOOLEAN DEFAULT FALSE,
      ADD COLUMN IF NOT EXISTS is_processed BOOLEAN DEFAULT FALSE;

    CREATE INDEX IF NOT EXISTS idx_google_docs_materials_compressed_storage
      ON google_docs_materials(compressed_storage_path)
      WHERE compressed_storage_path IS NOT NULL;
  END IF;
END $$;

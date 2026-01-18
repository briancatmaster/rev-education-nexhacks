-- Migration: Fix image/PDF storage architecture
-- This migration:
-- 1. Adds storage path columns if they don't exist
-- 2. Clears inline data for records that have storage paths
-- 3. Marks records without storage paths for reprocessing

-- ============================================
-- Add storage path columns if they don't exist
-- ============================================
ALTER TABLE academia_materials
ADD COLUMN IF NOT EXISTS compressed_storage_bucket TEXT DEFAULT 'compressed_documents';

ALTER TABLE academia_materials
ADD COLUMN IF NOT EXISTS compressed_storage_path TEXT;

-- ============================================
-- Add comments for documentation
-- ============================================
COMMENT ON COLUMN academia_materials.compressed_storage_bucket IS 'Storage bucket name for compressed content (default: compressed_documents)';
COMMENT ON COLUMN academia_materials.compressed_storage_path IS 'Path within the storage bucket to the compressed JSON file';

-- ============================================
-- Clear inline data for records that have storage paths
-- This saves database space since data is in object storage
-- ============================================
UPDATE academia_materials
SET
  original_text = NULL,
  compressed_text = NULL,
  extracted_images = NULL
WHERE compressed_storage_path IS NOT NULL
  AND (
    original_text IS NOT NULL
    OR compressed_text IS NOT NULL
    OR extracted_images IS NOT NULL
  );

-- ============================================
-- Mark records for reprocessing that:
-- 1. Were marked as processed
-- 2. But don't have a storage path
-- This forces the worker to reprocess them with the new storage architecture
-- ============================================
UPDATE academia_materials
SET ttc_processed = FALSE
WHERE compressed_storage_path IS NULL
  AND ttc_processed = TRUE;

-- ============================================
-- Create index for finding materials by storage path
-- ============================================
CREATE INDEX IF NOT EXISTS idx_academia_materials_storage_path
ON academia_materials(compressed_storage_path)
WHERE compressed_storage_path IS NOT NULL;

-- ============================================
-- Add RLS policy for storage bucket if not exists
-- Note: This is a reminder - actual bucket policies should be set in Supabase Dashboard
-- ============================================
-- Bucket: compressed_documents
-- Recommended policies:
-- - Allow authenticated users to read their own files
-- - Allow service role to upload/delete files
-- - Path pattern: {user_id}/{material_id}/*

-- ============================================
-- Summary of changes:
-- ============================================
-- 1. Added compressed_storage_bucket column (default 'compressed_documents')
-- 2. Added compressed_storage_path column
-- 3. Cleared inline data for records that already have storage paths
-- 4. Marked records without storage paths for reprocessing
-- 5. Added index on storage_path for faster lookups
--
-- After running this migration:
-- - Run the document processing worker to reprocess flagged materials
-- - Verify storage bucket 'compressed_documents' exists and has proper RLS policies
-- - Check that new uploads store images as individual files in storage

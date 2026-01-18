-- Migration: Add columns for Token Company compression tracking
-- Run this in Supabase SQL Editor after 001_academia_materials.sql

-- ============================================
-- Add compression tracking columns to academia_materials
-- ============================================
ALTER TABLE academia_materials ADD COLUMN IF NOT EXISTS original_text TEXT;
ALTER TABLE academia_materials ADD COLUMN IF NOT EXISTS compressed_text TEXT;
ALTER TABLE academia_materials ADD COLUMN IF NOT EXISTS original_token_count INTEGER;
ALTER TABLE academia_materials ADD COLUMN IF NOT EXISTS compressed_token_count INTEGER;
ALTER TABLE academia_materials ADD COLUMN IF NOT EXISTS compression_ratio FLOAT;
ALTER TABLE academia_materials ADD COLUMN IF NOT EXISTS compression_aggressiveness FLOAT;
ALTER TABLE academia_materials ADD COLUMN IF NOT EXISTS extracted_images JSONB;
ALTER TABLE academia_materials ADD COLUMN IF NOT EXISTS ttc_processed BOOLEAN DEFAULT FALSE;
ALTER TABLE academia_materials ADD COLUMN IF NOT EXISTS ttc_processed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE academia_materials ADD COLUMN IF NOT EXISTS pdf_extraction_method TEXT;

-- ============================================
-- Create index for quick lookups of unprocessed materials
-- ============================================
CREATE INDEX IF NOT EXISTS idx_academia_materials_ttc_unprocessed
ON academia_materials(ttc_processed)
WHERE ttc_processed = FALSE;

-- Create index for finding materials with compressed text
CREATE INDEX IF NOT EXISTS idx_academia_materials_ttc_processed
ON academia_materials(ttc_processed)
WHERE ttc_processed = TRUE;

-- ============================================
-- Add comments for documentation
-- ============================================
COMMENT ON COLUMN academia_materials.original_text IS 'Full extracted text from PDF before compression';
COMMENT ON COLUMN academia_materials.compressed_text IS 'Text after Token Company API compression';
COMMENT ON COLUMN academia_materials.original_token_count IS 'Token count before compression';
COMMENT ON COLUMN academia_materials.compressed_token_count IS 'Token count after compression';
COMMENT ON COLUMN academia_materials.compression_ratio IS 'Ratio of compression achieved (compressed/original)';
COMMENT ON COLUMN academia_materials.compression_aggressiveness IS 'Aggressiveness setting used (0.0-1.0)';
COMMENT ON COLUMN academia_materials.extracted_images IS 'Array of extracted images: [{page, index, base64, width, height, alt}]';
COMMENT ON COLUMN academia_materials.ttc_processed IS 'Whether Token Company has processed this document';
COMMENT ON COLUMN academia_materials.ttc_processed_at IS 'Timestamp when Token Company processing completed';
COMMENT ON COLUMN academia_materials.pdf_extraction_method IS 'Method used for PDF extraction (pymupdf, pdfplumber, etc.)';

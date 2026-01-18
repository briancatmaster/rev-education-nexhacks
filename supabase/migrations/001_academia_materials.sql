-- Migration: Add tables for topic concepts, similarity tracking, and academia materials
-- Run this in Supabase SQL Editor

-- ============================================
-- Table: topic_concepts
-- Stores generated topic concepts from research questions
-- ============================================
CREATE TABLE IF NOT EXISTS topic_concepts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    research_topic TEXT NOT NULL,
    concepts JSONB NOT NULL, -- Array of 10 concept objects
    storage_url TEXT, -- URL in topic_concepts bucket
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_topic_concepts_session ON topic_concepts(session_id);
CREATE INDEX idx_topic_concepts_user ON topic_concepts(user_id);

-- ============================================
-- Table: user_knowledge_similarity
-- Stores computed knowledge similarity (which concepts user likely knows)
-- ============================================
CREATE TABLE IF NOT EXISTS user_knowledge_similarity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic_concepts_id UUID REFERENCES topic_concepts(id) ON DELETE CASCADE,
    known_concepts JSONB NOT NULL, -- Array of 4 known concept objects
    learning_path_suggestion TEXT,
    storage_url TEXT, -- URL in similarity bucket
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_user_knowledge_session ON user_knowledge_similarity(session_id);
CREATE INDEX idx_user_knowledge_user ON user_knowledge_similarity(user_id);

-- ============================================
-- Table: academia_materials
-- Stores all academic materials (papers read, authored, courses, etc.)
-- ============================================
CREATE TABLE IF NOT EXISTS academia_materials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Material classification
    material_type TEXT NOT NULL CHECK (material_type IN (
        'paper_read',           -- Papers user has read and taken notes on
        'paper_authored',       -- Papers user has written/co-authored
        'educational_course',   -- Courses/textbooks completed
        'educational_problems', -- Problems/exercises solved
        'other'                 -- Any other materials
    )),

    -- Source information
    title TEXT,
    doi TEXT,                   -- Digital Object Identifier (for papers)
    url TEXT,                   -- External URL (arxiv, semantic scholar, etc.)
    source_type TEXT CHECK (source_type IN (
        'pdf_upload',
        'doi_url',
        'zotero_import',
        'semantic_scholar',
        'manual_entry',
        'other'
    )),

    -- Storage
    storage_bucket TEXT,        -- Which bucket the file is in
    storage_path TEXT,          -- Path within the bucket
    file_name TEXT,
    file_size_bytes INTEGER,

    -- Metadata
    authors TEXT[],             -- Array of author names
    publication_year INTEGER,
    notes TEXT,                 -- User's notes about the material
    tags TEXT[],                -- User-defined tags

    -- Processing status
    is_processed BOOLEAN DEFAULT FALSE,
    gemini_processed BOOLEAN DEFAULT FALSE, -- Whether Gemini has analyzed this
    extracted_concepts JSONB,   -- Concepts extracted by Gemini (only for paper_read)

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_academia_materials_session ON academia_materials(session_id);
CREATE INDEX idx_academia_materials_user ON academia_materials(user_id);
CREATE INDEX idx_academia_materials_type ON academia_materials(material_type);
CREATE INDEX idx_academia_materials_doi ON academia_materials(doi);

-- ============================================
-- Table: zotero_connections
-- Stores Zotero API credentials for users
-- ============================================
CREATE TABLE IF NOT EXISTS zotero_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    zotero_user_id TEXT NOT NULL,
    api_key_encrypted TEXT NOT NULL, -- Store encrypted
    last_sync_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id)
);

-- ============================================
-- Storage Buckets (create in Supabase Dashboard > Storage)
-- ============================================
-- 1. topic_concepts - JSON files with generated topic concepts
-- 2. similarity - JSON files with knowledge similarity results
-- 3. academia_analyzed - Papers user has read (PDFs)
-- 4. papers_authored - Papers user has written (PDFs)
-- 5. educational_materials - Courses, textbooks, problems (PDFs/docs)
-- 6. other_materials - Any other uploaded materials

-- ============================================
-- Function to update updated_at timestamp
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DROP TRIGGER IF EXISTS update_topic_concepts_updated_at ON topic_concepts;
CREATE TRIGGER update_topic_concepts_updated_at
    BEFORE UPDATE ON topic_concepts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_knowledge_similarity_updated_at ON user_knowledge_similarity;
CREATE TRIGGER update_user_knowledge_similarity_updated_at
    BEFORE UPDATE ON user_knowledge_similarity
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_academia_materials_updated_at ON academia_materials;
CREATE TRIGGER update_academia_materials_updated_at
    BEFORE UPDATE ON academia_materials
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_zotero_connections_updated_at ON zotero_connections;
CREATE TRIGGER update_zotero_connections_updated_at
    BEFORE UPDATE ON zotero_connections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- RLS Policies (enable Row Level Security)
-- ============================================
ALTER TABLE topic_concepts ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_knowledge_similarity ENABLE ROW LEVEL SECURITY;
ALTER TABLE academia_materials ENABLE ROW LEVEL SECURITY;
ALTER TABLE zotero_connections ENABLE ROW LEVEL SECURITY;

-- For now, allow all operations (adjust based on auth setup)
CREATE POLICY "Allow all for topic_concepts" ON topic_concepts FOR ALL USING (true);
CREATE POLICY "Allow all for user_knowledge_similarity" ON user_knowledge_similarity FOR ALL USING (true);
CREATE POLICY "Allow all for academia_materials" ON academia_materials FOR ALL USING (true);
CREATE POLICY "Allow all for zotero_connections" ON zotero_connections FOR ALL USING (true);

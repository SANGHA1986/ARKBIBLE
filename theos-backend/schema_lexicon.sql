-- ARK AI Lexicon + Membership schema (SQLite-compatible)
-- UTF-8 is default for SQLite text. For MySQL use utf8mb4.

CREATE TABLE IF NOT EXISTS source_registry (
    id INTEGER PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,          -- e.g. STRONGS_1890, STEP_TBESG, SEFARIA
    title VARCHAR(200) NOT NULL,
    author VARCHAR(100),
    publisher VARCHAR(100),
    source_url VARCHAR(500),
    source_type VARCHAR(50),
    copyright_owner VARCHAR(100),
    copyright_status VARCHAR(50) NOT NULL,     -- Public Domain | CC BY 4.0 | Mixed
    license_type VARCHAR(50) NOT NULL,         -- NEVER auto-stamp CC0 for PD
    license_url VARCHAR(500),
    attribution_text TEXT NOT NULL,            -- required display credit
    commercial_use BOOLEAN DEFAULT 0,
    allow_ai_quote BOOLEAN DEFAULT 1,
    publication_year INTEGER,
    verification_status VARCHAR(20) DEFAULT '미검증',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Strong's number is the join key across lexicons
CREATE TABLE IF NOT EXISTS strong_entries (
    id INTEGER PRIMARY KEY,
    strong_number VARCHAR(16) NOT NULL UNIQUE, -- H7225, G0026 (normalized)
    language_type VARCHAR(20) NOT NULL,        -- Hebrew | Greek
    lemma TEXT,
    transliteration VARCHAR(200),
    pronunciation VARCHAR(200),
    gloss TEXT,
    definition_short TEXT,
    definition_full TEXT,
    morphology_hint VARCHAR(100),
    root_word TEXT,
    source_id INTEGER NOT NULL REFERENCES source_registry(id),
    content_hash VARCHAR(64),                  -- dedupe of payload
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lexicon_expansions (
    id INTEGER PRIMARY KEY,
    strong_number VARCHAR(16) NOT NULL,
    lexicon_name VARCHAR(80) NOT NULL,         -- Thayer | BDB | STEP_TBESG | STEP_TBESH
    entry_text TEXT NOT NULL,
    source_id INTEGER NOT NULL REFERENCES source_registry(id),
    content_hash VARCHAR(64),
    UNIQUE(strong_number, lexicon_name, source_id)
);

CREATE TABLE IF NOT EXISTS morphology_links (
    id INTEGER PRIMARY KEY,
    strong_number VARCHAR(16) NOT NULL,
    related_strong VARCHAR(16) NOT NULL,
    relation_type VARCHAR(50) NOT NULL,        -- cross_ref | LXX_equiv | synonym
    morph_code VARCHAR(100),
    source_id INTEGER NOT NULL REFERENCES source_registry(id),
    UNIQUE(strong_number, related_strong, relation_type, source_id)
);

CREATE TABLE IF NOT EXISTS sefaria_passages (
    id INTEGER PRIMARY KEY,
    ref_key VARCHAR(200) NOT NULL UNIQUE,      -- e.g. Genesis.1.1
    title VARCHAR(200),
    he_text TEXT,
    en_text TEXT,
    tradition_note TEXT,
    source_id INTEGER NOT NULL REFERENCES source_registry(id),
    content_hash VARCHAR(64),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Membership: Free_Trial(7d) -> Limited_24h -> Blocked / Paid
-- (extends users table conceptually)
-- ALTER: membership_status, trial_started_at, limited_started_at, subscribed_until

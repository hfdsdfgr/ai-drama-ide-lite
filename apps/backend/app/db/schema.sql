-- AI Drama IDE Lite — Phase 1 基线 schema
-- 约定：所有建表语句 IF NOT EXISTS（幂等），时间统一 UTC ISO-8601 字符串。

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    deleted_at  TEXT
);

CREATE TABLE IF NOT EXISTS novels (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL DEFAULT '',
    source_type TEXT NOT NULL DEFAULT 'original',
    ai_brief    TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chapters (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    novel_id    TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    title       TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL DEFAULT '',
    order_index INTEGER NOT NULL DEFAULT 0,
    deleted_at  TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stories (
    id         TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content    TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS characters (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS locations (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS props (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS episodes (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    novel_id            TEXT REFERENCES novels(id) ON DELETE SET NULL,
    title               TEXT NOT NULL DEFAULT '',
    summary             TEXT NOT NULL DEFAULT '',
    order_index         INTEGER NOT NULL DEFAULT 0,
    source_chapter_index INTEGER,
    deleted_at          TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenes (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    episode_id  TEXT REFERENCES episodes(id) ON DELETE SET NULL,
    novel_id    TEXT REFERENCES novels(id) ON DELETE SET NULL,
    title       TEXT NOT NULL DEFAULT '',
    order_index INTEGER NOT NULL DEFAULT 0,
    slugline    TEXT NOT NULL DEFAULT '',
    action      TEXT NOT NULL DEFAULT '',
    dialogue    TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shots (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scene_id    TEXT REFERENCES scenes(id) ON DELETE SET NULL,
    shot_number INTEGER,
    order_index INTEGER NOT NULL DEFAULT 0,
    shot_type   TEXT NOT NULL DEFAULT '',
    camera      TEXT NOT NULL DEFAULT '',
    characters  TEXT NOT NULL DEFAULT '',
    action      TEXT NOT NULL DEFAULT '',
    lighting    TEXT NOT NULL DEFAULT '',
    dialogue    TEXT NOT NULL DEFAULT '',
    duration    REAL NOT NULL DEFAULT 0,
    prompt      TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    asset_type      TEXT NOT NULL,
    name            TEXT NOT NULL DEFAULT '',
    prompt          TEXT NOT NULL DEFAULT '',
    negative_prompt TEXT NOT NULL DEFAULT '',
    model_id        TEXT NOT NULL DEFAULT '',
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id             TEXT PRIMARY KEY,
    project_id     TEXT REFERENCES projects(id) ON DELETE CASCADE,
    type           TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'queued',
    progress       INTEGER NOT NULL DEFAULT 0,
    model_id       TEXT NOT NULL DEFAULT '',
    provider_id    TEXT NOT NULL DEFAULT '',
    capability     TEXT NOT NULL DEFAULT '',
    task_id        TEXT NOT NULL DEFAULT '',
    input_payload  TEXT NOT NULL DEFAULT '{}',
    result_payload TEXT NOT NULL DEFAULT '{}',
    output_files   TEXT NOT NULL DEFAULT '[]',
    error          TEXT NOT NULL DEFAULT '',
    error_category TEXT NOT NULL DEFAULT '',
    attempts       INTEGER NOT NULL DEFAULT 0,
    max_attempts   INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL,
    started_at     TEXT,
    completed_at   TEXT,
    heartbeat_at   TEXT,
    paused_at      TEXT,
    cancelled_at   TEXT
);

CREATE TABLE IF NOT EXISTS versions (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    version     INTEGER NOT NULL,
    payload     TEXT NOT NULL DEFAULT '{}',
    file_path   TEXT NOT NULL DEFAULT '',
    model_id    TEXT NOT NULL DEFAULT '',
    provider_id TEXT NOT NULL DEFAULT '',
    job_id      TEXT NOT NULL DEFAULT '',
    is_current  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audio_stems (
    id           TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    shot_id      TEXT REFERENCES shots(id) ON DELETE SET NULL,
    role         TEXT NOT NULL,
    source_type  TEXT NOT NULL,
    file_path    TEXT NOT NULL DEFAULT '',
    format       TEXT NOT NULL DEFAULT 'wav',
    duration     REAL NOT NULL DEFAULT 0,
    model_id     TEXT NOT NULL DEFAULT '',
    provider_id  TEXT NOT NULL DEFAULT '',
    job_id       TEXT NOT NULL DEFAULT '',
    order_index  INTEGER NOT NULL DEFAULT 0,
    payload      TEXT NOT NULL DEFAULT '{}',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audio_mix_sessions (
    id                 TEXT PRIMARY KEY,
    project_id         TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    shot_id            TEXT REFERENCES shots(id) ON DELETE SET NULL,
    status             TEXT NOT NULL DEFAULT 'draft',
    stem_snapshot      TEXT NOT NULL DEFAULT '[]',
    gain_settings      TEXT NOT NULL DEFAULT '{}',
    output_audio_path  TEXT NOT NULL DEFAULT '',
    error              TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dialogue_clips (
    id               TEXT PRIMARY KEY,
    project_id       TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    shot_id          TEXT REFERENCES shots(id) ON DELETE SET NULL,
    audio_asset_id   TEXT NOT NULL DEFAULT '',
    speaker_id       TEXT NOT NULL DEFAULT '',
    voice_profile_id TEXT NOT NULL DEFAULT '',
    start_time       REAL NOT NULL DEFAULT 0,
    end_time         REAL NOT NULL DEFAULT 0,
    version          INTEGER NOT NULL DEFAULT 1,
    alignment        TEXT NOT NULL DEFAULT '{}',
    segments         TEXT NOT NULL DEFAULT '[]',
    job_id           TEXT NOT NULL DEFAULT '',
    order_index      INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS production_edges (
    id               TEXT PRIMARY KEY,
    project_id       TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    upstream_type    TEXT NOT NULL,
    upstream_id      TEXT NOT NULL,
    upstream_version INTEGER,
    downstream_type  TEXT NOT NULL,
    downstream_id    TEXT NOT NULL,
    relation         TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS providers (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    preset_key    TEXT,
    protocol      TEXT NOT NULL DEFAULT 'openai_compat',
    api_base_url  TEXT NOT NULL DEFAULT '',
    needs_key     INTEGER NOT NULL DEFAULT 1,
    enabled       INTEGER NOT NULL DEFAULT 1,
    key_ref       TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    deleted_at    TEXT
);

CREATE TABLE IF NOT EXISTS models (
    id               TEXT PRIMARY KEY,
    provider_id      TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    model_id         TEXT NOT NULL,
    model_type       TEXT NOT NULL DEFAULT 'llm' CHECK (model_type IN ('llm', 'image', 'video', 'audio')),
    capabilities     TEXT NOT NULL DEFAULT '',
    capability_source TEXT NOT NULL DEFAULT 'auto',
    enabled          INTEGER NOT NULL DEFAULT 1,
    is_default_image INTEGER NOT NULL DEFAULT 0,
    is_default_video INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    deleted_at       TEXT,
    UNIQUE (provider_id, model_id)
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shot_dialogue_reviews (
    id                 TEXT PRIMARY KEY,
    project_id         TEXT NOT NULL,
    shot_id            TEXT NOT NULL,
    video_version_id   TEXT NOT NULL,
    mode               TEXT NOT NULL DEFAULT 'manual' CHECK (mode IN ('model', 'manual')),
    model_id           TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'passed', 'flagged')),
    detected_speech    TEXT NOT NULL DEFAULT '',
    expected_dialogue  TEXT NOT NULL DEFAULT '',
    issue              TEXT NOT NULL DEFAULT '',
    decision           TEXT NOT NULL DEFAULT '' CHECK (decision IN ('', 'regenerate', 'delete_shot', 'keep')),
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shot_visual_reviews (
    id                 TEXT PRIMARY KEY,
    project_id         TEXT NOT NULL,
    shot_id            TEXT NOT NULL,
    image_version_id   TEXT NOT NULL,
    review_type        TEXT NOT NULL DEFAULT 'character' CHECK (review_type IN ('character', 'scene', 'continuity', 'costume')),
    mode               TEXT NOT NULL DEFAULT 'manual' CHECK (mode IN ('model', 'manual')),
    model_id           TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'passed', 'flagged')),
    issue              TEXT NOT NULL DEFAULT '',
    decision           TEXT NOT NULL DEFAULT '' CHECK (decision IN ('', 'regenerate', 'delete_shot', 'keep')),
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS story_consistency_reviews (
    id                 TEXT PRIMARY KEY,
    project_id         TEXT NOT NULL,
    shot_id            TEXT NOT NULL,
    mode               TEXT NOT NULL DEFAULT 'manual' CHECK (mode IN ('model', 'manual')),
    model_id           TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'passed', 'flagged')),
    issue              TEXT NOT NULL DEFAULT '',
    decision           TEXT NOT NULL DEFAULT '' CHECK (decision IN ('', 'regenerate', 'delete_shot', 'keep')),
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_novels_project ON novels(project_id);
CREATE INDEX IF NOT EXISTS idx_chapters_novel ON chapters(novel_id);
CREATE INDEX IF NOT EXISTS idx_stories_project ON stories(project_id);
CREATE INDEX IF NOT EXISTS idx_characters_project ON characters(project_id);
CREATE INDEX IF NOT EXISTS idx_locations_project ON locations(project_id);
CREATE INDEX IF NOT EXISTS idx_props_project ON props(project_id);
CREATE INDEX IF NOT EXISTS idx_episodes_project ON episodes(project_id);
CREATE INDEX IF NOT EXISTS idx_scenes_project ON scenes(project_id);
CREATE INDEX IF NOT EXISTS idx_shots_project ON shots(project_id);
CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id);
CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id);
CREATE INDEX IF NOT EXISTS idx_versions_project ON versions(project_id);
CREATE INDEX IF NOT EXISTS idx_audio_stems_project ON audio_stems(project_id);
CREATE INDEX IF NOT EXISTS idx_audio_stems_shot ON audio_stems(shot_id);
CREATE INDEX IF NOT EXISTS idx_audio_mix_sessions_project ON audio_mix_sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_audio_mix_sessions_shot ON audio_mix_sessions(shot_id);
CREATE INDEX IF NOT EXISTS idx_production_edges_project ON production_edges(project_id);
CREATE INDEX IF NOT EXISTS idx_production_edges_upstream ON production_edges(upstream_type, upstream_id);
CREATE INDEX IF NOT EXISTS idx_production_edges_downstream ON production_edges(downstream_type, downstream_id);
CREATE INDEX IF NOT EXISTS idx_models_provider ON models(provider_id);
CREATE INDEX IF NOT EXISTS idx_models_type ON models(model_type);
CREATE INDEX IF NOT EXISTS idx_dialogue_reviews_shot ON shot_dialogue_reviews(project_id, shot_id);
CREATE INDEX IF NOT EXISTS idx_visual_reviews_shot ON shot_visual_reviews(project_id, shot_id);
CREATE INDEX IF NOT EXISTS idx_story_reviews_shot ON story_consistency_reviews(project_id, shot_id);

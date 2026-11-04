CREATE TABLE IF NOT EXISTS image_search_feature (
    media_id INTEGER PRIMARY KEY,
    idp_id INTEGER NOT NULL,
    link TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_mtime_ns INTEGER NOT NULL,
    features_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_image_search_idp ON image_search_feature(idp_id);

"""Additive schema update. Does not drop or reinitialise existing tables."""


class ImageReviewSchema:
    @staticmethod
    def statements():
        return [
            '''CREATE TABLE IF NOT EXISTS image_fingerprint (
                media_id INTEGER PRIMARY KEY, pixel_hash TEXT NOT NULL,
                phash TEXT NOT NULL, dhash TEXT NOT NULL, texture REAL NOT NULL,
                algorithm TEXT NOT NULL)''',
            '''CREATE TABLE IF NOT EXISTS image_review_case (
                id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL,
                revision INTEGER NOT NULL, uploaded_media_id INTEGER NOT NULL,
                matched_media_id INTEGER NOT NULL, matched_project_id INTEGER NOT NULL,
                uploaded_snapshot TEXT NOT NULL, matched_snapshot TEXT NOT NULL,
                matched_title TEXT NOT NULL, matched_designer TEXT NOT NULL,
                score REAL NOT NULL, kind TEXT NOT NULL,
                phash_distance INTEGER NOT NULL, dhash_distance INTEGER NOT NULL,
                algorithm TEXT NOT NULL, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''',
            '''CREATE TABLE IF NOT EXISTS project_review_decision (
                id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL,
                revision INTEGER NOT NULL, manager_id INTEGER NOT NULL,
                decision TEXT NOT NULL CHECK(decision IN ('approved','rejected')),
                reason TEXT NOT NULL, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, revision))''',
            'CREATE INDEX IF NOT EXISTS ix_review_queue ON idp(approval_status)',
            'CREATE INDEX IF NOT EXISTS ix_review_cases ON image_review_case(project_id, revision)',
        ]

    @classmethod
    def apply(cls, db):
        columns = {r[1] for r in db.execute('PRAGMA table_info(idp)')}
        if not columns:
            raise RuntimeError('No idp table found. Check the configured database path.')
        db.execute('BEGIN IMMEDIATE')
        try:
            additions = {
                'approval_status': "TEXT NOT NULL DEFAULT 'approved' CHECK(approval_status IN ('draft','pending','approved','rejected'))",
                'approval_reason': "TEXT NOT NULL DEFAULT ''",
                'image_revision': 'INTEGER NOT NULL DEFAULT 0',
            }
            # Existing projects remain published. New projects are explicitly
            # created as drafts by IDP.create, including after this migration.
            for name, definition in additions.items():
                if name not in columns:
                    db.execute(f'ALTER TABLE idp ADD COLUMN {name} {definition}')
            for sql in cls.statements():
                db.execute(sql)
            db.commit()
        except Exception:
            db.rollback()
            raise
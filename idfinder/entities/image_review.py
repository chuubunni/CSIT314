from contextlib import contextmanager
from idfinder.db import get_db
from idfinder.controller.errors import NotFoundError, PermissionDenied, ValidationError


class ImageReview:
    @staticmethod
    @contextmanager
    def transaction():
        db = get_db()
        db.execute('BEGIN IMMEDIATE')
        try:
            yield
            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def project(project_id):
        return get_db().execute('SELECT * FROM idp WHERE id=?', (project_id,)).fetchone()

    @staticmethod
    def owned(project_id, owner_id):
        project = ImageReview.project(project_id)
        if project is None:
            raise NotFoundError('Project not found.')
        if project['designer_id'] != owner_id:
            raise PermissionDenied('You can only manage your own projects.')
        return project

    @staticmethod
    def media(project_id=None):
        sql = ('SELECT m.*, p.designer_id, p.title, u.name AS designer_name '
               'FROM idp_media m JOIN idp p ON p.id=m.idp_id '
               'JOIN user u ON u.id=p.designer_id')
        return get_db().execute(sql + (' WHERE m.idp_id=?' if project_id is not None else '') +
                                ' ORDER BY m.mediaID', (project_id,) if project_id is not None else ()).fetchall()

    @staticmethod
    def insert_media(project_id, link):
        return get_db().execute('INSERT INTO idp_media(idp_id,link) VALUES(?,?)', (project_id,link)).lastrowid

    @staticmethod
    def fingerprint(media_id):
        return get_db().execute('SELECT * FROM image_fingerprint WHERE media_id=?', (media_id,)).fetchone()

    @staticmethod
    def store_fingerprint(media_id, f):
        get_db().execute('INSERT OR REPLACE INTO image_fingerprint '
                         '(media_id,pixel_hash,phash,dhash,texture,algorithm) VALUES(?,?,?,?,?,?)',
                         (media_id,f['pixel_hash'],f['phash'],f['dhash'],f['texture'],f['algorithm']))

    @staticmethod
    def set_state(project_id, status, reason, revision):
        get_db().execute('UPDATE idp SET approval_status=?,approval_reason=?,image_revision=? WHERE id=?',
                         (status,reason,revision,project_id))

    @staticmethod
    def add_case(project_id, revision, media_id, match, source_snapshot, target_snapshot, result, algorithm):
        get_db().execute('INSERT INTO image_review_case '
            '(project_id,revision,uploaded_media_id,matched_media_id,matched_project_id,'
            'uploaded_snapshot,matched_snapshot,matched_title,matched_designer,score,kind,'
            'phash_distance,dhash_distance,algorithm) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (project_id,revision,media_id,match['mediaID'],match['idp_id'],source_snapshot,target_snapshot,
             match['title'],match['designer_name'],result['score'],result['kind'],
             result['phash_distance'],result['dhash_distance'],algorithm))

    @staticmethod
    def queue():
        return get_db().execute(
            "SELECT p.*,u.name AS designer_name, (SELECT COUNT(*) FROM image_review_case c "
            "WHERE c.project_id=p.id AND c.revision=p.image_revision) AS match_count "
            "FROM idp p JOIN user u ON u.id=p.designer_id WHERE p.approval_status='pending' "
            "ORDER BY p.id").fetchall()

    @staticmethod
    def cases(project_id, revision):
        return get_db().execute('SELECT * FROM image_review_case WHERE project_id=? AND revision=? ORDER BY score DESC,id',
                                 (project_id,revision)).fetchall()

    @staticmethod
    def history(project_id):
        return get_db().execute('SELECT d.*, u.name AS manager_name FROM project_review_decision d '
                                'JOIN user u ON u.id=d.manager_id WHERE project_id=? ORDER BY d.id DESC',
                                (project_id,)).fetchall()

    @staticmethod
    def evidence(case_id):
        return get_db().execute('SELECT * FROM image_review_case WHERE id=?', (case_id,)).fetchone()

    @staticmethod
    def remove_media(media_id):
        get_db().execute('DELETE FROM image_fingerprint WHERE media_id=?',(media_id,))
        get_db().execute('DELETE FROM idp_media WHERE mediaID=?',(media_id,))

    @staticmethod
    def media_access(link):
        return get_db().execute('SELECT p.designer_id,p.approval_status FROM idp_media m '
                                'JOIN idp p ON p.id=m.idp_id WHERE m.link=?',(link,)).fetchall()

    @staticmethod
    def decide(project_id, revision, manager_id, decision, reason):
        # Called within a write transaction. A stale review cannot approve newly
        # uploaded images or overwrite another manager's decision.
        manager = get_db().execute("SELECT id FROM user WHERE id=? AND Usertype='manager'",(manager_id,)).fetchone()
        if manager is None:
            raise PermissionDenied('Platform Manager access required.')
        project = ImageReview.project(project_id)
        if project is None:
            raise NotFoundError('Project not found.')
        if project['approval_status'] != 'pending' or project['image_revision'] != revision:
            raise ValidationError('This submission changed or was already reviewed. Reload the review page.')
        ImageReview.set_state(project_id,decision,reason,revision)
        get_db().execute('INSERT INTO project_review_decision(project_id,revision,manager_id,decision,reason) '
                        'VALUES(?,?,?,?,?)',(project_id,revision,manager_id,decision,reason))
from idfinder.db import get_db


class Review:
    """Entity: a customer's rating + comment for a completed engagement (table review)."""

    @staticmethod
    def create(engagement_id, customer_id, designer_id, rating, comment, sentiment, aspects_json):
        db = get_db()
        cursor = db.execute(
            'INSERT INTO review (engagement_id, customer_id, designer_id, rating, comment,'
            ' sentiment, aspects) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (engagement_id, customer_id, designer_id, rating, comment, sentiment, aspects_json))
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def find(review_id):
        return get_db().execute(
            'SELECT r.*, cu.name AS customer_name, du.name AS designer_name, e.title AS job_title'
            ' FROM review r'
            ' JOIN user cu ON cu.id = r.customer_id'
            ' JOIN user du ON du.id = r.designer_id'
            ' JOIN engagement e ON e.id = r.engagement_id'
            ' WHERE r.id = ?', (review_id,)).fetchone()

    @staticmethod
    def find_by_engagement(engagement_id):
        return get_db().execute('SELECT * FROM review WHERE engagement_id = ?',
                                (engagement_id,)).fetchone()

    @staticmethod
    def update_content(review_id, rating, comment, sentiment, aspects_json):
        db = get_db()
        db.execute(
            'UPDATE review SET rating = ?, comment = ?, sentiment = ?, aspects = ?,'
            ' edit_count = edit_count + 1, updated = CURRENT_TIMESTAMP WHERE id = ?',
            (rating, comment, sentiment, aspects_json, review_id))
        db.commit()

    @staticmethod
    def delete(review_id):
        db = get_db()
        db.execute('DELETE FROM review WHERE id = ?', (review_id,))
        db.commit()

    @staticmethod
    def set_reply(review_id, reply):
        db = get_db()
        db.execute('UPDATE review SET designer_reply = ?,'
                   ' replied_at = CASE WHEN ? IS NULL THEN NULL ELSE CURRENT_TIMESTAMP END'
                   ' WHERE id = ?', (reply, reply, review_id))
        db.commit()

    @staticmethod
    def set_report(review_id, reason):
        db = get_db()
        db.execute('UPDATE review SET reported_reason = ?,'
                   ' reported_at = CASE WHEN ? IS NULL THEN NULL ELSE CURRENT_TIMESTAMP END'
                   ' WHERE id = ?', (reason, reason, review_id))
        db.commit()

    @staticmethod
    def set_status(review_id, status, reason=None):
        db = get_db()
        db.execute('UPDATE review SET status = ?, hidden_reason = ?,'
                   ' moderated_at = CURRENT_TIMESTAMP WHERE id = ?',
                   (status, reason if status == 'hidden' else None, review_id))
        db.commit()

    @staticmethod
    def find_for_designer(designer_id, include_hidden=False):
        """Newest first. Hidden (moderated) reviews are left out unless asked for."""
        sql = ('SELECT r.*, cu.name AS customer_name, e.title AS job_title'
               ' FROM review r JOIN user cu ON cu.id = r.customer_id'
               ' JOIN engagement e ON e.id = r.engagement_id'
               ' WHERE r.designer_id = ?')
        if not include_hidden:
            sql += " AND r.status = 'visible'"
        return get_db().execute(sql + ' ORDER BY r.created DESC, r.id DESC', (designer_id,)).fetchall()

    @staticmethod
    def find_for_moderation():
        """Every review with the facts the integrity checks need (newest first)."""
        return get_db().execute(
            'SELECT r.*, cu.name AS customer_name, cu.created AS customer_joined,'
            ' du.name AS designer_name, e.title AS job_title,'
            ' e.created AS job_created, e.completed_at AS job_completed'
            ' FROM review r'
            ' JOIN user cu ON cu.id = r.customer_id'
            ' JOIN user du ON du.id = r.designer_id'
            ' JOIN engagement e ON e.id = r.engagement_id'
            ' ORDER BY r.created DESC, r.id DESC').fetchall()

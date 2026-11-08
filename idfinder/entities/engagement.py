# C20 / ID20: shared customer-designer hiring/job data model.
from idfinder.db import get_db


class Engagement:
    """Entity: a customer hiring a designer (table engagement). SQL only, no rules."""

    @staticmethod
    def create(customer_id, designer_id, title, message, idp_id=None):
        db = get_db()
        cursor = db.execute(
            'INSERT INTO engagement (customer_id, designer_id, idp_id, title, message)'
            ' VALUES (?, ?, ?, ?, ?)',
            (customer_id, designer_id, idp_id, title, message))
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def find(engagement_id):
        return get_db().execute(
            'SELECT e.*, cu.name AS customer_name, du.name AS designer_name'
            ' FROM engagement e'
            ' JOIN user cu ON cu.id = e.customer_id'
            ' JOIN user du ON du.id = e.designer_id'
            ' WHERE e.id = ?', (engagement_id,)).fetchone()

    @staticmethod
    def set_status(engagement_id, status, expected_status=None):
        db = get_db()
        try:
            cursor = db.execute(
                "UPDATE engagement SET status=?,updated=CURRENT_TIMESTAMP,"
                " completed_at=CASE WHEN ?='completed' THEN CURRENT_TIMESTAMP ELSE completed_at END"
                ' WHERE id=? AND (? IS NULL OR status=?)',
                (status, status, engagement_id, expected_status, expected_status))
            db.commit()
            return cursor.rowcount == 1
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def count_open(customer_id, designer_id):
        """Requests/jobs between this pair that are not finished yet."""
        return get_db().execute(
            "SELECT COUNT(*) FROM engagement WHERE customer_id = ? AND designer_id = ?"
            " AND status IN ('requested', 'ongoing')", (customer_id, designer_id)).fetchone()[0]

    @staticmethod
    def find_for_customer(customer_id):
        return get_db().execute(
            'SELECT e.*, du.name AS designer_name, r.id AS review_id, r.rating AS review_rating'
            ' FROM engagement e'
            ' JOIN user du ON du.id = e.designer_id'
            ' LEFT JOIN review r ON r.engagement_id = e.id'
            ' WHERE e.customer_id = ? ORDER BY e.created DESC, e.id DESC',
            (customer_id,)).fetchall()

    @staticmethod
    def find_for_designer(designer_id):
        return get_db().execute(
            'SELECT e.*, cu.name AS customer_name, r.id AS review_id, r.rating AS review_rating'
            ' FROM engagement e'
            ' JOIN user cu ON cu.id = e.customer_id'
            ' LEFT JOIN review r ON r.engagement_id = e.id'
            ' WHERE e.designer_id = ? ORDER BY e.created DESC, e.id DESC',
            (designer_id,)).fetchall()

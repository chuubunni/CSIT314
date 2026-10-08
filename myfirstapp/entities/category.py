from myfirstapp.db import get_db


class Category:
    """Entity: an IDP category (managed by platform management)."""

    @staticmethod
    def find_all_active():
        return get_db().execute(
            'SELECT id, name FROM category WHERE active = 1 ORDER BY name'
        ).fetchall()

    @staticmethod
    def find(category_id):
        return get_db().execute(
            'SELECT id, name, active FROM category WHERE id = ?', (category_id,)
        ).fetchone()

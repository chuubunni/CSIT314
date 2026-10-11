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

    @staticmethod
    def find_all(search=''):
        return get_db().execute(
            'SELECT c.id, c.name, c.active, COUNT(p.id) AS project_count '
            'FROM category c LEFT JOIN idp p ON p.category_id = c.id '
            'WHERE c.name LIKE ? GROUP BY c.id ORDER BY c.name',
            (f'%{search}%',)
        ).fetchall()

    @staticmethod
    def create(name):
        db = get_db()
        db.execute('INSERT INTO category (name, active) VALUES (?, 1)', (name,))
        db.commit()

    @staticmethod
    def update(category_id, name, active):
        db = get_db()
        db.execute('UPDATE category SET name = ?, active = ? WHERE id = ?',
                   (name, int(active), category_id))
        db.commit()

    @staticmethod
    def delete(category_id):
        db = get_db()
        db.execute('DELETE FROM category WHERE id = ?', (category_id,))
        db.commit()
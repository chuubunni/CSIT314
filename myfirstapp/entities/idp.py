from myfirstapp.db import get_db


class IDP:
    """Entity: an interior design project. Only this class writes SQL for the idp table."""

    @staticmethod
    def create(designer_id, title, description, houseType, category_id, status):
        db = get_db()
        cursor = db.execute(
            'INSERT INTO idp (designer_id, title, description, houseType, category_id, status)'
            ' VALUES (?, ?, ?, ?, ?, ?)',
            (designer_id, title, description, houseType, category_id, status),
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def find(idp_id):
        return get_db().execute(
            'SELECT p.id, p.designer_id, p.houseType, p.category_id, p.title, p.description,'
            ' p.status, p.created, c.name AS category_name'
            ' FROM idp p LEFT JOIN category c ON p.category_id = c.id'
            ' WHERE p.id = ?',
            (idp_id,),
        ).fetchone()

    @staticmethod
    def find_by_designer(designer_id):
        """A designer's IDPs, newest first, each with a cover image (first image, if any)."""
        return get_db().execute(
            'SELECT p.id, p.title, p.description, p.houseType, p.status, p.created,'
            ' c.name AS category_name,'
            ' (SELECT m.link FROM idp_media m WHERE m.idp_id = p.id '
            '  ORDER BY m.mediaID LIMIT 1) AS cover'
            ' FROM idp p LEFT JOIN category c ON p.category_id = c.id'
            ' WHERE p.designer_id = ?'
            ' ORDER BY p.created DESC, p.id DESC',
            (designer_id,),
        ).fetchall()

    @staticmethod
    def find_all():
        """Every IDP (for the home page), newest first."""
        return get_db().execute(
            'SELECT p.id, p.title, p.description, p.houseType, p.status, p.created,'
            ' u.name AS designer_name, d.companyName AS company_name,'
            ' c.name AS category_name,'
            ' (SELECT m.link FROM idp_media m WHERE m.idp_id = p.id'
            '  ORDER BY m.mediaID LIMIT 1) AS cover'
            ' FROM idp p JOIN user u ON p.designer_id = u.id'
            ' LEFT JOIN designer d ON d.userID = p.designer_id'
            ' LEFT JOIN category c ON p.category_id = c.id'
            ' ORDER BY p.created DESC, p.id DESC'
        ).fetchall()

    @staticmethod
    def update(idp_id, title, description, houseType, category_id, status):
        db = get_db()
        db.execute(
            'UPDATE idp SET title = ?, description = ?, houseType = ?, category_id = ?, status = ?'
            ' WHERE id = ?',
            (title, description, houseType, category_id, status, idp_id),
        )
        db.commit()

    @staticmethod
    def delete(idp_id):
        db = get_db()
        db.execute('DELETE FROM idp WHERE id = ?', (idp_id,))
        db.commit()

from myfirstapp.db import get_db


class IDPMedia:
    """Entity: an image or PDF attached to an IDP (table idp_media)."""

    @staticmethod
    def create(idp_id, kind, link, filename=None, caption=None):
        db = get_db()
        cursor = db.execute(
            'INSERT INTO idp_media (idp_id, kind, link, filename, caption)'
            ' VALUES (?, ?, ?, ?, ?)',
            (idp_id, kind, link, filename, caption),
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def find(media_id):
        return get_db().execute(
            'SELECT id, idp_id, kind, link, filename, caption, created'
            ' FROM idp_media WHERE id = ?',
            (media_id,),
        ).fetchone()

    @staticmethod
    def find_by_idp(idp_id, kind=None):
        sql = ('SELECT id, idp_id, kind, link, filename, caption, created'
               ' FROM idp_media WHERE idp_id = ?')
        params = [idp_id]
        if kind is not None:
            sql += ' AND kind = ?'
            params.append(kind)
        sql += ' ORDER BY id'
        return get_db().execute(sql, params).fetchall()

    @staticmethod
    def delete(media_id):
        db = get_db()
        db.execute('DELETE FROM idp_media WHERE id = ?', (media_id,))
        db.commit()

    @staticmethod
    def delete_by_idp(idp_id):
        # explicit delete: SQLite only cascades when PRAGMA foreign_keys is on
        db = get_db()
        db.execute('DELETE FROM idp_media WHERE idp_id = ?', (idp_id,))
        db.commit()
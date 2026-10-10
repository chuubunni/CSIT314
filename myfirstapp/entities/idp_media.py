from myfirstapp.db import get_db


class IDPMedia:
    """Entity: an image attached to an IDP (table idp_media)."""

    @staticmethod
    def create(idp_id, link, caption=None):
        db = get_db()
        cursor = db.execute(
            'INSERT INTO idp_media (idp_id, link, caption)'
            ' VALUES (?, ?, ?)',
            (idp_id, link, caption),
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def find(media_id):
        return get_db().execute(
            'SELECT mediaID, idp_id, link, caption, created'
            ' FROM idp_media WHERE mediaID = ?',
            (media_id,),
        ).fetchone()

    @staticmethod
    def find_by_idp(idp_id):
        sql = ('SELECT mediaID, idp_id, link, caption, created'
               ' FROM idp_media WHERE idp_id = ?')
        params = [idp_id]
        sql += ' ORDER BY mediaID'
        return get_db().execute(sql, params).fetchall()

    @staticmethod
    def delete(mediaID):
        db = get_db()
        db.execute('DELETE FROM idp_media WHERE mediaID = ?', (mediaID,))
        db.commit()

    @staticmethod
    def delete_by_idp(idp_id):
        # explicit delete: SQLite only cascades when PRAGMA foreign_keys is on
        db = get_db()
        db.execute('DELETE FROM idp_media WHERE idp_id = ?', (idp_id,))
        db.commit()

#these two are for image slideshow, may move to customers
    @staticmethod 
    def get_all_images(idp_id):
        db = get_db()
        all_images = db.execute('SELECT * FROM idp_media WHERE idp_id = ?', (idp_id)).fetchall()
        db.commit()
        return all_images

    @staticmethod
    def count_all_images(idp_id):
        db = get_db()
        image_count = db.execute('SELECT COUNT(idp_media) WHERE idp_id = ?',(idp_id)).fetchall()
        db.commit()
        return image_count 
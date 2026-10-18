from idfinder.db import get_db

# An IDP can be in several categories (table idp_category), so the names are
# combined into one value per IDP instead of joining and repeating the row.
_CATEGORY_NAMES = (
    "(SELECT GROUP_CONCAT(c.name, ', ') FROM idp_category ic"
    " JOIN category c ON c.id = ic.category_id"
    " WHERE ic.idp_id = p.id) AS category_names"
)


class IDP:

    @staticmethod
    def create(designer_id, title, description, houseType, price, status, category_ids=()):
        """Insert the IDP and its category links in one transaction. Returns the new id."""
        db = get_db()
        try:
            cursor = db.execute(
                'INSERT INTO idp (designer_id, title, description, houseType, price, status)'
                ' VALUES (?, ?, ?, ?, ?, ?)',
                (designer_id, title, description, houseType, price, status),
            )
            IDP._replace_categories(db, cursor.lastrowid, category_ids)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return cursor.lastrowid

    @staticmethod
    def find(idp_id):
        return get_db().execute(
            'SELECT p.id, p.designer_id, p.houseType, p.title, p.description,'
            ' p.price, p.status, p.created, ' + _CATEGORY_NAMES +
            ' FROM idp p WHERE p.id = ?',
            (idp_id,),
        ).fetchone()

    @staticmethod
    def find_category_ids(idp_id):
        """Ids of the categories this IDP is in (for pre-ticking the edit form)."""
        rows = get_db().execute(
            'SELECT category_id FROM idp_category WHERE idp_id = ?', (idp_id,)
        ).fetchall()
        return [row['category_id'] for row in rows]

    @staticmethod
    def find_by_designer(designer_id):
        """A designer's IDPs, newest first, each with a cover image (first image, if any)."""
        return get_db().execute(
            'SELECT p.id, p.title, p.description, p.houseType, p.price, p.status, p.created,'
            ' ' + _CATEGORY_NAMES + ','
            ' (SELECT m.link FROM idp_media m WHERE m.idp_id = p.id '
            '  ORDER BY m.mediaID LIMIT 1) AS cover'
            ' FROM idp p'
            ' WHERE p.designer_id = ?'
            ' ORDER BY p.created DESC, p.id DESC',
            (designer_id,),
        ).fetchall()

    @staticmethod
    def find_all():
        """Every IDP (for the home page), newest first."""
        return get_db().execute(
            'SELECT p.id, p.title, p.description, p.houseType, p.price, p.status, p.created,'
            ' u.name AS designer_name, co.companyName AS company_name,'
            ' ' + _CATEGORY_NAMES + ','
            ' (SELECT m.link FROM idp_media m WHERE m.idp_id = p.id'
            '  ORDER BY m.mediaID LIMIT 1) AS cover'
            ' FROM idp p JOIN user u ON p.designer_id = u.id'
            ' LEFT JOIN designer d ON d.userID = p.designer_id'
            ' LEFT JOIN company co ON co.companyID = d.companyID'
            ' ORDER BY p.created DESC, p.id DESC'
        ).fetchall()

    @staticmethod
    def update(idp_id, title, description, houseType, status, price, category_ids=None):
        """Update the IDP. If category_ids is given (even empty) the categories are replaced
        too; None leaves them as they are."""
        db = get_db()
        try:
            db.execute(
                'UPDATE idp SET title = ?, description = ?, houseType = ?, status = ?, price = ?'
                ' WHERE id = ?',
                (title, description, houseType, status, price, idp_id),
            )
            if category_ids is not None:
                IDP._replace_categories(db, idp_id, category_ids)
            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def set_categories(idp_id, category_ids):
        """Replace the categories of one IDP."""
        db = get_db()
        try:
            IDP._replace_categories(db, idp_id, category_ids)
            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def delete(idp_id):
        """Delete the IDP and every row that points at it, in one transaction.
        Done explicitly because SQLite only cascades when PRAGMA foreign_keys is on."""
        db = get_db()
        try:
            for table in ('idp_category', 'idp_group_member', 'favourite_idp',
                          'idp_view', 'idp_media'):
                db.execute(f'DELETE FROM {table} WHERE idp_id = ?', (idp_id,))
            db.execute('DELETE FROM idp WHERE id = ?', (idp_id,))
            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def find_all_with_images():
        """Homepage records and their image lists, using two queries (no N+1 queries)."""
        projects = [dict(item) for item in IDP.find_all()]
        if not projects:
            return projects
        ids = [project['id'] for project in projects]
        placeholders = ','.join('?' for _ in ids)
        images = get_db().execute(
            f'SELECT idp_id, link FROM idp_media '
            f'WHERE idp_id IN ({placeholders}) ORDER BY mediaID',
            ids
        ).fetchall()
        lookup = {project_id: [] for project_id in ids}
        for item in images:
            lookup[item['idp_id']].append(dict(item))
        for project in projects:
            project['images'] = lookup[project['id']]
        return projects

    @staticmethod
    def _replace_categories(db, idp_id, category_ids):
        db.execute('DELETE FROM idp_category WHERE idp_id = ?', (idp_id,))
        for category_id in sorted(set(int(c) for c in (category_ids or ()))):
            db.execute('INSERT INTO idp_category (idp_id, category_id) VALUES (?, ?)',
                       (idp_id, category_id))

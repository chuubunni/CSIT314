from idfinder.db import get_db

# An IDP can be in several categories (table idp_category), so the names are
# combined into one value per IDP instead of joining and repeating the row.
_CATEGORY_NAMES = (
    "(SELECT GROUP_CONCAT(c.name, ', ') FROM idp_category ic"
    " JOIN category c ON c.id = ic.category_id"
    " WHERE ic.idp_id = p.id) AS category_names"
)

_INTEREST_COUNTS = (
    "(SELECT COUNT(*) FROM idp_view v"
    " WHERE v.idp_id = p.id) AS view_count,"
    " (SELECT COUNT(*) FROM favourite_idp f"
    " WHERE f.idp_id = p.id) AS favourite_count"
)


class IDP:

    @staticmethod
    def create(designer_id, title, description, property_type, price, status, category_ids=(), property_subtype_id=None):
        db = get_db()
        try:
            cursor = db.execute(
                'INSERT INTO idp (designer_id, title, description, property_type, '
                ' property_subtype_id, price, status)'
                ' VALUES (?, ?, ?, ?, ?, ?, ?)',
                (designer_id, title, description, property_type,
                 property_subtype_id, price, status),
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
<<<<<<< Updated upstream
            '''
            SELECT
                p.id,
                p.designer_id,
                p.property_type,
                p.title,
                p.description,
                p.price,
                p.status,
                p.created,
                p.property_subtype_id,
                (
                    SELECT name
                    FROM property_subtype
                    WHERE id = p.property_subtype_id
                ) AS property_subtype_name,
            '''
            + _CATEGORY_NAMES + ', ' + _INTEREST_COUNTS +
            '''
=======
<<<<<<< HEAD
            '''
            SELECT
                p.id, p.designer_id, p.propertyType,
                p.title, p.description, p.price,
                p.status, p.created, p.property_subtype_id,
                (
                    SELECT name FROM property_subtype
                    WHERE id = p.property_subtype_id
                ) AS property_subtype_name,
            '''
            + _CATEGORY_NAMES +
            ''',
                (
                    SELECT COUNT(*)
                    FROM idp_view v
                    WHERE v.idp_id = p.id
                ) AS view_count,
                (
                    SELECT COUNT(*)
                    FROM favourite_idp f
                    WHERE f.idp_id = p.id
                ) AS favourite_count
>>>>>>> Stashed changes
            FROM idp p
            WHERE p.id = ?
            ''',
            (idp_id,)
<<<<<<< Updated upstream
=======
=======
            'SELECT p.id, p.designer_id, p.property_type, p.title, p.description,'
            ' p.price, p.status, p.created, p.property_subtype_id, '
            " (SELECT name FROM property_subtype WHERE id = p.property_subtype_id) AS property_subtype_name, " + _CATEGORY_NAMES +
            ' FROM idp p WHERE p.id = ?',
            (idp_id,),
>>>>>>> 84d9b5b122c39770b087659e9a8703559280376e
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
=======
<<<<<<< HEAD
            '''
            SELECT
                p.id, p.title, p.description, p.propertyType,
                p.price, p.status, p.created, p.property_subtype_id,
                (
                    SELECT name FROM property_subtype
                    WHERE id = p.property_subtype_id
                ) AS property_subtype_name,
            '''
            + _CATEGORY_NAMES +
            ''',
                (
                    SELECT m.link
                    FROM idp_media m
                    WHERE m.idp_id = p.id
                    ORDER BY m.mediaID
                    LIMIT 1
                ) AS cover,
                (
                    SELECT COUNT(*)
                    FROM idp_view v
                    WHERE v.idp_id = p.id
                ) AS view_count,
                (
                    SELECT COUNT(*)
                    FROM favourite_idp f
                    WHERE f.idp_id = p.id
                ) AS favourite_count
            FROM idp p
            WHERE p.designer_id = ?
            ORDER BY p.created DESC, p.id DESC
            ''',
            (designer_id,)
=======
>>>>>>> Stashed changes
            'SELECT p.id, p.title, p.description, p.property_type, p.price, p.status, p.created,'
            ' p.property_subtype_id,'
            ' (SELECT name FROM property_subtype WHERE id = p.property_subtype_id) AS property_subtype_name,'
            ' ' + _CATEGORY_NAMES + ','+ _INTEREST_COUNTS + ','
            ' (SELECT m.link FROM idp_media m WHERE m.idp_id = p.id '
            '  ORDER BY m.mediaID LIMIT 1) AS cover'
            ' FROM idp p'
            ' WHERE p.designer_id = ?'
            ' ORDER BY p.created DESC, p.id DESC',
            (designer_id,),
>>>>>>> 84d9b5b122c39770b087659e9a8703559280376e
        ).fetchall()

    @staticmethod
    def find_all(property_type='', property_subtype_id=None):
        """Homepage projects, with optional parameterised housing filters."""
        conditions, parameters = [], []
        if property_type:
            conditions.append('p.property_type = ?')
            parameters.append(property_type)
        if property_subtype_id is not None:
            conditions.append('p.property_subtype_id = ?')
            parameters.append(property_subtype_id)
        where = (' WHERE ' + ' AND '.join(conditions) if conditions else '')
        return get_db().execute(
<<<<<<< Updated upstream
            'SELECT p.id,p.designer_id, p.title, p.description, p.property_type, p.price, p.status, p.created,'
=======
<<<<<<< HEAD
            '''
            SELECT
                p.id,
                p.designer_id,
                p.title,
                p.description,
                p.propertyType,
                p.price,
                p.status,
                p.created,
                p.property_subtype_id,
                (
                    SELECT name
                    FROM property_subtype
                    WHERE id = p.property_subtype_id
                ) AS property_subtype_name,
                u.name AS designer_name,
                co.companyName AS company_name,
            '''
            + _CATEGORY_NAMES +
            ''',
                (
                    SELECT m.link
                    FROM idp_media m
                    WHERE m.idp_id = p.id
                    ORDER BY m.mediaID
                    LIMIT 1
                ) AS cover,
                (
                    SELECT COUNT(*)
                    FROM idp_view v
                    WHERE v.idp_id = p.id
                ) AS view_count,
                (
                    SELECT COUNT(*)
                    FROM favourite_idp f
                    WHERE f.idp_id = p.id
                ) AS favourite_count
            FROM idp p
            JOIN user u ON p.designer_id = u.id
            LEFT JOIN designer d ON d.userID = p.designer_id
            LEFT JOIN company co ON co.companyID = d.companyID
            '''
            + where +
            ' ORDER BY p.created DESC, p.id DESC',
=======
            'SELECT p.id, p.title, p.description, p.property_type, p.price, p.status, p.created,'
>>>>>>> Stashed changes
            ' p.property_subtype_id,'
            ' (SELECT name FROM property_subtype WHERE id = p.property_subtype_id) AS property_subtype_name,'
            ' u.name AS designer_name, co.companyName AS company_name,'
            ' ' + _CATEGORY_NAMES + ','+ _INTEREST_COUNTS + ','
            ' (SELECT m.link FROM idp_media m WHERE m.idp_id = p.id'
            '  ORDER BY m.mediaID LIMIT 1) AS cover'
            ' FROM idp p JOIN user u ON p.designer_id = u.id'
            ' LEFT JOIN designer d ON d.userID = p.designer_id'
            ' LEFT JOIN company co ON co.companyID = d.companyID'
            + where + ' ORDER BY p.created DESC, p.id DESC',
>>>>>>> 84d9b5b122c39770b087659e9a8703559280376e
            parameters
        ).fetchall()

    @staticmethod
    def update(idp_id, title, description, property_type, status, price, category_ids=None, property_subtype_id=None):
        db = get_db()
        try:
            db.execute(
                'UPDATE idp SET title = ?, description = ?, property_type = ?, status = ?, price = ?, property_subtype_id = ?'
                ' WHERE id = ?',
                (title, description, property_type, status, price, property_subtype_id, idp_id),
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
    def find_all_with_images(property_type='', property_subtype_id=None):
        """Homepage records and their image lists, using two queries (no N+1 queries)."""
        projects = [dict(item) for item in IDP.find_all(property_type, property_subtype_id)]
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

    # ID19: use the existing idp_category and _replace_categories; no schema migration.
    @staticmethod
    def update_categories_bulk(designer_id, idp_ids, category_ids):
        from idfinder.controller.errors import NotFoundError, PermissionDenied, ValidationError
        db = get_db()
        try:
            db.execute('BEGIN IMMEDIATE')
            for idp_id in idp_ids:
                row = db.execute('SELECT designer_id FROM idp WHERE id=?', (idp_id,)).fetchone()
                if row is None:
                    raise NotFoundError('A selected project no longer exists.')
                if row['designer_id'] != designer_id:
                    raise PermissionDenied('You can only update your own projects.')
            for category_id in category_ids:
                row = db.execute('SELECT active FROM category WHERE id=?', (category_id,)).fetchone()
                if row is None or not row['active']:
                    raise ValidationError('Choose only available categories.')
            for idp_id in idp_ids:
                IDP._replace_categories(db, idp_id, category_ids)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return len(idp_ids)

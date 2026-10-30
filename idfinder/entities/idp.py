from idfinder.db import get_db


# Combine category names without producing duplicate project rows.
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
    def create(
        designer_id,
        title,
        description,
        property_type,
        price,
        status,
        category_ids=(),
        property_subtype_id=None
    ):
        db = get_db()

        try:
            cursor = db.execute(
                'INSERT INTO idp '
                '(designer_id, title, description, property_type, '
                'property_subtype_id, price, status) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (
                    designer_id,
                    title,
                    description,
                    property_type,
                    property_subtype_id,
                    price,
                    status
                )
            )

            IDP._replace_categories(
                db,
                cursor.lastrowid,
                category_ids
            )

            db.commit()

        except Exception:
            db.rollback()
            raise

        return cursor.lastrowid

    @staticmethod
    def find(idp_id):
        return get_db().execute(
            'SELECT p.id, p.designer_id, p.property_type, '
            'p.title, p.description, p.price, p.status, p.created, '
            'p.property_subtype_id, '
            '(SELECT name FROM property_subtype '
            ' WHERE id = p.property_subtype_id) '
            'AS property_subtype_name, '
            + _CATEGORY_NAMES + ', '
            + _INTEREST_COUNTS +
            ' FROM idp p WHERE p.id = ?',
            (idp_id,)
        ).fetchone()

    @staticmethod
    def find_category_ids(idp_id):
        """Get assigned category IDs for the edit form."""
        rows = get_db().execute(
            'SELECT category_id FROM idp_category '
            'WHERE idp_id = ?',
            (idp_id,)
        ).fetchall()

        return [row['category_id'] for row in rows]

    @staticmethod
    def find_by_designer(designer_id, category_id=None, sort_by='newest'):
        """Get a designer's projects, including interest counts,
        optionally only those in one category."""
        query = (
            'SELECT p.id, p.designer_id, p.title, p.description, '
            'p.property_type, p.price, p.status, p.created, '
            'p.property_subtype_id, '
            '(SELECT name FROM property_subtype '
            ' WHERE id = p.property_subtype_id) '
            'AS property_subtype_name, '
            + _CATEGORY_NAMES + ', '
            + _INTEREST_COUNTS + ', '
            '(SELECT m.link FROM idp_media m '
            ' WHERE m.idp_id = p.id '
            ' ORDER BY m.mediaID LIMIT 1) AS cover '
            'FROM idp p '
            'WHERE p.designer_id = ?'
        )
        parameters = [designer_id]

        if category_id is not None:
            # EXISTS keeps one row per project even with several categories.
            query += (
                ' AND EXISTS ('
                'SELECT 1 FROM idp_category ic '
                'WHERE ic.idp_id = p.id '
                'AND ic.category_id = ?'
                ')'
            )
            parameters.append(category_id)

        sort_options = {
            'newest': 'p.created DESC, p.id DESC',
            'views': 'view_count DESC, p.created DESC, p.id DESC',
            'favourites': 'favourite_count DESC, p.created DESC, p.id DESC'
        }

        order_by = sort_options.get(sort_by, sort_options['newest'])
        query += ' ORDER BY ' + order_by

        return get_db().execute(query, parameters).fetchall()

    @staticmethod
    def find_all(
        property_type='',
        property_subtype_id=None,
        category_id=None
    ):
        """Find projects matching all selected homepage filters."""
        conditions = []
        parameters = []

        if property_type:
            conditions.append('p.property_type = ?')
            parameters.append(property_type)

        if property_subtype_id is not None:
            conditions.append('p.property_subtype_id = ?')
            parameters.append(property_subtype_id)

        if category_id is not None:
            # EXISTS prevents duplicate projects when a project
            # belongs to multiple design categories.
            conditions.append(
                'EXISTS ('
                'SELECT 1 FROM idp_category ic '
                'JOIN category c ON c.id = ic.category_id '
                'WHERE ic.idp_id = p.id '
                'AND ic.category_id = ? '
                'AND c.active = 1'
                ')'
            )
            parameters.append(category_id)

        where = ''

        if conditions:
            where = ' WHERE ' + ' AND '.join(conditions)

        return get_db().execute(
            'SELECT p.id, p.designer_id, p.title, p.description, '
            'p.property_type, p.price, p.status, p.created, '
            'p.property_subtype_id, '
            '(SELECT name FROM property_subtype '
            ' WHERE id = p.property_subtype_id) '
            'AS property_subtype_name, '
            'u.name AS designer_name, '
            'co.companyName AS company_name, '
            + _CATEGORY_NAMES + ', '
            + _INTEREST_COUNTS + ', '
            '(SELECT m.link FROM idp_media m '
            ' WHERE m.idp_id = p.id '
            ' ORDER BY m.mediaID LIMIT 1) AS cover '
            'FROM idp p '
            'JOIN user u ON p.designer_id = u.id '
            'LEFT JOIN designer d ON d.userID = p.designer_id '
            'LEFT JOIN company co ON co.companyID = d.companyID'
            + where
            + ' ORDER BY p.created DESC, p.id DESC',
            parameters
        ).fetchall()

    @staticmethod
    def update(
        idp_id,
        title,
        description,
        property_type,
        status,
        price,
        category_ids=None,
        property_subtype_id=None
    ):
        db = get_db()

        try:
            db.execute(
                'UPDATE idp SET '
                'title = ?, description = ?, property_type = ?, '
                'status = ?, price = ?, property_subtype_id = ? '
                'WHERE id = ?',
                (
                    title,
                    description,
                    property_type,
                    status,
                    price,
                    property_subtype_id,
                    idp_id
                )
            )

            if category_ids is not None:
                IDP._replace_categories(
                    db,
                    idp_id,
                    category_ids
                )

            db.commit()

        except Exception:
            db.rollback()
            raise

    @staticmethod
    def set_categories(idp_id, category_ids):
        """Replace the categories of one project."""
        db = get_db()

        try:
            IDP._replace_categories(
                db,
                idp_id,
                category_ids
            )

            db.commit()

        except Exception:
            db.rollback()
            raise

    @staticmethod
    def delete(idp_id):
        """Delete a project and its related records."""
        db = get_db()

        try:
            for table in (
                'idp_category',
                'idp_group_member',
                'favourite_idp',
                'idp_view',
                'idp_media'
            ):
                db.execute(
                    f'DELETE FROM {table} WHERE idp_id = ?',
                    (idp_id,)
                )

            db.execute(
                'DELETE FROM idp WHERE id = ?',
                (idp_id,)
            )

            db.commit()

        except Exception:
            db.rollback()
            raise

    @staticmethod
    def find_all_with_images(
        property_type='',
        property_subtype_id=None,
        category_id=None
    ):
        """Get matching projects and their slideshow images."""
        projects = [
            dict(item)
            for item in IDP.find_all(
                property_type,
                property_subtype_id,
                category_id
            )
        ]

        if not projects:
            return projects

        ids = [project['id'] for project in projects]
        placeholders = ','.join('?' for _ in ids)

        images = get_db().execute(
            'SELECT idp_id, link FROM idp_media '
            f'WHERE idp_id IN ({placeholders}) '
            'ORDER BY mediaID',
            ids
        ).fetchall()

        lookup = {
            project_id: []
            for project_id in ids
        }

        for item in images:
            lookup[item['idp_id']].append(dict(item))

        for project in projects:
            project['images'] = lookup[project['id']]

        return projects

    @staticmethod
    def _replace_categories(db, idp_id, category_ids):
        db.execute(
            'DELETE FROM idp_category WHERE idp_id = ?',
            (idp_id,)
        )

        unique_ids = sorted(
            set(int(c) for c in (category_ids or ()))
        )

        for category_id in unique_ids:
            db.execute(
                'INSERT INTO idp_category '
                '(idp_id, category_id) VALUES (?, ?)',
                (idp_id, category_id)
            )

    @staticmethod
    def update_categories_bulk(
        designer_id,
        idp_ids,
        category_ids
    ):
        """Keep the existing bulk category update functionality."""
        from idfinder.controller.errors import (
            NotFoundError,
            PermissionDenied,
            ValidationError
        )

        db = get_db()

        try:
            db.execute('BEGIN IMMEDIATE')

            for idp_id in idp_ids:
                row = db.execute(
                    'SELECT designer_id FROM idp WHERE id = ?',
                    (idp_id,)
                ).fetchone()

                if row is None:
                    raise NotFoundError(
                        'A selected project no longer exists.'
                    )

                if row['designer_id'] != designer_id:
                    raise PermissionDenied(
                        'You can only update your own projects.'
                    )

            for category_id in category_ids:
                row = db.execute(
                    'SELECT active FROM category WHERE id = ?',
                    (category_id,)
                ).fetchone()

                if row is None or not row['active']:
                    raise ValidationError(
                        'Choose only available categories.'
                    )

            for idp_id in idp_ids:
                IDP._replace_categories(
                    db,
                    idp_id,
                    category_ids
                )

            db.commit()

        except Exception:
            db.rollback()
            raise

        return len(idp_ids)
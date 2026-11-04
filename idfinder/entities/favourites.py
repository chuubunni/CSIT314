# C08: use the existing favourite_idp table; no new favourites schema is needed.
from idfinder.db import get_db
from idfinder.controller.errors import NotFoundError, PermissionDenied


class Favourites:
    @staticmethod
    def add(customer_id, idp_id):
        # C08: lock, validate references and insert together; duplicate saves are safe.
        db = get_db()
        try:
            db.execute('BEGIN IMMEDIATE')
            customer = db.execute("SELECT c.cust_id FROM customer c JOIN user u ON u.id=c.cust_id "
                                  "WHERE c.cust_id=? AND u.Usertype='customer'", (customer_id,)).fetchone()
            if customer is None:
                raise PermissionDenied('A customer profile is required to save projects.')
            if db.execute("SELECT id FROM idp WHERE id=? AND approval_status='approved'", (idp_id,)).fetchone() is None:
                raise NotFoundError('This project no longer exists.')
            cursor = db.execute('INSERT INTO favourite_idp(customer_id,idp_id) VALUES (?,?) '
                                'ON CONFLICT(customer_id,idp_id) DO NOTHING', (customer_id, idp_id))
            added = cursor.rowcount == 1
            db.commit()
        except Exception:
            db.rollback()
            raise
        return added
    
    @staticmethod
    def find_comparison(customer_id, first_id, second_id):
        return get_db().execute(
            '''
            SELECT
                p.id,
                p.title,
                p.price,
                p.property_type,
                p.property_subtype_id,
                p.designer_id,
                u.name AS designer_name,
                (
                    SELECT name
                    FROM property_subtype
                    WHERE id = p.property_subtype_id
                ) AS property_subtype_name,
                (
                    SELECT GROUP_CONCAT(c.name, ', ')
                    FROM idp_category ic
                    JOIN category c ON c.id = ic.category_id
                    WHERE ic.idp_id = p.id
                ) AS category_names,
                (
                    SELECT COUNT(*)
                    FROM favourite_idp f
                    WHERE f.idp_id = p.id
                ) AS favourite_count,
                (
                    SELECT AVG(r.rating)
                    FROM review r
                    WHERE r.designer_id = p.designer_id
                      AND r.status = 'visible'
                ) AS average_rating,
                (
                    SELECT COUNT(*)
                    FROM review r
                    WHERE r.designer_id = p.designer_id
                      AND r.status = 'visible'
                ) AS review_count
            FROM idp p
            JOIN user u ON u.id = p.designer_id
            WHERE p.id IN (?, ?)
              AND p.approval_status = 'approved'
              AND EXISTS (
                  SELECT 1
                  FROM favourite_idp own
                  WHERE own.idp_id = p.id
                    AND own.customer_id = ?
              )
            ''',
            (first_id, second_id, customer_id)
        ).fetchall()


    @staticmethod
    def find_projects(customer_id):
        # C09: the customer's saved projects, most recently saved first, each with a cover image.
        return get_db().execute(
            'SELECT p.id, p.title, p.description, p.property_type, p.price, p.status,'
            ' (SELECT name FROM property_subtype WHERE id = p.property_subtype_id) AS property_subtype_name,'
            ' u.name AS designer_name, co.companyName AS company_name,'
            " (SELECT GROUP_CONCAT(c.name, ', ') FROM idp_category ic"
            '  JOIN category c ON c.id = ic.category_id WHERE ic.idp_id = p.id) AS category_names,'
            ' (SELECT m.link FROM idp_media m WHERE m.idp_id = p.id'
            '  ORDER BY m.mediaID LIMIT 1) AS cover,'
            ' f.created AS saved_at'
            ' FROM favourite_idp f JOIN idp p ON p.id = f.idp_id'
            ' JOIN user u ON u.id = p.designer_id'
            ' LEFT JOIN designer d ON d.userID = p.designer_id'
            ' LEFT JOIN company co ON co.companyID = d.companyID'
            " WHERE f.customer_id = ? AND p.approval_status = 'approved'"
            ' ORDER BY f.created DESC, p.id DESC',
            (customer_id,)).fetchall()

    @staticmethod
    def find_project_ids(customer_id):
        # C08: return only this customer's saved IDs to mark project cards.
        return {row['idp_id'] for row in get_db().execute(
            "SELECT f.idp_id FROM favourite_idp f JOIN idp p ON p.id=f.idp_id WHERE f.customer_id=? AND p.approval_status='approved'", (customer_id,))}
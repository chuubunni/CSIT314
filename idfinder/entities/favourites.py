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
            if db.execute('SELECT id FROM idp WHERE id=?', (idp_id,)).fetchone() is None:
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
    def find_project_ids(customer_id):
        # C08: return only this customer's saved IDs to mark project cards.
        return {row['idp_id'] for row in get_db().execute(
            'SELECT idp_id FROM favourite_idp WHERE customer_id=?', (customer_id,))}

from idfinder.db import get_db


class PropertyType:
    """Entity: a property type (HDB / Condo / Landed). idp.property_type stores the code."""

    @staticmethod
    def find_all():
        return get_db().execute(
            'SELECT id, code, name FROM property_type ORDER BY id'
        ).fetchall()

    @staticmethod
    def find(property_type_id):
        return get_db().execute(
            'SELECT id, code, name FROM property_type WHERE id = ?', (property_type_id,)
        ).fetchone()

    @staticmethod
    def find_by_code(code):
        return get_db().execute(
            'SELECT id, code, name FROM property_type WHERE code = ?', (code,)
        ).fetchone()

    @staticmethod
    def find_all_with_usage():
        """Every type with how many subtypes, projects and customers use it (PM14)."""
        return get_db().execute(
            'SELECT t.id, t.code, t.name,'
            ' (SELECT COUNT(*) FROM property_subtype s WHERE s.property_type_id = t.id) AS subtype_count,'
            ' (SELECT COUNT(*) FROM idp p WHERE p.property_type = t.code COLLATE NOCASE) AS project_count,'
            ' (SELECT COUNT(*) FROM customer c WHERE c.current_property_type = t.code COLLATE NOCASE) AS customer_count'
            ' FROM property_type t ORDER BY t.id'
        ).fetchall()

    @staticmethod
    def delete(property_type_id):
        """PM14: delete a type and its subtypes together (all or nothing)."""
        db = get_db()
        try:
            db.execute('DELETE FROM property_subtype WHERE property_type_id = ?', (property_type_id,))
            db.execute('DELETE FROM property_type WHERE id = ?', (property_type_id,))
            db.commit()
        except Exception:
            db.rollback()
            raise


class PropertySubtype:
    """Entity: a subtype under a property type (for example 4-Room under HDB)."""

    # project_count = how many IDPs use the subtype, so managers can't delete one that is in use
    _SELECT = (
        'SELECT s.id, s.property_type_id, t.code AS type_code, t.name AS type_name, s.name,'
        ' (SELECT COUNT(*) FROM idp p WHERE p.property_subtype_id = s.id) AS project_count'
        ' FROM property_subtype s JOIN property_type t ON t.id = s.property_type_id'
    )

    @staticmethod
    def find_all(property_type_id=None):
        sql, params = PropertySubtype._SELECT, ()
        if property_type_id is not None:
            sql += ' WHERE s.property_type_id = ?'
            params = (property_type_id,)
        return get_db().execute(sql + ' ORDER BY s.property_type_id, s.id', params).fetchall()

    @staticmethod
    def find(subtype_id):
        """One subtype with its type code, so callers can check it matches an IDP's property_type."""
        return get_db().execute(PropertySubtype._SELECT + ' WHERE s.id = ?', (subtype_id,)).fetchone()

    @staticmethod
    def create(property_type_id, name):
        db = get_db()
        cursor = db.execute('INSERT INTO property_subtype (property_type_id, name) VALUES (?, ?)',
                            (property_type_id, name))
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update(subtype_id, name):
        db = get_db()
        db.execute('UPDATE property_subtype SET name = ? WHERE id = ?', (name, subtype_id))
        db.commit()

    @staticmethod
    def delete(subtype_id):
        db = get_db()
        db.execute('DELETE FROM property_subtype WHERE id = ?', (subtype_id,))
        db.commit()


class Housing:

    @staticmethod
    def types():
        return PropertyType.find_all()

    @staticmethod
    def codes():
        """Codes of the property types that currently exist, e.g. ['HDB', 'Condo']."""
        return [t['code'] for t in PropertyType.find_all()]

    @staticmethod
    def types_with_usage():
        return PropertyType.find_all_with_usage()

    @staticmethod
    def delete_type(property_type_id):
        PropertyType.delete(property_type_id)

    @staticmethod
    def subtypes(property_type_id=None):
        return PropertySubtype.find_all(property_type_id)

    @staticmethod
    def find_type(code):
        return PropertyType.find_by_code(code)

    @staticmethod
    def find_subtype(subtype_id):
        return PropertySubtype.find(subtype_id)
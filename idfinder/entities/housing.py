from idfinder.db import get_db


class Housing:
    """Database housing options shared by project forms and homepage filters."""

    @staticmethod
    def types():
        return [dict(r) for r in get_db().execute(
            'SELECT id, code, name FROM property_type ORDER BY id')]

    @staticmethod
    def subtypes():
        return [dict(r) for r in get_db().execute(
            'SELECT s.id, s.property_type_id, s.name, t.code AS type_code '
            'FROM property_subtype s JOIN property_type t ON t.id = s.property_type_id '
            'ORDER BY t.id, s.id')]

    @staticmethod
    def find_type(code):
        return get_db().execute('SELECT * FROM property_type WHERE code = ?', (code,)).fetchone()

    @staticmethod
    def find_subtype(subtype_id):
        return get_db().execute(
            'SELECT s.id, s.name, t.code AS type_code FROM property_subtype s '
            'JOIN property_type t ON t.id = s.property_type_id WHERE s.id = ?',
            (subtype_id,)).fetchone()
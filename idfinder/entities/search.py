from idfinder.db import get_db


class DesignerSearch:
    """Entity: read-only queries for finding interior designers."""

    @staticmethod
    def find_by_name(name=''):
        """Designers whose name contains `name` (case-insensitive), A-Z.

        An empty `name` returns every designer. The text is passed as a query
        parameter, and LIKE wildcards typed by the user (% and _) are escaped so
        they are matched literally.
        """
        escaped = name.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        return get_db().execute(
            'SELECT u.id, u.name, co.companyName AS company_name,'
            ' (SELECT COUNT(*) FROM idp p WHERE p.designer_id = u.id) AS project_count'
            ' FROM designer d'
            ' JOIN user u ON u.id = d.userID'
            ' LEFT JOIN company co ON co.companyID = d.companyID'
            " WHERE u.name LIKE ? ESCAPE '\\'"
            ' ORDER BY u.name COLLATE NOCASE, u.id',
            ('%' + escaped + '%',),
        ).fetchall()

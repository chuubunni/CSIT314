from idfinder.db import get_db


class DesignerStats:
    """Entity: read-only queries that collect the raw numbers behind ratings and the leaderboard.

    Only counting happens here. Turning the numbers into a score is the controller's job.
    """

    @staticmethod
    def designers(category_id=None, property_type=None):
        """Every designer (id, name, company), optionally only those with a project in a
        design category and/or housing type."""
        sql = ('SELECT u.id, u.name, co.companyName AS company'
               ' FROM designer d JOIN user u ON u.id = d.userID'
               ' LEFT JOIN company co ON co.companyID = d.companyID WHERE 1 = 1')
        params = []
        if category_id:
            sql += (' AND EXISTS (SELECT 1 FROM idp p JOIN idp_category ic ON ic.idp_id = p.id'
                    " WHERE p.designer_id = u.id AND p.approval_status='approved' AND ic.category_id = ?)")
            params.append(category_id)
        if property_type:
            sql += (' AND EXISTS (SELECT 1 FROM idp p WHERE p.designer_id = u.id'
                    " AND p.approval_status='approved' AND p.property_type = ?)")
            params.append(property_type)
        return [dict(r) for r in get_db().execute(sql + ' ORDER BY u.name COLLATE NOCASE, u.id', params)]

    @staticmethod
    def visible_reviews():
        """(designer_id, rating, sentiment, created) of every visible review."""
        return [dict(r) for r in get_db().execute(
            "SELECT designer_id, rating, sentiment, created FROM review WHERE status = 'visible'")]

    @staticmethod
    def engagement_counts():
        """Per designer: how many jobs were requested / accepted / completed / declined."""
        rows = get_db().execute(
            "SELECT designer_id, COUNT(*) AS requested,"
            " SUM(status IN ('ongoing', 'completed')) AS accepted,"
            " SUM(status = 'completed') AS completed,"
            " SUM(status = 'declined') AS declined"
            " FROM engagement GROUP BY designer_id")
        return {r['designer_id']: {k: (r[k] or 0) for k in ('requested', 'accepted', 'completed', 'declined')}
                for r in rows}

    @staticmethod
    def interest():
        """Per designer: projects, views and shortlists across all their projects.
        Counted in sub-queries before joining, so the numbers are not multiplied."""
        rows = get_db().execute(
            'SELECT p.designer_id, COUNT(*) AS projects,'
            ' COALESCE(SUM(v.n), 0) AS views, COALESCE(SUM(f.n), 0) AS favourites'
            ' FROM idp p'
            ' LEFT JOIN (SELECT idp_id, COUNT(*) AS n FROM idp_view GROUP BY idp_id) v ON v.idp_id = p.id'
            ' LEFT JOIN (SELECT idp_id, COUNT(*) AS n FROM favourite_idp GROUP BY idp_id) f ON f.idp_id = p.id'
            " WHERE p.approval_status='approved' GROUP BY p.designer_id")
        return {r['designer_id']: dict(r) for r in rows}

    @staticmethod
    def reply_counts():
        """Per designer: visible reviews and how many of them got a reply."""
        rows = get_db().execute(
            "SELECT designer_id, COUNT(*) AS reviews, SUM(designer_reply IS NOT NULL) AS replied"
            " FROM review WHERE status = 'visible' GROUP BY designer_id")
        return {r['designer_id']: {'reviews': r['reviews'], 'replied': r['replied'] or 0} for r in rows}

    @staticmethod
    def designer_header(designer_id):
        return get_db().execute(
            'SELECT u.id, u.name, co.companyName AS company, u.created'
            ' FROM designer d JOIN user u ON u.id = d.userID'
            ' LEFT JOIN company co ON co.companyID = d.companyID WHERE u.id = ?',
            (designer_id,)).fetchone()

    @staticmethod
    def designer_projects(designer_id, limit=6):
        return [dict(r) for r in get_db().execute(
            'SELECT p.id, p.title, p.property_type, p.price,'
            ' (SELECT link FROM idp_media m WHERE m.idp_id = p.id ORDER BY m.mediaID LIMIT 1) AS image'
            " FROM idp p WHERE p.designer_id = ? AND p.approval_status='approved' ORDER BY p.created DESC, p.id DESC LIMIT ?",
            (designer_id, limit))]
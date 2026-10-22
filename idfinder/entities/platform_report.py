from idfinder.db import get_db


class PlatformReport:
    """SQL-only reporting entity. Periods use SQLite UTC timestamps."""

    @staticmethod
    def overview(period='daily'):
        start = {'daily': '-1 day', 'weekly': '-7 days', 'monthly': '-1 month'}[period]
        db = get_db()
        def count(sql):
            return db.execute(sql, (start,)).fetchone()[0]
        return {
            'projects': count("SELECT COUNT(*) FROM idp WHERE created >= datetime('now', ?)"),
            'views': count("SELECT COUNT(*) FROM idp_view WHERE viewed_at >= datetime('now', ?)"),
            'favourites': count("SELECT COUNT(*) FROM favourite_idp WHERE created >= datetime('now', ?)"),
            'users': count("SELECT COUNT(*) FROM user WHERE created >= datetime('now', ?)"),
        }

    @staticmethod
    def interest():
        return get_db().execute(
            'SELECT p.id, p.title, '
            '(SELECT COUNT(*) FROM idp_view v WHERE v.idp_id=p.id) AS views, '
            '(SELECT COUNT(*) FROM favourite_idp f WHERE f.idp_id=p.id) AS favourites '
            'FROM idp p ORDER BY views DESC, favourites DESC, p.id DESC'
        ).fetchall()

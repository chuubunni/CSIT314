from datetime import timedelta

from idfinder.db import get_db


class PlatformCharts:
    """Entity: SQL-only queries that feed the platform manager's graphs.

    PM21 -> daily_activity()          counts per day over a date window
    PM23 -> interest_by_category()    views and shortlists grouped by design category

    Timestamps are stored by SQLite as UTC text ('YYYY-MM-DD HH:MM:SS'), so a "day"
    here is a UTC day, the same as the existing report on the dashboard.
    """

    # (key in the result, table, timestamp column)
    ACTIVITY_SOURCES = (
        ('projects', 'idp', 'created'),
        ('views', 'idp_view', 'viewed_at'),
        ('favourites', 'favourite_idp', 'created'),
        ('users', 'user', 'created'),
    )

    @staticmethod
    def daily_activity(start, end):
        """Counts per day from `start` to `end` inclusive (both datetime.date).

        Returns {'labels': ['YYYY-MM-DD', ...], 'projects': [...], 'views': [...],
                 'favourites': [...], 'users': [...]}.
        Every list has one entry per day, with 0 for days that had no activity
        (SQL GROUP BY only returns days that have rows, so gaps are filled here).
        """
        if end < start:
            raise ValueError('end must not be before start')

        days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        labels = [d.isoformat() for d in days]
        # Half-open range [start, day after end). A plain range on the timestamp
        # column can use the existing indexes (ix_idp_view_time, ix_fav_idp_created, ...).
        lower = start.isoformat()
        upper = (end + timedelta(days=1)).isoformat()

        db = get_db()
        result = {'labels': labels}
        for key, table, column in PlatformCharts.ACTIVITY_SOURCES:
            # table and column come from the constant above, never from user input
            rows = db.execute(
                f'SELECT date({column}) AS day, COUNT(*) AS n FROM "{table}" '
                f'WHERE {column} >= ? AND {column} < ? GROUP BY day',
                (lower, upper),
            ).fetchall()
            per_day = {row['day']: row['n'] for row in rows}
            result[key] = [per_day.get(label, 0) for label in labels]
        return result

    @staticmethod
    def interest_by_category():
        """One row per category: id, name, active, projects, views, favourites.

        A project can be in several categories (idp_category is many-to-many), so it
        counts towards each of its categories. Views and favourites are counted per
        project first and only then joined, otherwise joining both tables at once
        would multiply the rows (views x favourites) and inflate the totals.
        Categories with no projects are kept, with zeros.
        Most viewed first, then most shortlisted, then by name.
        """
        rows = get_db().execute(
            'SELECT c.id, c.name, c.active, '
            '       COUNT(ic.idp_id) AS projects, '
            '       COALESCE(SUM(v.n), 0) AS views, '
            '       COALESCE(SUM(f.n), 0) AS favourites '
            'FROM category c '
            'LEFT JOIN idp_category ic ON ic.category_id = c.id '
            'LEFT JOIN (SELECT idp_id, COUNT(*) AS n FROM idp_view '
            '           GROUP BY idp_id) v ON v.idp_id = ic.idp_id '
            'LEFT JOIN (SELECT idp_id, COUNT(*) AS n FROM favourite_idp '
            '           GROUP BY idp_id) f ON f.idp_id = ic.idp_id '
            'GROUP BY c.id '
            'ORDER BY views DESC, favourites DESC, c.name'
        ).fetchall()
        return [dict(row) for row in rows]

from datetime import timedelta

from idfinder.db import get_db


class PlatformCharts:
    """ENTITY for the platform manager's graphs. SQL only, no business rules.

    PM21 -> daily_activity()          counts per day over a date window
    PM23 -> interest_by_category()    views and shortlists grouped by design category

    Timestamps are stored by SQLite as UTC text ('YYYY-MM-DD HH:MM:SS'), so a "day"
    here is a UTC day, the same as the existing report on the dashboard.
    """

    # ======================================================================
    # PM21 START: weekly activity graph (entity part)
    # ======================================================================

    # The four measures shown on the graph: (name in the result, table, timestamp column)
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
        Every list has one entry per day, with 0 for days that had no activity.
        """
        if end < start:
            raise ValueError('end must not be before start')

        # The full list of days we want on the graph, e.g. 7 dates for a week.
        days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        labels = [d.isoformat() for d in days]

        # HARD PART 1: the date range.
        # We want every second of the last day, so the range runs from the start day up to
        # (but not including) the day AFTER the end day:  start <= time < end + 1 day.
        # This also lets SQLite use the existing indexes on the timestamp columns.
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

            # HARD PART 2: filling the gaps.
            # SQL's GROUP BY only returns days that HAVE rows, so a quiet day would simply
            # be missing. We go through the full list of days and use 0 for missing ones,
            # so the graph always has one bar for every day.
            result[key] = [per_day.get(label, 0) for label in labels]
        return result

    # ======================= PM21 END (entity part) =======================

    # ======================================================================
    # PM23 START: project interest by design category (entity part)
    # ======================================================================
    @staticmethod
    def interest_by_category():
        """One row per category: id, name, active, projects, views, favourites.

        A project can be in several categories (idp_category is many-to-many), so it
        counts towards each of its categories.
        Categories with no projects are kept, with zeros.
        Most viewed first, then most shortlisted, then by name.
        """
        # HARD PART: avoiding inflated counts.
        # Views and favourites are counted per project in two small sub-queries (v and f)
        # BEFORE they are joined. If we joined the raw views table and the raw favourites
        # table together, every project's rows would multiply (a project with 3 views and
        # 2 favourites would give 3 x 2 = 6 rows) and the totals would be wrong.
        rows = get_db().execute(
            'SELECT c.id, c.name, c.active, '
            '       COUNT(ic.idp_id) AS projects, '
            '       COALESCE(SUM(v.n), 0) AS views, '
            '       COALESCE(SUM(f.n), 0) AS favourites '
            'FROM category c '
            # LEFT JOIN keeps categories that have no projects (they show as 0)
            'LEFT JOIN idp_category ic ON ic.category_id = c.id '
            'LEFT JOIN (SELECT idp_id, COUNT(*) AS n FROM idp_view '
            '           GROUP BY idp_id) v ON v.idp_id = ic.idp_id '
            'LEFT JOIN (SELECT idp_id, COUNT(*) AS n FROM favourite_idp '
            '           GROUP BY idp_id) f ON f.idp_id = ic.idp_id '
            'GROUP BY c.id '
            'ORDER BY views DESC, favourites DESC, c.name'
        ).fetchall()
        return [dict(row) for row in rows]

    # ======================= PM23 END (entity part) =======================

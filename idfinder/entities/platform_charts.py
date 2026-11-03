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

    # ======================================================================
    # PM21 (extra): when are projects viewed?  weekday x hour grid
    # ======================================================================
    @staticmethod
    def views_by_weekday_hour(start, end, offset_minutes=0):
        """Project views from `start` to `end` inclusive (UTC days), counted per weekday and hour.

        `offset_minutes` shifts the clock to the viewer's time zone (Singapore = 480), so
        "8 pm" on the grid is 8 pm on the manager's own clock.
        Returns a 7 x 24 list of lists: row 0 = Monday ... row 6 = Sunday, column = hour 0-23.
        """
        modifier = f'{int(offset_minutes):+d} minutes'          # e.g. '+480 minutes'; an int, never user text
        rows = get_db().execute(
            "SELECT CAST(strftime('%w', datetime(viewed_at, ?)) AS INTEGER) AS dow,"
            " CAST(strftime('%H', datetime(viewed_at, ?)) AS INTEGER) AS hour, COUNT(*) AS n"
            " FROM idp_view WHERE viewed_at >= ? AND viewed_at < ? GROUP BY dow, hour",
            (modifier, modifier, start.isoformat(), (end + timedelta(days=1)).isoformat())).fetchall()
        grid = [[0] * 24 for _ in range(7)]
        for row in rows:
            grid[(row['dow'] + 6) % 7][row['hour']] = row['n']      # SQLite: 0 = Sunday -> we want Monday first
        return grid

    # ======================================================================
    # PM23 (extra): weekly views per category (for the area chart and the growth chart)
    # ======================================================================
    @staticmethod
    def weekly_category_views(last_day, weeks=8):
        """Views per category in each of the last `weeks` weeks; the last week ends on `last_day`.

        Returns (week_start_dates, {category_id: {'name': ..., 'weeks': [n, n, ...]}}).
        A project in several categories counts towards each, like the rest of PM23.
        """
        first_day = last_day - timedelta(days=weeks * 7 - 1)
        rows = get_db().execute(
            "SELECT CAST((julianday(date(v.viewed_at)) - julianday(?)) / 7 AS INTEGER) AS week,"
            " c.id, c.name, COUNT(*) AS n"
            " FROM idp_view v JOIN idp_category ic ON ic.idp_id = v.idp_id"
            " JOIN category c ON c.id = ic.category_id"
            " WHERE v.viewed_at >= ? AND v.viewed_at < ? GROUP BY week, c.id",
            (first_day.isoformat(), first_day.isoformat(), (last_day + timedelta(days=1)).isoformat())).fetchall()
        starts = [(first_day + timedelta(days=7 * i)) for i in range(weeks)]
        series = {}
        for row in rows:
            entry = series.setdefault(row['id'], {'name': row['name'], 'weeks': [0] * weeks})
            if 0 <= row['week'] < weeks:
                entry['weeks'][row['week']] = row['n']
        return starts, series

    # ======================================================================
    # Ratings overview for the manager (from the review tables)
    # ======================================================================
    @staticmethod
    def visible_review_ratings():
        """[(rating, created)] of every visible review. Empty if the review tables do not exist yet."""
        try:
            return [(r['rating'], r['created']) for r in get_db().execute(
                "SELECT rating, created FROM review WHERE status = 'visible'")]
        except Exception:
            return []


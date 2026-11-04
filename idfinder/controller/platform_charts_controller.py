import logging
from datetime import date, datetime, timedelta, timezone

from idfinder.controller import forecasting
from idfinder.controller.errors import ValidationError
from idfinder.controller.ranking import to_datetime
from idfinder.entities.platform_charts import PlatformCharts


class PlatformChartsController:
    """Control (the "C" in ECB): the rules for the platform manager's graphs.

    No Flask objects and no SQL in here. It checks the input, asks the entity for the
    data, then does the calculations (totals, change compared with the week before).
    """

    METRICS = ('projects', 'views', 'favourites', 'users')   # what we count each day
    WEEK_LENGTH = 7                                           # days in one "week" on the graphs

    # ======================================================================
    # PM21 START  -  Weekly platform activity
    # ======================================================================
    def weekly_activity(self, end=None, today=None):
        """The 7 days ending on `end` (text 'YYYY-MM-DD'; empty = today), with the totals
        for the week and how much they changed compared with the 7 days before.

        `today` can be passed in so tests do not depend on the real clock.
        """
        today = today or datetime.now(timezone.utc).date()
        end_date = self._parse_end_date(end, today)
        start_date = end_date - timedelta(days=self.WEEK_LENGTH - 1)

        # This week, and the 7 days directly before it (used only for the comparison)
        current = PlatformCharts.daily_activity(start_date, end_date)
        previous = PlatformCharts.daily_activity(
            start_date - timedelta(days=self.WEEK_LENGTH), start_date - timedelta(days=1))

        totals = {metric: sum(current[metric]) for metric in self.METRICS}
        previous_totals = {metric: sum(previous[metric]) for metric in self.METRICS}
        change = {metric: self.percent_change(totals[metric], previous_totals[metric])
                  for metric in self.METRICS}

        return {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'today': today.isoformat(),
            'labels': current['labels'],
            'series': {metric: current[metric] for metric in self.METRICS},
            'totals': totals,
            'previous_totals': previous_totals,
            'change': change,
            'has_activity': any(totals.values()),
        }

    @staticmethod
    def percent_change(current, previous):
        """Percentage change from `previous` to `current`, as a whole number.
        Example: 12 now vs 10 before -> +20.  Returns None when `previous` is 0,
        because you cannot work out a percentage of nothing (the page then shows
        "No previous-week data").
        """
        if previous == 0:
            return None
        return round((current - previous) / previous * 100)

    @staticmethod
    def _parse_end_date(text, today):
        """Turn the text from the date picker into a date, or raise a friendly error."""
        import re
        text = (text or '').strip()
        try:
            if text and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
                raise ValueError('Invalid date format')
            end_date = date.fromisoformat(text) if text else today
        except (TypeError, ValueError):
            raise ValidationError('Please enter a valid date (YYYY-MM-DD).')
        # All four dated charts use this guard before any date-window arithmetic.
        if end_date < date(2000, 1, 1):
            raise ValidationError('Please choose a date from 2000-01-01 onwards.')
        if end_date > today:
            raise ValidationError('The week cannot end in the future.')
        return end_date

    # PM21 END

    # ======================================================================
    # PM23 START  -  Project interest by design category
    # ======================================================================
    def interest_by_category(self):
        """Interest per design category (most viewed first), plus the headline answers the manager
        is looking for and a few sentences that say what the numbers mean."""
        categories = PlatformCharts.interest_by_category()

        # Share of all views that belong to each category, e.g. 40 of 100 views -> 40
        total_views = sum(c['views'] for c in categories)
        for c in categories:
            c['share_of_views'] = round(c['views'] / total_views * 100) if total_views else 0
            # shortlist rate = of everything viewed, how much gets saved (0 when nothing was viewed)
            c['shortlist_rate'] = round(c['favourites'] / c['views'] * 100, 1) if c['views'] else 0.0

        # The entity already sorts by views, so the first row is the most viewed.
        # We only call it "top" if it really has some views.
        top_viewed = categories[0] if categories and categories[0]['views'] else None
        top_shortlisted = max(categories, key=lambda c: c['favourites'], default=None)
        if top_shortlisted and not top_shortlisted['favourites']:
            top_shortlisted = None

        insights = []
        if top_viewed:
            insights.append(f"{top_viewed['name']} is the most viewed category, with {top_viewed['views']} views "
                            f"({top_viewed['share_of_views']}% of all views).")
        # "looked at a lot but rarely saved" needs enough views to mean something
        busy = [c for c in categories if c['views'] >= max(10, total_views * 0.05)]
        if len(busy) >= 2:
            low = min(busy, key=lambda c: c['shortlist_rate'])
            high = max(busy, key=lambda c: c['shortlist_rate'])
            if low is not high:
                insights.append(f"{low['name']} gets plenty of views but only {low['shortlist_rate']}% are shortlisted, "
                                f"while {high['name']} converts best at {high['shortlist_rate']}%.")

        return {
            'categories': categories,
            'has_data': any(c['views'] or c['favourites'] for c in categories),
            'top_viewed': {'name': top_viewed['name'], 'count': top_viewed['views']} if top_viewed else None,
            'top_shortlisted': ({'name': top_shortlisted['name'], 'count': top_shortlisted['favourites']}
                                if top_shortlisted else None),
            'insights': insights,
        }

    # ------------------------------------------------------------------
    # PM23 (extra): how each category's views changed week by week
    # ------------------------------------------------------------------
    TOP_CATEGORIES = 5          # the area chart shows this many categories, the rest become "Other"
    TREND_WEEKS = 8

    def category_trend(self, end=None, today=None):
        """Weekly views per category over the last 8 weeks, plus growth: the last 4 weeks
        compared with the 4 weeks before them."""
        today = today or datetime.now(timezone.utc).date()
        end_date = self._parse_end_date(end, today)
        starts, raw = PlatformCharts.weekly_category_views(end_date, self.TREND_WEEKS)
        half = self.TREND_WEEKS // 2

        entries = []
        for category_id, item in raw.items():
            previous, recent = sum(item['weeks'][:half]), sum(item['weeks'][half:])
            entries.append({'id': category_id, 'name': item['name'], 'weeks': item['weeks'],
                            'total': sum(item['weeks']), 'previous': previous, 'recent': recent,
                            'change': self.percent_change(recent, previous)})
        entries.sort(key=lambda e: (-e['total'], e['name'].lower()))

        top = entries[:self.TOP_CATEGORIES]
        rest = entries[self.TOP_CATEGORIES:]
        series = [{'id': e['id'], 'name': e['name'], 'data': e['weeks']} for e in top]
        if rest:
            series.append({'id': None, 'name': 'Other', 'data': [sum(e['weeks'][w] for e in rest)
                                                                for w in range(self.TREND_WEEKS)]})

        # growth, biggest riser first; categories with no views before cannot show a percentage
        growth = sorted(entries, key=lambda e: (e['change'] is None, -(e['change'] or 0), e['name'].lower()))

        insights = []
        measurable = [e for e in entries if e['change'] is not None and e['previous'] >= 10]
        if measurable:
            riser = max(measurable, key=lambda e: e['change'])
            faller = min(measurable, key=lambda e: e['change'])
            if riser['change'] > 0:
                insights.append(f"{riser['name']} is growing fastest: views are up {riser['change']}% on the previous 4 weeks "
                                f"({riser['previous']} to {riser['recent']}).")
            if faller['change'] < 0:
                insights.append(f"{faller['name']} is cooling off: views are down {abs(faller['change'])}% on the previous 4 weeks "
                                f"({faller['previous']} to {faller['recent']}).")
        return {
            'labels': [d.isoformat() for d in starts],
            'series': series,
            'growth': [{'name': e['name'], 'change': e['change'], 'previous': e['previous'], 'recent': e['recent']}
                       for e in growth],
            'has_data': bool(entries),
            'insights': insights,
        }

    # ------------------------------------------------------------------
    # PM21 (extra): when are projects viewed?
    # ------------------------------------------------------------------
    DAY_NAMES = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
    HEATMAP_DAYS = 28

    @staticmethod
    def _parse_offset(text):
        """Time-zone offset in minutes east of UTC (Singapore = 480). Blank = 0 (UTC)."""
        text = (text or '').strip()
        if not text:
            return 0
        try:
            minutes = int(text)
        except ValueError:
            raise ValidationError('The time zone offset must be a whole number of minutes.')
        if not -720 <= minutes <= 840:                           # UTC-12:00 to UTC+14:00
            raise ValidationError('The time zone offset must be between -720 and 840 minutes.')
        return minutes

    def heatmap(self, end=None, tz=None, today=None):
        """Views per weekday and hour over the 28 days ending on `end`."""
        today = today or datetime.now(timezone.utc).date()
        end_date = self._parse_end_date(end, today)
        offset = self._parse_offset(tz)
        start_date = end_date - timedelta(days=self.HEATMAP_DAYS - 1)
        grid = PlatformCharts.views_by_weekday_hour(start_date, end_date, offset)

        total = sum(sum(row) for row in grid)
        peak = None
        if total:
            day, hour = max(((d, h) for d in range(7) for h in range(24)), key=lambda p: (grid[p[0]][p[1]], -p[0], -p[1]))
            peak = {'day': self.DAY_NAMES[day], 'hour': hour, 'count': grid[day][hour]}
        return {
            'start': start_date.isoformat(), 'end': end_date.isoformat(), 'offset': offset,
            'days': list(self.DAY_NAMES), 'grid': grid, 'total': total,
            'max': max((max(row) for row in grid), default=0), 'peak': peak,
            'weekday_totals': [sum(row) for row in grid],
        }

    # ------------------------------------------------------------------
    # PM21 (extra): one metric over 28 days with moving average, last week, forecast, unusual days
    # ------------------------------------------------------------------
    SHOWN_DAYS = 28
    HISTORY_DAYS = 42            # 14 extra days at the start give the unusual-day check something to compare with
    METRIC_NAMES = {'projects': 'new projects', 'views': 'project views',
                    'favourites': 'new favourites', 'users': 'new users'}

    def trend(self, metric='views', end=None, today=None):
        """The chosen metric day by day, for the 28 days ending on `end`."""
        if metric not in self.METRICS:
            raise ValidationError('Please choose one of: ' + ', '.join(self.METRICS) + '.')
        today = today or datetime.now(timezone.utc).date()
        end_date = self._parse_end_date(end, today)
        start_date = end_date - timedelta(days=self.HISTORY_DAYS - 1)

        series = PlatformCharts.daily_activity(start_date, end_date)
        values = series[metric]
        dates = [start_date + timedelta(days=i) for i in range(self.HISTORY_DAYS)]

        # HARD PART: today is only partly over, so its count is too low. Showing it is fine (it is
        # marked "so far"), but it must NOT be used to judge what is normal or to predict the future.
        live = end_date == today
        complete = values[:-1] if live else values
        complete_dates = dates[:len(complete)]

        anomalies = forecasting.detect_anomalies(complete, complete_dates)
        forecast_data = None
        if live:                                         # a forecast for a week in the past would be confusing
            forecast_data = forecasting.forecast(forecasting.without_anomalies(complete, anomalies), complete_dates)

        shown = self.SHOWN_DAYS
        offset = self.HISTORY_DAYS - shown
        previous_week = [None] * (shown - 7) + values[-14:-7]        # lines up with this week's 7 days
        # week-on-week uses COMPLETE days only (today so far would make this week look worse than it is)
        this_week_total, previous_total = sum(complete[-7:]), sum(complete[-14:-7])

        name = self.METRIC_NAMES[metric]
        insights = []
        change = self.percent_change(this_week_total, previous_total)
        if change is not None:
            how = 'unchanged' if change == 0 else f"{'up' if change > 0 else 'down'} {abs(change)}%"
            insights.append(f"{name.capitalize()} are {how} on the 7 days before "
                            f"({previous_total} to {this_week_total}"
                            f"{', not counting today so far' if live else ''}).")
        for item in anomalies:
            if item['index'] >= offset:
                word = 'high' if item['kind'] == 'spike' else 'low'
                insights.append(f"Unusually {word} {name} on {item['date']}: {item['value']}, "
                                f"where about {round(item['expected'])} was expected.")
        if forecast_data:
            insights.append(f"Expected next 7 days: about {round(sum(forecast_data['values']))} {name} "
                            f"(between {round(sum(forecast_data['lower']))} and {round(sum(forecast_data['upper']))}).")

        return {
            'metric': metric, 'name': name, 'end': end_date.isoformat(), 'today': today.isoformat(),
            'labels': series['labels'][-shown:], 'values': values[-shown:],
            'moving_average': forecasting.moving_average(values)[-shown:],
            'previous_week': previous_week,
            'partial_today': live,
            'forecast': forecast_data,
            'anomalies': [dict(a, index=a['index'] - offset) for a in anomalies if a['index'] >= offset],
            'has_activity': any(values[-shown:]),
            'insights': insights,
        }

    # ------------------------------------------------------------------
    # Ratings overview (links the graphs page with the designer reviews)
    # ------------------------------------------------------------------
    def ratings_overview(self, today=None):
        today = today or datetime.now(timezone.utc).date()
        ratings = PlatformCharts.visible_review_ratings()
        distribution = {stars: 0 for stars in range(5, 0, -1)}
        monthly = {}
        for rating, created in ratings:
            distribution[rating] += 1
            moment = to_datetime(created)
            if moment:
                monthly.setdefault((moment.year, moment.month), []).append(rating)
        year, month, months = today.year, today.month, []
        for _ in range(6):
            values = monthly.get((year, month), [])
            months.append({'label': f'{year}-{month:02d}', 'count': len(values),
                           'average': round(sum(values) / len(values), 2) if values else None})
            month -= 1
            if month == 0:
                year, month = year - 1, 12
        return {'total': len(ratings),
                'average': round(sum(r for r, _ in ratings) / len(ratings), 2) if ratings else None,
                'distribution': distribution, 'monthly': list(reversed(months))}

    # PM23 END

    # ======================================================================
    # DASHBOARD SUMMARY (PM21 + PM23 together) - used by platform.py DashboardView
    # ======================================================================
    def get_dashboard_summary(self, today=None):
        """Small numbers for the dashboard: views and shortlists in the last 7 days
        (PM21) and the most viewed design category (PM23).

        Never raises: if something goes wrong 'available' is False, so the dashboard
        still opens and simply hides the summary."""
        summary = {'weekly_views': 0, 'weekly_saves': 0, 'top_category': None, 'available': False}
        try:
            week = self.weekly_activity(None, today)
            interest = self.interest_by_category()
        except Exception as error:
            from idfinder.db import is_busy_error
            if is_busy_error(error):
                raise
            logging.getLogger(__name__).exception('Dashboard graph summary failed')
            return summary
        summary['weekly_views'] = week['totals']['views']
        summary['weekly_saves'] = week['totals']['favourites']
        summary['top_category'] = interest['top_viewed']['name'] if interest['top_viewed'] else None
        summary['available'] = True
        return summary

    # ======================= DASHBOARD SUMMARY END =======================

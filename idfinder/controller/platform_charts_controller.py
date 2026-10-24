from datetime import datetime, timedelta, timezone

from idfinder.controller.errors import ValidationError
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
        text = (text or '').strip()
        if not text:
            return today
        try:
            end_date = datetime.strptime(text, '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError('Please enter a valid date (YYYY-MM-DD).')
        if end_date > today:
            raise ValidationError('The week cannot end in the future.')
        return end_date

    # PM21 END

    # ======================================================================
    # PM23 START  -  Project interest by design category
    # ======================================================================
    def interest_by_category(self):
        """Interest per design category (most viewed first), plus the headline answers
        the manager is looking for: which category is viewed most and shortlisted most."""
        categories = PlatformCharts.interest_by_category()

        # Share of all views that belong to each category, e.g. 40 of 100 views -> 40
        total_views = sum(c['views'] for c in categories)
        for c in categories:
            c['share_of_views'] = round(c['views'] / total_views * 100) if total_views else 0

        # The entity already sorts by views, so the first row is the most viewed.
        # We only call it "top" if it really has some views.
        top_viewed = categories[0] if categories and categories[0]['views'] else None
        top_shortlisted = max(categories, key=lambda c: c['favourites'], default=None)
        if top_shortlisted and not top_shortlisted['favourites']:
            top_shortlisted = None

        return {
            'categories': categories,
            'has_data': any(c['views'] or c['favourites'] for c in categories),
            'top_viewed': {'name': top_viewed['name'], 'count': top_viewed['views']} if top_viewed else None,
            'top_shortlisted': ({'name': top_shortlisted['name'], 'count': top_shortlisted['favourites']}
                                if top_shortlisted else None),
        }

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
        except Exception:
            return summary
        summary['weekly_views'] = week['totals']['views']
        summary['weekly_saves'] = week['totals']['favourites']
        summary['top_category'] = interest['top_viewed']['name'] if interest['top_viewed'] else None
        summary['available'] = True
        return summary

    # ======================= DASHBOARD SUMMARY END =======================

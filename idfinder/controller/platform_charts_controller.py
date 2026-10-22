from datetime import date, datetime, timedelta, timezone

from idfinder.controller.errors import ValidationError
from idfinder.entities.platform_charts import PlatformCharts

METRICS = ('projects', 'views', 'favourites', 'users')
WEEK_LENGTH = 7


class PlatformChartsController:
    """Control: the rules for the platform manager's graphs (PM21, PM23).

    No Flask objects and no SQL in here: it validates the input, asks the entity
    for the data, and does the calculations (totals, week-on-week change).
    """

    # ------------------------------------------------------------------ PM21
    def weekly_activity(self, end=None, today=None):
        """The 7 days ending on `end` (YYYY-MM-DD text; blank = today), plus the
        totals for the week and the change against the previous 7 days.

        `today` can be passed in so tests do not depend on the real clock.
        """
        today = today or datetime.now(timezone.utc).date()
        end_date = self._parse_end_date(end, today)
        start_date = end_date - timedelta(days=WEEK_LENGTH - 1)

        current = PlatformCharts.daily_activity(start_date, end_date)
        previous = PlatformCharts.daily_activity(
            start_date - timedelta(days=WEEK_LENGTH), start_date - timedelta(days=1))

        totals = {metric: sum(current[metric]) for metric in METRICS}
        previous_totals = {metric: sum(previous[metric]) for metric in METRICS}
        change = {metric: self.percent_change(totals[metric], previous_totals[metric])
                  for metric in METRICS}

        return {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'today': today.isoformat(),
            'labels': current['labels'],
            'series': {metric: current[metric] for metric in METRICS},
            'totals': totals,
            'previous_totals': previous_totals,
            'change': change,
            'has_activity': any(totals.values()),
        }

    @staticmethod
    def percent_change(current, previous):
        """Whole-number % change from `previous` to `current`.
        None when there is nothing to compare with (previous is 0)."""
        if previous == 0:
            return None
        return round((current - previous) / previous * 100)

    @staticmethod
    def _parse_end_date(text, today):
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

    # ------------------------------------------------------------------ PM23
    def interest_by_category(self):
        """Interest per design category, most viewed first."""
        categories = PlatformCharts.interest_by_category()
        return {
            'categories': categories,
            'has_data': any(c['views'] or c['favourites'] for c in categories),
        }

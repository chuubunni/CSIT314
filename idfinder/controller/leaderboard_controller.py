import json
from datetime import datetime, timezone

from idfinder.controller import ranking
from idfinder.controller.errors import NotFoundError, ValidationError
from idfinder.entities.category import Category
from idfinder.entities.designer_stats import DesignerStats
from idfinder.entities.housing import Housing
from idfinder.entities.review import Review

MAX_MIN_REVIEWS = 50


def _utc_now():
    """Naive UTC time, the same clock SQLite's CURRENT_TIMESTAMP uses."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


class LeaderboardController:
    """Control: ranks designers and builds the data for a designer's public profile.
    The maths lives in ranking.py; this class validates input and gathers the numbers."""

    # ------------------------------------------------------------------ the leaderboard
    def leaderboard(self, category_id='', property_type='', min_reviews='0', weights=None, now=None):
        """Ranked designers. Every filter is optional.

        The platform averages used for shrinking come from ALL designers, so a designer's
        score does not change just because a filter hides the others.
        """
        now = now or _utc_now()
        category = self._category(category_id)
        property_type = (property_type or '').strip()
        if property_type and Housing.find_type(property_type) is None:
            raise ValidationError('Please choose a valid housing type.')
        minimum = self._min_reviews(min_reviews)

        everyone = DesignerStats.designers()
        wanted = {d['id'] for d in DesignerStats.designers(category, property_type or None)}
        rows = ranking.build_rows(everyone, DesignerStats.visible_reviews(), DesignerStats.engagement_counts(),
                                  DesignerStats.interest(), DesignerStats.reply_counts(), now)
        rows = [r for r in rows if r['id'] in wanted and r['reviews'] >= minimum]
        weights = ranking.clean_weights(weights)
        return {'rows': ranking.rank(rows, weights), 'weights': weights,
                'components': list(ranking.COMPONENTS), 'labels': ranking.LABELS}

    @staticmethod
    def _category(category_id):
        if not category_id:
            return None
        try:
            category_id = int(category_id)
        except (TypeError, ValueError):
            raise ValidationError('Please choose a valid design category.')
        category = Category.find(category_id)
        if category is None or not category['active']:
            raise ValidationError('Please choose an available design category.')
        return category_id

    @staticmethod
    def _min_reviews(value):
        try:
            number = int(value or 0)
        except (TypeError, ValueError):
            raise ValidationError('The minimum number of reviews must be a whole number.')
        if not 0 <= number <= MAX_MIN_REVIEWS:
            raise ValidationError(f'The minimum number of reviews must be 0 to {MAX_MIN_REVIEWS}.')
        return number

    @staticmethod
    def weights_from_args(args):
        """Reads w_rating=40&w_sentiment=15... from the URL (ranking.clean_weights fixes bad values)."""
        return {name: args.get('w_' + name) for name in ranking.COMPONENTS if args.get('w_' + name) not in (None, '')}

    # ------------------------------------------------------------------ one designer's profile
    def profile(self, designer_id, now=None):
        now = now or _utc_now()
        header = DesignerStats.designer_header(designer_id)
        if header is None:
            raise NotFoundError('Designer not found.')

        board = self.leaderboard(now=now)
        row = next((r for r in board['rows'] if r['id'] == designer_id), None)
        reviews = [dict(r) for r in Review.find_for_designer(designer_id)]
        for review in reviews:
            review['aspects_list'] = json.loads(review['aspects'] or '[]')

        distribution = {stars: 0 for stars in range(5, 0, -1)}
        for review in reviews:
            distribution[review['rating']] += 1

        return {
            'designer': dict(header),
            'stats': row,
            'rank_total': len(board['rows']),
            'distribution': distribution,
            'aspects': self._aspect_summary(reviews),
            'monthly': self._monthly(reviews, now),
            'reviews': reviews,
            'projects': DesignerStats.designer_projects(designer_id),
        }

    @staticmethod
    def _aspect_summary(reviews):
        """{'praised': [(aspect, count)], 'criticised': [(aspect, count)]} - the topics customers
        mention most. A topic needs at least 2 mentions in that direction and must lead the other."""
        tally = {}
        for review in reviews:
            for item in review['aspects_list']:
                entry = tally.setdefault(item['aspect'], {1: 0, -1: 0})
                entry[item['polarity']] += 1
        praised = sorted(((a, v[1]) for a, v in tally.items() if v[1] >= 2 and v[1] > v[-1]),
                         key=lambda x: (-x[1], x[0]))
        criticised = sorted(((a, v[-1]) for a, v in tally.items() if v[-1] >= 2 and v[-1] > v[1]),
                            key=lambda x: (-x[1], x[0]))
        return {'praised': praised, 'criticised': criticised}

    @staticmethod
    def _monthly(reviews, now, months=6):
        """Average rating and number of reviews for each of the last `months` calendar months."""
        buckets = {}
        for review in reviews:
            created = ranking.to_datetime(review['created'])
            if created:
                buckets.setdefault((created.year, created.month), []).append(review['rating'])
        year, month, series = now.year, now.month, []
        for _ in range(months):
            values = buckets.get((year, month), [])
            series.append({'label': f'{year}-{month:02d}', 'count': len(values),
                           'average': round(sum(values) / len(values), 2) if values else None})
            month -= 1
            if month == 0:
                year, month = year - 1, 12
        return list(reversed(series))

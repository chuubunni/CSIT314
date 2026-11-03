"""C18: adapt customer chat filters to the existing designer leaderboard."""
import math

from idfinder.controller import ranking
from idfinder.controller.errors import ValidationError
from idfinder.controller.leaderboard_controller import LeaderboardController, MAX_MIN_REVIEWS
from idfinder.entities.category import Category
from idfinder.entities.housing import Housing


class ChatbotLeaderboard:
    # C18: only expose filters and weights supported by the actual leaderboard.
    FIELDS = {'category', 'property_type', 'min_reviews', 'limit', 'weights'}

    @staticmethod
    def clean(incoming, previous=None):
        if not isinstance(incoming, dict) or set(incoming) - ChatbotLeaderboard.FIELDS:
            raise ValidationError('Use a leaderboard category, housing type, minimum reviews or ranking weights.')
        clean = dict(previous or {})
        for name in ('category', 'property_type'):
            value = incoming.get(name)
            if value is None:
                continue
            if not isinstance(value, str) or len(value) > 100:
                raise ValidationError('Use a valid leaderboard category and housing type.')
            value = ' '.join(value.split())
            if not value:
                clean.pop(name, None)
                clean.pop('category_id' if name == 'category' else name, None)
                continue
            if name == 'category':
                match = next((r for r in Category.find_all_active()
                              if r['name'].casefold() == value.casefold()), None)
                if match is None:
                    raise ValidationError('Choose one available design category for the leaderboard.')
                clean.update(category=match['name'], category_id=match['id'])
            else:
                match = next((r for r in Housing.types() if value.casefold() in
                              (r['code'].casefold(), r['name'].casefold())), None)
                if match is None:
                    raise ValidationError('Choose HDB, Condo or Landed for the leaderboard.')
                clean['property_type'] = match['code']
        for name, default, low, high in [('min_reviews', 0, 0, MAX_MIN_REVIEWS), ('limit', 5, 1, 10)]:
            value = incoming.get(name)
            if value is None:
                value = clean.get(name, default)
            if type(value) is not int or not low <= value <= high:
                raise ValidationError(f'Leaderboard {name.replace("_", " ")} must be a whole number from {low} to {high}.')
            clean[name] = value
        weights = incoming.get('weights')
        if weights is not None:
            if not isinstance(weights, dict) or set(weights) - set(ranking.COMPONENTS):
                raise ValidationError('Choose only the five supported leaderboard ranking weights.')
            # C18: explicit {} resets priorities; null preserves a genuine follow-up.
            result = dict(ranking.DEFAULT_WEIGHTS)
            for name, value in weights.items():
                if value is None:
                    continue
                if type(value) not in (int, float) or not 0 <= value <= 100 or not math.isfinite(value):
                    raise ValidationError('Leaderboard weights must be numbers from 0 to 100.')
                result[name] = value
            if not any(result.values()):
                raise ValidationError('At least one leaderboard weight must be above zero.')
            clean['weights'] = result
        else:
            clean.setdefault('weights', dict(ranking.DEFAULT_WEIGHTS))
        return clean

    @staticmethod
    def search(filters):
        # C18: use the same controller, scoring, tie handling and visible reviews as /leaderboard.
        board = LeaderboardController().leaderboard(
            category_id=filters.get('category_id', ''),
            property_type=filters.get('property_type', ''),
            min_reviews=filters['min_reviews'], weights=filters['weights'])
        rows = board['rows']
        previews = [{
            'id': row['id'], 'name': row['name'], 'company_name': row['company'],
            'rank': row['rank'], 'score': row['score'], 'reviews': row['reviews'],
            'avg_rating': row['avg_rating'] if row['reviews'] else None,
            'completed_jobs': row['completed_jobs'],
        } for row in rows[:filters['limit']]]
        params = {'min_reviews': filters['min_reviews']}
        if filters.get('category_id'):
            params['category_id'] = filters['category_id']
        if filters.get('property_type'):
            params['property_type'] = filters['property_type']
        params.update({'w_' + key: value for key, value in board['weights'].items()})
        scope = [filters.get('category'), filters.get('property_type'),
                 f"at least {filters['min_reviews']} visible review(s)"]
        description = ', '.join(value for value in scope if value)
        reply = (f"I found {len(rows)} ranked designer(s). Showing {len(previews)} from the leaderboard. "
                 if rows else 'No designers match those leaderboard filters. Try a lower minimum review count or another category. ')
        reply += f'Filters: {description}. Scores use the existing weighted leaderboard.'
        if any(row['reviews'] == 0 for row in previews):
            reply += ' Some designers have no visible reviews yet; their scores include the leaderboard’s prior values and other available signals.'
        return {'reply': reply, 'leaderboard': previews, 'total': len(rows),
                'ranking_weights': board['weights'],
                'actions': [{'page': 'leaderboard', 'leaderboard_params': params}]}

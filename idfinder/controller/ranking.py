"""The maths behind designer ratings and the leaderboard. Pure functions: no Flask, no SQL.

WHY NOT JUST "AVERAGE STARS"?
  A designer with one 5-star review would beat one with 80 reviews averaging 4.8. So every
  component is SHRUNK towards the platform average: with few reviews the score stays close to
  "typical", and it only moves away as evidence builds up (a Bayesian average).
  Recent reviews count more (exponential time decay, half-life HALF_LIFE_DAYS).

THE FIVE COMPONENTS (each 0..1, higher is better):
  rating       time-decayed Bayesian mean of the 1-5 stars
  sentiment    time-decayed Bayesian mean of the sentiment of the review text
  interest     shortlists per view of their projects, compared with the platform average
  reliability  accepts requests, finishes accepted jobs, replies to reviews
  experience   completed jobs (saturating: the 20th job adds less than the 2nd)

SCORE = weighted average of the components x 100. The weights are adjustable (the sliders on the
leaderboard page do exactly this, in the browser, using the same numbers).
"""
import math
from datetime import datetime, timedelta

COMPONENTS = ('rating', 'sentiment', 'interest', 'reliability', 'experience')
DEFAULT_WEIGHTS = {'rating': 40, 'sentiment': 15, 'interest': 15, 'reliability': 20, 'experience': 10}
LABELS = {'rating': 'Star rating', 'sentiment': 'Review sentiment', 'interest': 'Customer interest',
          'reliability': 'Reliability', 'experience': 'Experience'}

HALF_LIFE_DAYS = 60          # a review this old counts half as much as one from today
PRIOR_WEIGHT = 5             # "the platform average is worth 5 reviews" (Bayesian prior strength)
NO_DATA_RATING = 3.5         # platform average used before any review exists
INTEREST_PRIOR_VIEWS = 50    # same idea for views -> shortlists


def to_datetime(value):
    """SQLite gives a datetime or 'YYYY-MM-DD HH:MM:SS' text depending on the column."""
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace('T', ' ')[:19])


def decay_weight(age_days, half_life=HALF_LIFE_DAYS):
    """1.0 for today, 0.5 after one half-life, 0.25 after two ..."""
    return 0.5 ** (max(age_days, 0) / half_life)


def bayesian_mean(weighted_values, prior_mean, prior_weight=PRIOR_WEIGHT):
    """(prior_weight*prior_mean + sum(w*v)) / (prior_weight + sum(w)). Empty input -> the prior."""
    total_w = sum(w for _, w in weighted_values)
    total = sum(v * w for v, w in weighted_values)
    return (prior_weight * prior_mean + total) / (prior_weight + total_w)


def wilson_lower_bound(positive, total, z=1.96):
    """Lower end of the 95% confidence interval for the share of positive (4-5 star) reviews.
    "We are 95% sure at least this share of customers are happy." 0 when there are no reviews."""
    if total <= 0:
        return 0.0
    p = positive / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return max(0.0, (centre - margin) / denominator)


def rating_trend(points, now, window_days=120):
    """'rising' / 'falling' / 'steady' / None from the slope of rating over time (least squares).
    `points` = [(datetime, rating)]. Needs at least 4 reviews spread over 14+ days."""
    recent = [(to_datetime(t), r) for t, r in points if to_datetime(t) and (now - to_datetime(t)).days <= window_days]
    if len(recent) < 4:
        return None
    xs = [(t - now).total_seconds() / 86400 for t, _ in recent]        # days relative to today (<= 0)
    if max(xs) - min(xs) < 14:
        return None
    ys = [r for _, r in recent]
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    slope_per_month = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator * 30
    if slope_per_month > 0.25:
        return 'rising'
    if slope_per_month < -0.25:
        return 'falling'
    return 'steady'


def build_rows(designers, reviews, engagements, interest, replies, now):
    """One dict per designer with raw facts and the five components.

    designers   [{'id','name','company'}]       reviews  [{'designer_id','rating','sentiment','created'}]
    engagements {designer_id: {'requested','accepted','completed','declined'}}
    interest    {designer_id: {'projects','views','favourites'}}
    replies     {designer_id: {'reviews','replied'}}
    The platform averages (the priors) come from ALL the reviews and views passed in.
    """
    by_designer = {}
    for review in reviews:
        by_designer.setdefault(review['designer_id'], []).append(review)

    all_ratings = [r['rating'] for r in reviews]
    platform_rating = sum(all_ratings) / len(all_ratings) if all_ratings else NO_DATA_RATING
    all_sentiments = [r['sentiment'] for r in reviews if r['sentiment'] is not None]
    platform_sentiment = sum(all_sentiments) / len(all_sentiments) if all_sentiments else 0.0
    total_views = sum(i['views'] for i in interest.values())
    total_favs = sum(i['favourites'] for i in interest.values())
    platform_conversion = total_favs / total_views if total_views else 0.1

    rows = []
    for d in designers:
        mine = by_designer.get(d['id'], [])
        rating_points, sentiment_points = [], []
        for r in mine:
            created = to_datetime(r['created']) or now
            w = decay_weight((now - created).total_seconds() / 86400)
            rating_points.append((r['rating'], w))
            if r['sentiment'] is not None:
                sentiment_points.append((r['sentiment'], w))

        bayes_rating = bayesian_mean(rating_points, platform_rating)           # on the 1-5 scale
        bayes_sentiment = bayesian_mean(sentiment_points, platform_sentiment)  # on the -1..1 scale

        stats = interest.get(d['id'], {'projects': 0, 'views': 0, 'favourites': 0})
        conversion = ((stats['favourites'] + INTEREST_PRIOR_VIEWS * platform_conversion)
                      / (stats['views'] + INTEREST_PRIOR_VIEWS))
        jobs = engagements.get(d['id'], {'requested': 0, 'accepted': 0, 'completed': 0, 'declined': 0})
        rep = replies.get(d['id'], {'reviews': 0, 'replied': 0})
        completion = (jobs['completed'] + 2 * 0.8) / (jobs['accepted'] + 2)        # finishes what it accepts
        acceptance = (jobs['accepted'] + 2 * 0.7) / (jobs['requested'] + 2)        # says yes to customers
        reply_rate = (rep['replied'] + 0.5) / (rep['reviews'] + 1)

        n = len(mine)
        positive = sum(1 for r in mine if r['rating'] >= 4)
        rows.append({
            'id': d['id'], 'name': d['name'], 'company': d.get('company'),
            'reviews': n,
            'avg_rating': round(sum(r['rating'] for r in mine) / n, 2) if n else None,
            'bayes_rating': round(bayes_rating, 2),
            'positive_share': round(positive / n * 100) if n else None,
            'wilson': round(wilson_lower_bound(positive, n) * 100),
            'trend': rating_trend([(r['created'], r['rating']) for r in mine], now),
            'projects': stats['projects'], 'views': stats['views'], 'favourites': stats['favourites'],
            'conversion': round(stats['favourites'] / stats['views'] * 100, 1) if stats['views'] else None,
            'completed_jobs': jobs['completed'],
            'components': {
                'rating': round((bayes_rating - 1) / 4, 4),
                'sentiment': round((bayes_sentiment + 1) / 2, 4),
                # C18: no favourites anywhere means no comparative interest evidence yet.
                'interest': round(conversion / (conversion + platform_conversion), 4)
                            if conversion + platform_conversion else 0.5,
                'reliability': round(0.4 * completion + 0.4 * acceptance + 0.2 * reply_rate, 4),
                'experience': round(jobs['completed'] / (jobs['completed'] + 5), 4),
            },
        })
    return rows


def clean_weights(weights=None):
    """Weights from 0 to 100 for every component (missing/invalid -> the default).
    All zero would divide by zero, so that falls back to the defaults too."""
    result = {}
    for name in COMPONENTS:
        try:
            value = float((weights or {}).get(name, DEFAULT_WEIGHTS[name]))
        except (TypeError, ValueError, OverflowError):
            value = DEFAULT_WEIGHTS[name]
        # C18: match the slider range and prevent overflowing the weighted total.
        result[name] = value if 0 <= value <= 100 and math.isfinite(value) else DEFAULT_WEIGHTS[name]
    if not any(result.values()):
        return dict(DEFAULT_WEIGHTS)
    return result


def score(components, weights):
    """Weighted average of the components, 0..100."""
    weights = clean_weights(weights)
    total = sum(weights.values())
    return round(sum(components[c] * weights[c] for c in COMPONENTS) / total * 100, 1)


def rank(rows, weights=None):
    """Adds 'score' and 'rank' and sorts best first. Ties keep the same rank and are broken by
    more reviews, then name, so the order never jumps around between page loads."""
    weights = clean_weights(weights)
    for row in rows:
        row['score'] = score(row['components'], weights)
    rows.sort(key=lambda r: (-r['score'], -r['reviews'], r['name'].lower(), r['id']))
    previous_score, previous_rank = None, 0
    for position, row in enumerate(rows, start=1):
        row['rank'] = previous_rank if row['score'] == previous_score else position
        previous_score, previous_rank = row['score'], row['rank']
    return rows

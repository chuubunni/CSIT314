"""ranking.py: the maths behind the leaderboard (pure functions, no database)."""
import math
from datetime import datetime, timedelta

import pytest

from idfinder.controller import ranking

NOW = datetime(2026, 10, 30, 12, 0, 0)


def test_decay_halves_every_half_life():
    assert ranking.decay_weight(0) == 1
    assert ranking.decay_weight(60) == pytest.approx(0.5)
    assert ranking.decay_weight(120) == pytest.approx(0.25)
    assert ranking.decay_weight(-5) == 1                      # a clock slightly ahead must not give > 1


def test_bayesian_mean_with_no_data_is_the_prior():
    assert ranking.bayesian_mean([], 3.5) == 3.5


def test_bayesian_mean_moves_towards_the_data_as_evidence_grows():
    one = ranking.bayesian_mean([(5, 1)], 3.0)                # one 5-star review barely moves it
    many = ranking.bayesian_mean([(5, 1)] * 50, 3.0)          # fifty of them move it a lot
    assert 3.0 < one < 3.5 < many < 5.0
    assert many > 4.7


def test_wilson_bound_punishes_small_samples():
    assert ranking.wilson_lower_bound(0, 0) == 0.0
    assert ranking.wilson_lower_bound(2, 2) < ranking.wilson_lower_bound(80, 100)   # 100% of 2 < 80% of 100
    assert 0 <= ranking.wilson_lower_bound(10, 10) <= 1


def test_clean_weights_fixes_bad_input():
    assert ranking.clean_weights(None) == ranking.DEFAULT_WEIGHTS
    assert ranking.clean_weights({'rating': 'abc'})['rating'] == ranking.DEFAULT_WEIGHTS['rating']
    assert ranking.clean_weights({'rating': -5})['rating'] == ranking.DEFAULT_WEIGHTS['rating']
    assert ranking.clean_weights({'rating': float('nan')})['rating'] == ranking.DEFAULT_WEIGHTS['rating']
    zero = {c: 0 for c in ranking.COMPONENTS}
    assert ranking.clean_weights(zero) == ranking.DEFAULT_WEIGHTS      # all zero would divide by zero


def _designer(i, name=None):
    return {'id': i, 'name': name or f'D{i}', 'company': None}


def _rows(reviews, designers=(1, 2), engagements=None, interest=None, replies=None):
    return ranking.build_rows([_designer(i) for i in designers], reviews, engagements or {},
                              interest or {}, replies or {}, NOW)


def _review(designer, rating, days_ago=1, sentiment=None):
    return {'designer_id': designer, 'rating': rating, 'sentiment': sentiment,
            'created': NOW - timedelta(days=days_ago)}


def test_one_perfect_review_does_not_beat_a_long_track_record():
    # designer 3 pulls the platform average down to about 3.9, as on a real platform
    reviews = ([_review(1, 5)]
               + [_review(2, 5 if i % 5 else 4) for i in range(40)]      # designer 2: about 4.8 over 40 reviews
               + [_review(3, 3) for _ in range(40)])
    rows = {r['id']: r for r in ranking.rank(_rows(reviews, designers=(1, 2, 3)))}
    assert rows[2]['components']['rating'] > rows[1]['components']['rating']
    assert rows[2]['rank'] < rows[1]['rank']


def test_recent_reviews_count_more_than_old_ones():
    old_bad = [_review(1, 1, days_ago=400)] * 5 + [_review(1, 5, days_ago=2)] * 5
    old_good = [_review(2, 5, days_ago=400)] * 5 + [_review(2, 1, days_ago=2)] * 5
    rows = {r['id']: r for r in _rows(old_bad + old_good)}
    assert rows[1]['components']['rating'] > rows[2]['components']['rating']


def test_designer_without_reviews_gets_the_platform_average_not_zero():
    rows = {r['id']: r for r in _rows([_review(2, 4)] * 6)}
    assert rows[1]['reviews'] == 0 and rows[1]['avg_rating'] is None
    assert rows[1]['components']['rating'] == pytest.approx(rows[1]['components']['rating'])
    assert 0.5 < rows[1]['components']['rating'] < 0.8        # neither 0 nor a perfect score


def test_components_are_always_between_0_and_1():
    reviews = [_review(1, 1, sentiment=-1.0)] * 20 + [_review(2, 5, sentiment=1.0)] * 20
    interest = {1: {'projects': 3, 'views': 0, 'favourites': 0}, 2: {'projects': 3, 'views': 10 ** 6, 'favourites': 10 ** 6}}
    jobs = {1: {'requested': 0, 'accepted': 0, 'completed': 0, 'declined': 0},
            2: {'requested': 500, 'accepted': 500, 'completed': 500, 'declined': 0}}
    for row in _rows(reviews, interest=interest, engagements=jobs):
        for name, value in row['components'].items():
            assert 0 <= value <= 1, (name, value)


def test_changing_the_weights_changes_the_order():
    reviews = [_review(1, 5)] * 20 + [_review(2, 3)] * 20
    interest = {1: {'projects': 1, 'views': 1000, 'favourites': 10}, 2: {'projects': 1, 'views': 1000, 'favourites': 600}}
    by_rating = ranking.rank(_rows(reviews, interest=interest), {'rating': 100, 'sentiment': 0, 'interest': 0, 'reliability': 0, 'experience': 0})
    by_interest = ranking.rank(_rows(reviews, interest=interest), {'rating': 0, 'sentiment': 0, 'interest': 100, 'reliability': 0, 'experience': 0})
    assert [r['id'] for r in by_rating] == [1, 2]
    assert [r['id'] for r in by_interest] == [2, 1]


def test_ties_share_a_rank_and_order_is_stable():
    rows = ranking.rank(_rows([], designers=(3, 1, 2)))        # nobody has data: identical scores
    assert [r['rank'] for r in rows] == [1, 1, 1]
    assert [r['name'] for r in rows] == ['D1', 'D2', 'D3']     # name breaks the tie, so the page never shuffles


def test_score_is_a_weighted_average_out_of_100():
    components = {c: 0.5 for c in ranking.COMPONENTS}
    assert ranking.score(components, ranking.DEFAULT_WEIGHTS) == 50.0
    components['rating'] = 1.0
    only_rating = {c: 0 for c in ranking.COMPONENTS}; only_rating['rating'] = 1
    assert ranking.score(components, only_rating) == 100.0


def test_trend_needs_enough_spread_data_then_detects_direction():
    few = [(NOW - timedelta(days=i), 5) for i in range(3)]
    assert ranking.rating_trend(few, NOW) is None
    rising = [(NOW - timedelta(days=d), r) for d, r in [(90, 2), (70, 2), (50, 3), (30, 4), (10, 5), (2, 5)]]
    falling = [(NOW - timedelta(days=d), r) for d, r in [(90, 5), (70, 5), (50, 4), (30, 3), (10, 2), (2, 2)]]
    steady = [(NOW - timedelta(days=d), 4) for d in (90, 70, 50, 30, 10, 2)]
    assert ranking.rating_trend(rising, NOW) == 'rising'
    assert ranking.rating_trend(falling, NOW) == 'falling'
    assert ranking.rating_trend(steady, NOW) == 'steady'
    assert ranking.rating_trend([(NOW - timedelta(days=2), 5)] * 6, NOW) is None     # all on one day: no slope


def test_to_datetime_accepts_text_and_datetime():
    assert ranking.to_datetime('2026-10-30 12:00:00') == NOW
    assert ranking.to_datetime(NOW) == NOW
    assert ranking.to_datetime(None) is None

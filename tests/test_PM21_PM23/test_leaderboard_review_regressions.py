"""Regression checks for leaderboard edge cases, moderation and stale job requests."""
from datetime import datetime
import json
import math
from unittest.mock import patch

import pytest

from idfinder.controller import ranking
from idfinder.controller.engagement_controller import EngagementController
from idfinder.controller.errors import ValidationError
from idfinder.controller.leaderboard_controller import LeaderboardController
from idfinder.controller.review_controller import ReviewController
from idfinder.entities.engagement import Engagement
from idfinder.entities.review import Review


def test_views_without_favourites_have_neutral_interest(make):
    designer = make.user('designer')
    project = make.project(designer)
    make.view(project, '2026-11-01 09:00:00')
    row = LeaderboardController().leaderboard()['rows'][0]
    assert row['components']['interest'] == 0.5
    assert math.isfinite(row['score'])


@pytest.mark.parametrize('value', [1e308, float('inf'), float('nan'), 101, -1, 10**400])
def test_invalid_weights_are_bounded(value):
    weights = ranking.clean_weights({c: value for c in ranking.COMPONENTS})
    assert weights == ranking.DEFAULT_WEIGHTS
    assert ranking.score({c: 0.8 for c in ranking.COMPONENTS}, weights) == 80


def test_public_json_with_extreme_weights_is_strict_json(make, app):
    make.user('designer')
    query = {f'w_{c}': '1e308' for c in ranking.COMPONENTS}
    response = app.test_client().get('/leaderboard.json', query_string=query)
    assert response.status_code == 200
    def reject_constant(value):
        raise AssertionError(f'Invalid JSON constant: {value}')
    data = json.loads(response.get_data(as_text=True), parse_constant=reject_constant)
    assert data


def test_zero_weights_restore_default_score():
    components = dict(zip(ranking.COMPONENTS, [0.9, 0.6, 0.5, 0.7, 0.2]))
    assert ranking.score(components, {c: 0 for c in ranking.COMPONENTS}) == ranking.score(
        components, ranking.DEFAULT_WEIGHTS)


def test_hidden_review_cannot_be_deleted_to_repost(make):
    customer, designer = make.user(), make.user('designer')
    job = make.engagement(customer, designer)
    review = make.review(job, status='hidden')
    ctrl = ReviewController()
    with pytest.raises(ValidationError, match='moderation'):
        ctrl.delete(customer, review)
    assert Review.find(review)['status'] == 'hidden'
    with pytest.raises(ValidationError, match='already reviewed'):
        ctrl.submit(customer, job, 5, 'Replacement')


def test_moderation_during_deletion_is_not_lost(make):
    customer, designer = make.user(), make.user('designer')
    review = make.review(make.engagement(customer, designer))
    ctrl = ReviewController()
    old = dict(Review.find(review))
    Review.set_status(review, 'hidden', 'Manager decision')
    with patch.object(ctrl, '_own_review', return_value=old):
        with pytest.raises(ValidationError, match='changed'):
            ctrl.delete(customer, review)
    assert Review.find(review)['hidden_reason'] == 'Manager decision'


def test_visible_review_deletion_still_works(make):
    customer, designer = make.user(), make.user('designer')
    review = make.review(make.engagement(customer, designer))
    ReviewController().delete(customer, review)
    assert Review.find(review) is None


def test_stale_cancellation_preserves_completed_reviewed_job(make):
    customer, designer = make.user(), make.user('designer')
    job = make.engagement(customer, designer, status='ongoing')
    ctrl = EngagementController()
    old = dict(Engagement.find(job))
    ctrl.complete(designer, job)
    review = make.review(job)
    completed_at = Engagement.find(job)['completed_at']
    with patch.object(ctrl, '_load', return_value=old):
        with pytest.raises(ValidationError, match='changed'):
            ctrl.cancel(customer, job)
    assert Engagement.find(job)['status'] == 'completed'
    assert Engagement.find(job)['completed_at'] == completed_at
    assert Review.find(review) is not None


def test_empty_profile_explains_missing_data(make, app):
    designer = make.user('designer')
    response = app.test_client().get(f'/designers/{designer}')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'No visible customer reviews yet' in html
    assert 'No completed jobs recorded yet' in html
    assert 'No visible reviews in the last six months' in html


def test_profile_has_real_experience_and_review_months(make, app):
    customer, designer = make.user(), make.user('designer')
    job = make.engagement(customer, designer)
    now = datetime.now()
    make.review(job, created=now.strftime('%Y-%m-%d %H:%M:%S'))
    data = LeaderboardController().profile(designer, now=now)
    assert data['stats']['components']['experience'] > 0
    assert data['distribution'][5] == 1
    assert data['monthly'][-1]['count'] == 1
    html = app.test_client().get(f'/designers/{designer}').get_data(as_text=True)
    assert 'one month only' in html
    assert 'No completed jobs recorded yet' not in html

"""The pages and forms for ratings: who may open what, and what happens when they submit."""
import json

import pytest

from idfinder.db import get_db
from idfinder.entities.engagement import Engagement
from idfinder.entities.review import Review


def login(client, make, kind, **kw):
    user = make.user(kind, **kw)
    client.login(make.email(user))
    return user


# ---------------------------------------------------------------- public pages
def test_profile_and_leaderboard_are_public(client, make):
    d = make.user('designer', name='Dana Designer')
    make.reviewed_job(d, 5, 'Very responsive and great quality.', 0.8)
    page = client.get(f'/designers/{d}')
    assert page.status_code == 200 and b'Dana Designer' in page.data and b'Very responsive' in page.data
    assert client.get('/leaderboard').status_code == 200
    assert client.get('/designers/9999').status_code == 404
    assert client.get(f'/designers/{make.user("customer")}').status_code == 404      # customers have no profile page


def test_customer_names_are_shortened_on_the_public_profile(client, make):
    d = make.user('designer')
    c = make.user('customer', name='Aisha Rahman')
    make.review(make.engagement(c, d), 5, 'Lovely')
    html = client.get(f'/designers/{d}').get_data(as_text=True)
    assert 'Aisha R.' in html and 'Rahman' not in html


def test_review_text_is_escaped(client, make):
    d = make.user('designer')
    make.reviewed_job(d, 5, '<script>alert("x")</script>')
    html = client.get(f'/designers/{d}').get_data(as_text=True)
    assert '<script>alert' not in html and '&lt;script&gt;' in html


def test_leaderboard_json_and_bad_filters(client, make):
    d = make.user('designer'); make.reviewed_job(d, 5)
    data = client.get('/leaderboard.json').get_json()
    assert data['rows'][0]['id'] == d and set(data['components']) == {'rating', 'sentiment', 'interest', 'reliability', 'experience'}
    assert client.get('/leaderboard.json?category_id=abc').status_code == 400
    page = client.get('/leaderboard?min_reviews=abc')
    assert page.status_code == 400 and b'whole number' in page.data
    # weights in the URL change the order
    a, b = make.user('designer'), make.user('designer')
    for _ in range(6):
        make.reviewed_job(a, 5); make.reviewed_job(b, 2)
    rows = client.get('/leaderboard.json?w_rating=100&w_sentiment=0&w_interest=0&w_reliability=0&w_experience=0').get_json()['rows']
    assert rows[0]['id'] == a


def test_leaderboard_shows_the_slider_data(client, make):
    make.user('designer')
    html = client.get('/leaderboard').get_data(as_text=True)
    assert 'id="leaderboard-data"' in html and 'data-weight="rating"' in html and 'leaderboard.js' in html


# ---------------------------------------------------------------- access control
@pytest.mark.parametrize('url', ['/my-jobs', '/client-requests', '/platform/reviews/'])
def test_private_pages_redirect_visitors_to_login(client, url):
    response = client.get(url)
    assert response.status_code == 302 and '/auth/login' in response.headers['Location']


def test_pages_are_limited_to_their_own_role(client, make):
    login(client, make, 'customer')
    assert client.get('/my-jobs').status_code == 200
    assert client.get('/client-requests').status_code == 403 and client.get('/platform/reviews/').status_code == 403
    client.get('/auth/logout')
    login(client, make, 'designer')
    assert client.get('/client-requests').status_code == 200
    assert client.get('/my-jobs').status_code == 403 and client.get('/platform/reviews/').status_code == 403
    client.get('/auth/logout')
    login(client, make, 'manager')
    assert client.get('/platform/reviews/').status_code == 200 and client.get('/my-jobs').status_code == 403


def test_post_forms_need_the_form_token(client, make):
    c, d = make.user('customer'), make.user('designer')
    client.login(make.email(c))
    assert client.post(f'/designers/{d}/hire', {'title': 'Kitchen'}, token=False).status_code == 400
    assert client.post(f'/designers/{d}/hire', {'title': 'Kitchen'}).status_code == 302


def test_designers_and_managers_cannot_hire(client, make):
    d = make.user('designer')
    login(client, make, 'designer')
    assert client.post(f'/designers/{d}/hire', {'title': 'Kitchen'}).status_code == 403


# ---------------------------------------------------------------- the whole journey through the pages
def test_hire_accept_complete_review_reply_journey(client, make):
    customer, designer = make.user('customer'), make.user('designer', name='Dana Designer')
    client.login(make.email(customer))

    client.post(f'/designers/{designer}/hire', {'title': 'Living room refresh', 'message': 'Scandinavian please'})
    job = Engagement.find_for_customer(customer)[0]
    assert job['status'] == 'requested'
    assert b'Living room refresh' in client.get('/my-jobs').data
    assert client.get(f'/jobs/{job["id"]}/review', follow_redirects=False).status_code == 302   # too early

    client.get('/auth/logout'); client.login(make.email(designer))
    assert b'Scandinavian please' in client.get('/client-requests').data
    client.post(f'/jobs/{job["id"]}/accept')
    client.post(f'/jobs/{job["id"]}/complete')
    assert Engagement.find(job['id'])['status'] == 'completed'

    client.get('/auth/logout'); client.login(make.email(customer))
    assert b'Write a review' in client.get(f'/designers/{designer}').data
    form = client.get(f'/jobs/{job["id"]}/review')
    assert form.status_code == 200 and b'name="rating"' in form.data
    response = client.post(f'/jobs/{job["id"]}/review', {'rating': '5', 'comment': 'Responsive and delivered on time.'})
    assert response.status_code == 302 and f'/designers/{designer}' in response.headers['Location']
    review = Review.find_by_engagement(job['id'])
    assert review['rating'] == 5 and review['designer_id'] == designer

    client.post(f'/jobs/{job["id"]}/review', {'rating': '1', 'comment': 'Changed my mind'})     # second POST edits
    assert Review.find(review['id'])['rating'] == 1 and Review.find(review['id'])['edit_count'] == 1

    client.get('/auth/logout'); client.login(make.email(designer))
    client.post(f'/reviews/{review["id"]}/reply', {'reply': 'Thanks for the feedback'})
    assert b'Thanks for the feedback' in client.get(f'/designers/{designer}').data


def test_invalid_rating_keeps_the_form_and_shows_the_error(client, make):
    c, d = make.user('customer'), make.user('designer')
    job = make.engagement(c, d)
    client.login(make.email(c))
    page = client.post(f'/jobs/{job}/review', {'rating': '9', 'comment': 'keep this text'})
    assert page.status_code == 200 and b'1 to 5' in page.data and b'keep this text' in page.data
    assert Review.find_by_engagement(job) is None


def test_other_customers_cannot_touch_my_job_or_review(client, make):
    c, d = make.user('customer'), make.user('designer')
    job = make.engagement(c, d)
    review = make.review(job, 4, 'Mine')
    login(client, make, 'customer')                                  # a different customer
    assert client.get(f'/jobs/{job}/review').status_code == 403
    assert client.post(f'/jobs/{job}/review', {'rating': '1'}).status_code == 403
    assert client.post(f'/reviews/{review}/delete').status_code == 403
    assert client.post(f'/jobs/{job}/cancel').status_code == 403
    assert Review.find(review)['rating'] == 4


def test_other_designers_cannot_touch_my_jobs_or_reviews(client, make):
    c, d = make.user('customer'), make.user('designer')
    job = make.engagement(c, d, 'requested')
    review = make.review(make.engagement(c, d), 5, 'Great')
    login(client, make, 'designer')
    assert client.post(f'/jobs/{job}/accept').status_code == 403
    assert client.post(f'/reviews/{review}/reply', {'reply': 'hi'}).status_code == 403
    assert client.post(f'/reviews/{review}/report', {'reason': 'x'}).status_code == 403
    assert Engagement.find(job)['status'] == 'requested'


def test_next_parameter_cannot_redirect_off_site(client, make):
    d = make.user('designer')
    review = make.reviewed_job(d)
    client.login(make.email(d))
    for target in ('https://evil.test/', '//evil.test/'):
        response = client.post(f'/reviews/{review}/reply', {'reply': 'ok', 'next': target})
        assert 'evil.test' not in response.headers['Location']


def test_cancel_and_delete_from_my_jobs(client, make):
    c, d = make.user('customer'), make.user('designer')
    open_job = make.engagement(c, d, 'requested')
    review = make.review(make.engagement(c, d), 5, 'Great')
    client.login(make.email(c))
    client.post(f'/jobs/{open_job}/cancel')
    client.post(f'/reviews/{review}/delete')
    assert Engagement.find(open_job)['status'] == 'cancelled' and Review.find(review) is None


# ---------------------------------------------------------------- moderation
def test_manager_moderation_hides_and_restores(client, make):
    d = make.user('designer')
    review = make.reviewed_job(d, 1, 'Awful', -0.9, reported_reason='Not a real customer')
    login(client, make, 'manager')
    page = client.get('/platform/reviews/')
    assert b'Not a real customer' in page.data and b'Awful' in page.data
    assert client.post(f'/platform/reviews/{review}/hide', {'reason': ''}).status_code == 302
    assert Review.find(review)['status'] == 'visible'                # empty reason refused
    client.post(f'/platform/reviews/{review}/hide', {'reason': 'Abusive'})
    assert Review.find(review)['status'] == 'hidden'
    assert b'Awful' not in client.get(f'/designers/{d}').data        # no longer public
    client.post(f'/platform/reviews/{review}/restore')
    assert Review.find(review)['status'] == 'visible'
    client.post(f'/platform/reviews/{review}/dismiss')
    assert Review.find(review)['reported_reason'] is None
    assert client.get('/platform/reviews/?show=bogus').status_code == 400
    assert client.post('/platform/reviews/9999/restore').status_code == 404


def test_moderation_actions_need_manager_and_token(client, make):
    d = make.user('designer')
    review = make.reviewed_job(d)
    login(client, make, 'customer')
    assert client.post(f'/platform/reviews/{review}/hide', {'reason': 'x'}).status_code == 403
    client.get('/auth/logout')
    login(client, make, 'manager')
    assert client.post(f'/platform/reviews/{review}/hide', {'reason': 'x'}, token=False).status_code == 400
    assert Review.find(review)['status'] == 'visible'


# ---------------------------------------------------------------- links added to existing pages
def test_navigation_shows_role_specific_links(client, make):
    assert b'Leaderboard' in client.get('/').data
    login(client, make, 'customer')
    assert b'My Jobs' in client.get('/').data
    client.get('/auth/logout'); login(client, make, 'designer')
    assert b'Client Requests' in client.get('/').data
    client.get('/auth/logout'); login(client, make, 'manager')
    assert b'Review Moderation' in client.get('/').data


def test_designer_search_cards_link_to_profiles(client, make):
    d = make.user('designer', name='Dana Designer')
    login(client, make, 'customer')
    assert f'/designers/{d}'.encode() in client.get('/designers').data

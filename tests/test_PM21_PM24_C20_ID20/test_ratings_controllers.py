"""Engagement, review, moderation and leaderboard controllers + the review tables (needs the database)."""
import json
import sqlite3
from datetime import datetime

import pytest

from idfinder import create_app
from idfinder.controller.engagement_controller import EngagementController
from idfinder.controller.errors import NotFoundError, PermissionDenied, ValidationError
from idfinder.controller.leaderboard_controller import LeaderboardController
from idfinder.controller.review_controller import ReviewController
from idfinder.db import get_db
from idfinder.entities.review import Review

jobs, reviews, board = EngagementController(), ReviewController(), LeaderboardController()
NOW = datetime(2026, 10, 30, 12, 0, 0)


# ---------------------------------------------------------------- hiring a designer
def test_request_creates_a_requested_job(make):
    c, d = make.user('customer'), make.user('designer')
    job_id = jobs.request(c, d, '  Full   renovation ', 'Budget 40k')
    job = jobs.for_customer(c)[0]
    assert job['id'] == job_id and job['status'] == 'requested' and job['title'] == 'Full renovation'


@pytest.mark.parametrize('title', ['', '  ', 'ab', 'x' * 101, None])
def test_request_rejects_bad_titles(make, title):
    with pytest.raises(ValidationError):
        jobs.request(make.user('customer'), make.user('designer'), title)


def test_request_rejects_long_message_and_non_designers(make):
    c, d = make.user('customer'), make.user('designer')
    with pytest.raises(ValidationError):
        jobs.request(c, d, 'Kitchen', 'x' * 1001)
    with pytest.raises(NotFoundError):
        jobs.request(c, make.user('customer'), 'Kitchen')          # target is a customer
    with pytest.raises(NotFoundError):
        jobs.request(c, 9999, 'Kitchen')


def test_inspiring_project_must_belong_to_that_designer(make):
    c, d, other = make.user('customer'), make.user('designer'), make.user('designer')
    mine, theirs = make.project(d), make.project(other)
    assert jobs.request(c, d, 'Like this one', idp_id=str(mine))
    with pytest.raises(ValidationError):
        jobs.request(c, d, 'Like that one', idp_id=theirs)
    with pytest.raises(ValidationError):
        jobs.request(c, d, 'Like that one', idp_id='abc')


def test_a_customer_cannot_pile_up_unfinished_jobs(make):
    c, d = make.user('customer'), make.user('designer')
    for n in range(3):
        jobs.request(c, d, f'Job {n}')
    with pytest.raises(ValidationError):
        jobs.request(c, d, 'One too many')


def test_job_life_cycle_and_forbidden_moves(make):
    c, d = make.user('customer'), make.user('designer')
    job = jobs.request(c, d, 'Kitchen')
    with pytest.raises(ValidationError):
        jobs.complete(d, job)                                       # cannot finish what was never accepted
    jobs.accept(d, job)
    with pytest.raises(ValidationError):
        jobs.accept(d, job)                                         # cannot accept twice
    with pytest.raises(ValidationError):
        jobs.decline(d, job)                                        # too late to decline
    jobs.complete(d, job)
    status = lambda: jobs.for_customer(c)[0]
    assert status()['status'] == 'completed' and status()['completed_at'] is not None
    with pytest.raises(ValidationError):
        jobs.cancel(c, job)                                         # a finished job cannot be cancelled


def test_decline_and_cancel(make):
    c, d = make.user('customer'), make.user('designer')
    first, second = jobs.request(c, d, 'One'), jobs.request(c, d, 'Two')
    jobs.decline(d, first)
    jobs.cancel(c, second)
    assert {j['status'] for j in jobs.for_customer(c)} == {'declined', 'cancelled'}


def test_only_the_right_people_may_change_a_job(make):
    c, d = make.user('customer'), make.user('designer')
    job = jobs.request(c, d, 'Kitchen')
    for action, who in ((jobs.accept, make.user('designer')), (jobs.decline, make.user('designer')),
                        (jobs.cancel, make.user('customer'))):
        with pytest.raises(PermissionDenied):
            action(who, job)
    with pytest.raises(NotFoundError):
        jobs.accept(d, 9999)


# ---------------------------------------------------------------- writing a review
def completed_job(make):
    c, d = make.user('customer'), make.user('designer')
    return c, d, make.engagement(c, d, 'completed')


def test_review_needs_a_completed_job(make):
    c, d = make.user('customer'), make.user('designer')
    for status in ('requested', 'ongoing', 'declined', 'cancelled'):
        job = make.engagement(c, d, status)
        with pytest.raises(ValidationError):
            reviews.submit(c, job, 5, 'Nice')


def test_database_itself_refuses_a_review_without_a_completed_job(make):
    c, d = make.user('customer'), make.user('designer')
    job = make.engagement(c, d, 'ongoing')
    with pytest.raises(sqlite3.DatabaseError):
        make.review(job)                                            # bypasses the controller on purpose
    other = make.user('customer')
    done = make.engagement(c, d, 'completed')
    with pytest.raises(sqlite3.DatabaseError):                      # right job, wrong customer
        get_db().execute('INSERT INTO review (engagement_id, customer_id, designer_id, rating)'
                         ' VALUES (?, ?, ?, 5)', (done, other, d))


def test_only_the_customer_of_the_job_can_review_it_and_only_once(make):
    c, d, job = completed_job(make)
    with pytest.raises(PermissionDenied):
        reviews.submit(make.user('customer'), job, 5, 'I was not there')
    with pytest.raises(NotFoundError):
        reviews.submit(c, 9999, 5, '')
    review_id = reviews.submit(c, job, 4, 'Good work')
    assert Review.find(review_id)['rating'] == 4
    with pytest.raises(ValidationError):
        reviews.submit(c, job, 5, 'Second go')


@pytest.mark.parametrize('rating', [0, 6, -1, '0', '6', 'abc', '4.5', '', None, True, 3.5])
def test_bad_ratings_are_refused(make, rating):
    c, d, job = completed_job(make)
    with pytest.raises(ValidationError):
        reviews.submit(c, job, rating, '')


@pytest.mark.parametrize('rating,expected', [(1, 1), ('5', 5), (' 3 ', 3)])
def test_good_ratings_are_accepted(make, rating, expected):
    c, d, job = completed_job(make)
    assert Review.find(reviews.submit(c, job, rating, ''))['rating'] == expected


def test_comment_is_optional_trimmed_and_limited(make):
    c, d, job = completed_job(make)
    with pytest.raises(ValidationError):
        reviews.submit(c, job, 5, 'x' * 1001)
    review = Review.find(reviews.submit(c, job, 5, '   '))
    assert review['comment'] == '' and review['sentiment'] is None and json.loads(review['aspects']) == []


def test_text_is_analysed_when_saved(make):
    c, d, job = completed_job(make)
    review = Review.find(reviews.submit(c, job, 5, 'Very responsive and kept me informed. Loved the creative ideas!'))
    assert review['sentiment'] > 0
    assert {'aspect': 'communication', 'polarity': 1} in json.loads(review['aspects'])


def test_html_in_a_review_is_stored_as_text_not_removed(make):
    c, d, job = completed_job(make)
    review = Review.find(reviews.submit(c, job, 5, '<script>alert(1)</script>'))
    assert review['comment'] == '<script>alert(1)</script>'         # escaping happens in the template


def test_edit_and_delete_are_for_the_author_only(make):
    c, d, job = completed_job(make)
    review_id = reviews.submit(c, job, 5, 'Great')
    stranger = make.user('customer')
    for action in (lambda: reviews.edit(stranger, review_id, 1, 'Hacked'), lambda: reviews.delete(stranger, review_id)):
        with pytest.raises(PermissionDenied):
            action()
    reviews.edit(c, review_id, 2, 'Terrible, rude and slow.')
    edited = Review.find(review_id)
    assert (edited['rating'], edited['edit_count']) == (2, 1) and edited['sentiment'] < 0
    with pytest.raises(ValidationError):
        reviews.edit(c, review_id, 9, 'bad rating')
    reviews.delete(c, review_id)
    assert Review.find(review_id) is None
    with pytest.raises(NotFoundError):
        reviews.edit(c, review_id, 5, '')


def test_review_form_checks_ownership_and_status(make):
    c, d, job = completed_job(make)
    assert reviews.for_review_form(c, job)[1] is None
    with pytest.raises(PermissionDenied):
        reviews.for_review_form(make.user('customer'), job)
    open_job = make.engagement(c, d, 'ongoing')
    with pytest.raises(ValidationError):
        reviews.for_review_form(c, open_job)


# ---------------------------------------------------------------- replies, reports, moderation
def test_reply_is_for_the_reviewed_designer_and_empty_removes_it(make):
    c, d, job = completed_job(make)
    review_id = reviews.submit(c, job, 4, 'Fine')
    with pytest.raises(PermissionDenied):
        reviews.reply(make.user('designer'), review_id, 'Not mine')
    reviews.reply(d, review_id, 'Thank you!')
    assert Review.find(review_id)['designer_reply'] == 'Thank you!'
    with pytest.raises(ValidationError):
        reviews.reply(d, review_id, 'x' * 501)
    reviews.reply(d, review_id, '')
    assert Review.find(review_id)['designer_reply'] is None


def test_report_needs_a_reason_and_the_right_designer(make):
    c, d, job = completed_job(make)
    review_id = reviews.submit(c, job, 1, 'Fake!')
    with pytest.raises(ValidationError):
        reviews.report(d, review_id, '  ')
    with pytest.raises(PermissionDenied):
        reviews.report(make.user('designer'), review_id, 'spam')
    reviews.report(d, review_id, 'I never worked with this person')
    assert 'never worked' in Review.find(review_id)['reported_reason']
    queue = {r['id']: r for r in reviews.moderation_queue()}
    assert any('Reported by the designer' in f for f in queue[review_id]['flags'])
    reviews.dismiss_report(review_id)
    assert Review.find(review_id)['reported_reason'] is None


def test_hidden_reviews_stop_counting_and_can_be_restored(make):
    d = make.user('designer')
    keep = make.reviewed_job(d, 5)
    abusive = make.reviewed_job(d, 1)
    assert board.profile(d, NOW)['stats']['reviews'] == 2
    with pytest.raises(ValidationError):
        reviews.hide(abusive, ' ')                                   # a reason is required
    reviews.hide(abusive, 'Abusive language')
    profile = board.profile(d, NOW)
    assert profile['stats']['reviews'] == 1 and profile['stats']['avg_rating'] == 5
    assert [r['id'] for r in profile['reviews']] == [keep]
    reviews.restore(abusive)
    assert board.profile(d, NOW)['stats']['reviews'] == 2
    with pytest.raises(NotFoundError):
        reviews.hide(9999, 'x')


def test_moderation_queue_puts_flagged_reviews_first(make):
    d = make.user('designer')
    clean = make.reviewed_job(d, 4, 'Solid job, tidy finish and on time.', 0.6, created='2026-08-01 09:00:00')
    odd = make.reviewed_job(d, 5, 'Terrible awful worst ever', -0.9, created='2026-09-05 09:00:00')
    queue = reviews.moderation_queue()
    assert queue[0]['id'] == odd and queue[0]['flags'] and queue[-1]['id'] == clean and not queue[-1]['flags']


# ---------------------------------------------------------------- leaderboard and profile
def test_leaderboard_ranks_and_lists_designers_without_reviews(make):
    best, weak, new = make.user('designer'), make.user('designer'), make.user('designer')
    for _ in range(8):
        make.reviewed_job(best, 5)
        make.reviewed_job(weak, 2)
    rows = board.leaderboard(now=NOW)['rows']
    assert rows[0]['id'] == best and rows[0]['rank'] == 1
    assert {r['id'] for r in rows} == {best, weak, new}              # the new designer is listed too
    assert [r['rank'] for r in rows] == sorted(r['rank'] for r in rows)


def test_filters_by_category_housing_and_minimum_reviews(make):
    a, b = make.user('designer'), make.user('designer')
    modern = make.category('Modern')
    make.tag(make.project(a, property_type='Condo'), modern)
    make.project(b, property_type='HDB')
    make.reviewed_job(a, 5)
    ids = lambda **kw: {r['id'] for r in board.leaderboard(now=NOW, **kw)['rows']}
    assert ids(category_id=str(modern)) == {a}
    assert ids(property_type='Condo') == {a} and ids(property_type='HDB') == {b}
    assert ids(min_reviews='1') == {a} and ids(min_reviews='2') == set()


@pytest.mark.parametrize('kwargs', [{'category_id': 'abc'}, {'category_id': '9999'}, {'property_type': 'Castle'},
                                    {'min_reviews': '-1'}, {'min_reviews': 'x'}, {'min_reviews': '51'}])
def test_leaderboard_rejects_bad_filters(make, kwargs):
    with pytest.raises(ValidationError):
        board.leaderboard(**kwargs)


def test_inactive_category_cannot_be_used_as_a_filter(make):
    with pytest.raises(ValidationError):
        board.leaderboard(category_id=str(make.category('Old', active=0)))


def test_filters_do_not_change_a_designers_score(make):
    a, b = make.user('designer'), make.user('designer')
    make.project(a, property_type='Condo')
    for _ in range(5):
        make.reviewed_job(a, 5)
        make.reviewed_job(b, 3)
    everyone = {r['id']: r['score'] for r in board.leaderboard(now=NOW)['rows']}
    only_a = {r['id']: r['score'] for r in board.leaderboard(property_type='Condo', now=NOW)['rows']}
    assert only_a == {a: everyone[a]}


def test_weights_from_the_url(make):
    assert board.weights_from_args({'w_rating': '10', 'w_sentiment': '', 'other': '1'}) == {'rating': '10'}
    d = make.user('designer'); make.reviewed_job(d, 5)
    result = board.leaderboard(weights={'rating': 'abc', 'interest': '-4'}, now=NOW)
    assert result['weights']['rating'] == 40 and result['weights']['interest'] == 15      # bad values -> defaults


def test_profile_distribution_aspects_and_monthly(make):
    d = make.user('designer')
    for rating, created in [(5, '2026-10-02 10:00:00'), (5, '2026-10-20 10:00:00'), (4, '2026-09-15 10:00:00'), (1, '2026-06-01 10:00:00')]:
        make.reviewed_job(d, rating, 'ok', 0.5, created=created,
                          aspects=json.dumps([{'aspect': 'communication', 'polarity': 1}, {'aspect': 'budget', 'polarity': -1}]))
    make.reviewed_job(d, 3, 'meh', 0.0, created='2026-10-25 10:00:00', aspects=json.dumps([{'aspect': 'budget', 'polarity': -1}]))
    profile = board.profile(d, NOW)
    assert profile['distribution'] == {5: 2, 4: 1, 3: 1, 2: 0, 1: 1}
    assert profile['aspects']['praised'] == [('communication', 4)]
    assert profile['aspects']['criticised'] == [('budget', 5)]
    months = {m['label']: m for m in profile['monthly']}
    assert [m['label'] for m in profile['monthly']][-1] == '2026-10' and len(profile['monthly']) == 6
    assert months['2026-10']['count'] == 3 and months['2026-10']['average'] == pytest.approx((5 + 5 + 3) / 3, abs=0.01)
    assert months['2026-08']['average'] is None                       # a month without reviews stays empty


def test_aspect_needs_two_mentions_and_a_clear_lead(make):
    d = make.user('designer')
    make.reviewed_job(d, 5, 'x', 0.5, aspects=json.dumps([{'aspect': 'quality', 'polarity': 1}]))
    assert board.profile(d, NOW)['aspects'] == {'praised': [], 'criticised': []}      # one mention is not a theme
    make.reviewed_job(d, 5, 'x', 0.5, aspects=json.dumps([{'aspect': 'quality', 'polarity': -1}]))
    assert board.profile(d, NOW)['aspects'] == {'praised': [], 'criticised': []}      # a tie is not a theme


def test_profile_of_a_non_designer_is_not_found(make):
    with pytest.raises(NotFoundError):
        board.profile(make.user('customer'), NOW)
    with pytest.raises(NotFoundError):
        board.profile(9999, NOW)


# ---------------------------------------------------------------- the review tables
def test_tables_are_created_on_start_up_without_touching_existing_data(tmp_path):
    """An existing database (made with schema.sql only) gets the review tables when the site starts."""
    path = str(tmp_path / 'old.sqlite')
    app = create_app({'TESTING': True, 'DATABASE': path, 'UPLOAD_FOLDER': str(tmp_path)})
    with app.app_context():
        from idfinder.db import init_db
        init_db()
    connection = sqlite3.connect(path)
    connection.executescript('drop table review; drop table engagement;')       # as if the DB predates the feature
    connection.execute("insert into user (name, password, email, phone, Usertype) values ('Keep', 'x', 'k@t.com', '1', 'customer')")
    connection.commit(); connection.close()

    create_app({'TESTING': True, 'DATABASE': path, 'UPLOAD_FOLDER': str(tmp_path)})
    connection = sqlite3.connect(path)
    tables = {r[0] for r in connection.execute("select name from sqlite_master where type = 'table'")}
    assert {'engagement', 'review'} <= tables
    assert connection.execute('select count(*) from user').fetchone()[0] == 1   # existing data kept


def test_start_up_is_repeatable(tmp_path):
    path = str(tmp_path / 'x.sqlite')
    for _ in range(3):
        create_app({'TESTING': True, 'DATABASE': path, 'UPLOAD_FOLDER': str(tmp_path)})


def test_init_db_also_clears_reviews(app, make):
    c, d, job = completed_job(make)
    review_id = reviews.submit(c, job, 5, 'Great')
    from idfinder.db import init_db
    init_db()                                                           # what `flask init-db` runs
    assert get_db().execute('select count(*) from review').fetchone()[0] == 0
    assert get_db().execute('select count(*) from engagement').fetchone()[0] == 0

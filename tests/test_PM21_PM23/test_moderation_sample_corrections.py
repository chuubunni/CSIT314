from pathlib import Path

from idfinder.controller.review_controller import ReviewController
from idfinder.controller.review_integrity import flag_reviews
from idfinder.db import get_db
from idfinder.entities.review import Review
from repair_sample_review_text import repair
from seed_review_sample_data import COMMENTS, DETAILS


def marker(db, key, job):
    db.execute('''CREATE TABLE IF NOT EXISTS review_sample_seed_job
                  (seed_key TEXT PRIMARY KEY,engagement_id INTEGER UNIQUE)''')
    db.execute('INSERT INTO review_sample_seed_job VALUES (?,?)', (key, job))
    db.commit()


def legacy_text():
    return COMMENTS[4][0].format(detail=DETAILS[0]) + ' This was for our home in Bishan.'


def test_seed_repair_preserves_real_edited_and_moderated_reviews(make):
    db = get_db()
    customer, designer = make.user(), make.user('designer')
    sample_job = make.engagement(customer, designer, title='Space planning consultation - Bishan')
    sample = make.review(sample_job, rating=4, comment=legacy_text())
    marker(db, 'review-history-v1:one:0', sample_job)
    original = dict(Review.find(sample))
    others = []
    for kind in ('genuine', 'edited', 'hidden', 'reported'):
        job = make.engagement(customer, designer, title='Space planning consultation - Bishan')
        review = make.review(job, rating=4, comment=legacy_text())
        if kind != 'genuine':marker(db, 'review-history-v1:' + kind + ':0', job)
        if kind == 'edited':db.execute('UPDATE review SET edit_count=1 WHERE id=?', (review,))
        if kind == 'hidden':db.execute("UPDATE review SET status='hidden',hidden_reason='Keep this decision' WHERE id=?", (review,))
        if kind == 'reported':db.execute("UPDATE review SET reported_reason='Please investigate' WHERE id=?", (review,))
        db.commit()
        others.append((review, dict(Review.find(review))))
    assert repair(db)['updated'] == 1
    corrected = dict(Review.find(sample))
    assert corrected['comment'] != original['comment']
    for k in original:
        if k not in ('comment', 'sentiment', 'aspects'):assert corrected[k] == original[k]
    for review, before in others:assert dict(Review.find(review)) == before
    assert repair(db)['updated'] == 0


def test_many_real_duplicates_still_flagged_but_display_compactly(make, app):
    designer = make.user('designer')
    manager = make.user('manager')
    text = 'We received exactly the same copied proposal without any of the changes requested.'
    ids = []
    for _ in range(12):
        customer = make.user()
        ids.append(make.review(make.engagement(customer, designer), comment=text))
    rows = ReviewController().moderation_queue()
    assert len(rows) == 12
    assert all(len(r['duplicate_flags']) == 11 for r in rows)
    assert all(any('identical' in f for f in r['flags']) for r in rows)
    client = app.test_client()
    with client.session_transaction() as session:session['user_id'] = manager
    response = client.get('/platform/reviews/')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count('Similar wording found in 11 other reviews.') == 12
    assert '<details class="rv-duplicate-details">' in html
    assert '<details class="rv-duplicate-details" open' not in html
    assert 'Reason for hiding' in html
    assert 'within 24 hours' in html

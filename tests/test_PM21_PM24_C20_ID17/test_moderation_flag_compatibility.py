"""Keep v3 review safeguards compatible with the compact moderation display."""
from idfinder.controller.review_controller import ReviewController
from idfinder.entities.review import Review


def test_many_real_duplicates_still_flagged_but_display_compactly(make, app):
    designer = make.user('designer')
    manager = make.user('manager')
    text = 'We received exactly the same copied proposal without any of the changes requested.'
    for _ in range(12):
        customer = make.user()
        make.review(make.engagement(customer, designer), comment=text)
    rows = ReviewController().moderation_queue()
    assert len(rows) == 12
    assert all(len(r['duplicate_flags']) == 11 for r in rows)
    assert all(any('identical' in f for f in r['flags']) for r in rows)
    assert all(set(r['duplicate_flags'] + r['other_flags']) == set(r['flags']) for r in rows)
    client = app.test_client()
    with client.session_transaction() as session: session['user_id'] = manager
    response = client.get('/platform/reviews/')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count('Similar wording found in 11 other reviews.') == 12
    assert '<details class="rv-duplicate-details">' in html
    assert '<details class="rv-duplicate-details" open' not in html
    assert 'Reason for hiding' in html
    assert 'within 24 hours' in html


def test_report_reason_and_review_survive_hide_restore_and_dismiss(make, app):
    customer, designer, manager = make.user(), make.user('designer'), make.user('manager')
    review = make.review(make.engagement(customer,designer),rating=1,comment='Awful',sentiment=-.9,
                         reported_reason='Not a real customer')
    row = ReviewController().moderation_queue()[0]
    assert row['duplicate_flags'] == []
    assert 'Reported by the designer: Not a real customer' in row['other_flags']
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = manager
        session['story_form_token'] = 'moderation-test'
    page = client.get('/platform/reviews/')
    assert b'Not a real customer' in page.data and b'Awful' in page.data
    base = {'form_token':'moderation-test'}
    assert client.post(f'/platform/reviews/{review}/hide', data={**base,'reason':'Abusive'}).status_code == 302
    assert Review.find(review)['status'] == 'hidden'
    assert b'Awful' not in client.get(f'/designers/{designer}').data
    assert client.post(f'/platform/reviews/{review}/restore', data=base).status_code == 302
    assert Review.find(review)['status'] == 'visible'
    assert b'Not a real customer' in client.get('/platform/reviews/').data
    assert client.post(f'/platform/reviews/{review}/dismiss', data=base).status_code == 302
    assert Review.find(review)['reported_reason'] is None


def test_reviews_without_flags_still_supply_both_display_lists(make):
    customer, designer = make.user(), make.user('designer')
    make.review(make.engagement(customer,designer),comment='A useful consultation with clear advice.')
    row = ReviewController().moderation_queue()[0]
    assert row['flags'] == row['duplicate_flags'] == row['other_flags'] == []

from idfinder.controller.review_controller import ReviewController


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

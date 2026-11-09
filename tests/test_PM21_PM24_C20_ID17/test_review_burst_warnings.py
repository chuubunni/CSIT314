"""C18: overlapping review bursts retain one accurate warning, without hiding evidence."""
from datetime import datetime,timedelta
from idfinder.controller.review_integrity import flag_reviews

T0=datetime(2026,10,20,12)


def review(i,hours=0,designer=1,reported=None):
    return {'id':i,'designer_id':designer,'customer_id':i,'comment':'','rating':4,'sentiment':None,
            'created':T0+timedelta(hours=hours),'customer_joined':T0-timedelta(days=30),
            'job_created':T0-timedelta(days=10),'job_completed':T0-timedelta(days=2),'reported_reason':reported}


def burst(flags,i):
    return [f for f in flags.get(i,[]) if 'reviews for this designer within 24 hours' in f]


def test_overlapping_five_review_windows_show_only_the_highest_count():
    flags=flag_reviews([review(i,hours=i) for i in range(1,6)])
    assert all(burst(flags,i)==['5 reviews for this designer within 24 hours'] for i in range(1,6))


def test_overlapping_chain_does_not_merge_more_than_24_hours():
    flags=flag_reviews([review(i,hours=h) for i,h in enumerate([0,10,20,30],1)])
    assert all(burst(flags,i)==['3 reviews for this designer within 24 hours'] for i in range(1,5))


def test_separate_bursts_and_designers_keep_their_own_counts():
    rows=[review(i,hours=i) for i in range(1,4)]
    rows += [review(i,hours=72+i) for i in range(4,8)]
    rows += [review(8,designer=2),review(9,designer=2)]
    flags=flag_reviews(rows)
    assert all(burst(flags,i)==['3 reviews for this designer within 24 hours'] for i in range(1,4))
    assert all(burst(flags,i)==['4 reviews for this designer within 24 hours'] for i in range(4,8))
    assert not burst(flags,8) and not burst(flags,9)


def test_24_hour_boundary_is_inclusive_but_does_not_extend_it():
    rows=[review(1,0),review(2,1),review(3,24)]
    assert all(len(burst(flag_reviews(rows),i))==1 for i in (1,2,3))
    rows[2]['created']+=timedelta(microseconds=1)
    assert flag_reviews(rows)=={}


def test_other_integrity_reasons_are_not_discarded():
    rows=[review(i,i,reported='Please investigate' if i==1 else None) for i in range(1,6)]
    flags=flag_reviews(rows)
    assert len(burst(flags,1))==1
    assert 'Reported by the designer: Please investigate' in flags[1]


def test_moderation_page_renders_one_burst_warning_per_review(make,app):
    designer,manager=make.user('designer'),make.user('manager')
    for i in range(5):
        customer=make.user()
        make.review(make.engagement(customer,designer),comment=f'Feedback {i}',created=f'2026-10-20 {10+i:02d}:00:00')
    client=app.test_client()
    with client.session_transaction() as session:session['user_id']=manager
    page=client.get('/platform/reviews/')
    assert page.status_code==200
    html=page.get_data(as_text=True)
    assert html.count('5 reviews for this designer within 24 hours')==5
    assert '4 reviews for this designer within 24 hours' not in html
    assert '3 reviews for this designer within 24 hours' not in html
    assert 'Reason for hiding' in html

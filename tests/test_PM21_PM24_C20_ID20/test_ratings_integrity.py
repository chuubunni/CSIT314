"""review_integrity.py: the checks that flag possibly fake reviews."""
from datetime import datetime, timedelta

from idfinder.controller.review_integrity import flag_reviews

T0 = datetime(2026, 10, 20, 12, 0, 0)


def review(i, designer=1, customer=None, comment='', rating=4, sentiment=None, created=T0,
           joined=T0 - timedelta(days=30), job_start=T0 - timedelta(days=10), job_end=T0 - timedelta(days=2),
           reported=None):
    return {'id': i, 'designer_id': designer, 'customer_id': customer or i, 'comment': comment,
            'rating': rating, 'sentiment': sentiment, 'created': created, 'customer_joined': joined,
            'job_created': job_start, 'job_completed': job_end, 'reported_reason': reported}


def reasons(flags, i):
    return ' | '.join(flags.get(i, []))


def test_a_normal_review_has_no_flags():
    assert flag_reviews([review(1, comment='Good work overall, thank you.')]) == {}


def test_near_identical_wording_from_different_customers_is_flagged():
    text = 'Best designer in Singapore, highly recommend, five stars!'
    flags = flag_reviews([review(1, comment=text), review(2, comment=text + ' ')])
    assert 'identical' in reasons(flags, 1) and 'identical' in reasons(flags, 2)


def test_same_customer_repeating_their_own_words_is_not_flagged_as_duplicate():
    text = 'Best designer in Singapore, highly recommend, five stars!'
    assert flag_reviews([review(1, customer=7, comment=text), review(2, customer=7, comment=text)]) == {}


def test_short_texts_are_not_compared():
    assert flag_reviews([review(1, comment='Good!'), review(2, comment='Good!')]) == {}


def test_a_burst_of_reviews_for_one_designer_is_flagged():
    burst = [review(i, created=T0 + timedelta(hours=i)) for i in (1, 2, 3)]
    flags = flag_reviews(burst)
    assert all('within 24 hours' in reasons(flags, i) for i in (1, 2, 3))


def test_reviews_spread_over_time_or_for_different_designers_are_not_a_burst():
    spread = [review(i, created=T0 + timedelta(days=3 * i)) for i in (1, 2, 3)]
    other = [review(i, designer=i, created=T0 + timedelta(hours=i)) for i in (1, 2, 3)]
    assert flag_reviews(spread) == {} and flag_reviews(other) == {}


def test_brand_new_account_and_instant_job_are_flagged():
    flags = flag_reviews([review(1, joined=T0 - timedelta(hours=3), job_start=T0 - timedelta(minutes=30), job_end=T0 - timedelta(minutes=5))])
    assert 'less than a day old' in reasons(flags, 1)
    assert 'under an hour' in reasons(flags, 1)


def test_stars_and_words_that_disagree_are_flagged():
    assert 'opposite' in reasons(flag_reviews([review(1, rating=5, sentiment=-0.8)]), 1)
    assert 'opposite' in reasons(flag_reviews([review(1, rating=1, sentiment=0.8)]), 1)
    assert flag_reviews([review(1, rating=5, sentiment=0.8)]) == {}
    assert flag_reviews([review(1, rating=5, sentiment=None)]) == {}


def test_designer_report_is_always_shown():
    assert 'Reported by the designer: spam' in reasons(flag_reviews([review(1, reported='spam')]), 1)

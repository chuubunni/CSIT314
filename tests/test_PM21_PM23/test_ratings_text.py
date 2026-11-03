"""review_text.py: sentiment and which topics a review praises or criticises."""
import pytest

from idfinder.controller import review_text


@pytest.fixture(params=['vader', 'fallback'])
def engine(request, monkeypatch):
    """Run every test with both engines, so the site behaves the same when VADER is not installed."""
    if request.param == 'fallback':
        monkeypatch.setattr(review_text, '_VADER', None)
    elif review_text._VADER is None:
        pytest.skip('vaderSentiment is not installed')
    return request.param


def test_no_text_has_no_sentiment(engine):
    assert review_text.sentiment('') is None
    assert review_text.sentiment('   ') is None
    assert review_text.analyse(None) == (None, [])


def test_positive_and_negative_text(engine):
    assert review_text.sentiment('Great designer, excellent work, I love the result!') > 0.4
    assert review_text.sentiment('Terrible experience, rude and unprofessional.') < -0.4


def test_negation_flips_meaning(engine):
    assert review_text.sentiment('The work was not good.') < 0


def test_sentiment_is_within_range(engine):
    for text in ('!!!!!!!!', 'great ' * 200, 'terrible ' * 200, '12345'):
        assert -1 <= review_text.sentiment(text) <= 1


def test_aspects_pick_out_topic_and_direction(engine):
    found = review_text.aspects('Very responsive and kept me informed. But the project was delayed by weeks.')
    assert {'aspect': 'communication', 'polarity': 1} in found
    assert {'aspect': 'timeliness', 'polarity': -1} in found


def test_neutral_mentions_are_ignored(engine):
    assert review_text.aspects('We discussed the budget on Tuesday.') == []


def test_keywords_match_whole_words_not_fragments(engine):
    # "designer" must not count as the creativity topic, "plate" must not count as "late"
    assert review_text.aspects('The designer was great and I loved my new plate collection.') == []


def test_aspects_are_sorted_and_unique(engine):
    found = review_text.aspects('Excellent communication. Fantastic communication. Great quality.')
    assert [a['aspect'] for a in found] == ['communication', 'quality']

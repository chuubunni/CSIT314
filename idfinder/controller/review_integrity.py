"""Spots reviews that may be fake or abusive, so the platform manager can look at them first.
Pure functions: no Flask, no SQL. Every flag comes with a plain-English reason.

CHECKS
  duplicate_text   almost the same wording as another review by someone else (difflib similarity)
  burst            3+ reviews for the same designer within 24 hours
  new_account      the reviewer's account was less than a day old when they reviewed
  instant_job      the job went from request to completed in under an hour
  rating_mismatch  stars and words disagree (5 stars but a very negative text, or the reverse)
  reported         the designer reported it (always shown)
"""
from datetime import timedelta
from difflib import SequenceMatcher

from idfinder.controller.ranking import to_datetime

SIMILARITY = 0.85
WORD_OVERLAP = 0.4            # speed filter only: texts sharing fewer than 40% of their words are never 85% alike
BURST_COUNT = 3
BURST_WINDOW = timedelta(hours=24)
MIN_TEXT_LENGTH = 20          # very short texts ("good!") are not compared for duplication


def _normalise(text):
    return ' '.join((text or '').lower().split())


def flag_reviews(reviews):
    """reviews: dicts with id, designer_id, customer_id, comment, rating, sentiment, created,
    customer_joined, job_created, job_completed, reported_reason.
    Returns {review_id: [reason, ...]} for the reviews that have at least one flag."""
    flags = {}

    def add(review_id, reason):
        flags.setdefault(review_id, []).append(reason)

    texts = {r['id']: _normalise(r['comment']) for r in reviews}

    # duplicate wording. Many reviews share exactly the same text, so group them first and compare each
    # DISTINCT text pair once with difflib (its full ratio() is slow; two cheap upper bounds rule out most pairs).
    by_id = {r['id']: r for r in reviews}
    groups = {}
    for r in reviews:
        if len(texts[r['id']]) >= MIN_TEXT_LENGTH:
            groups.setdefault(texts[r['id']], []).append(r['id'])

    def flag_pair(first, second):
        if by_id[first]['customer_id'] != by_id[second]['customer_id']:      # one person reusing their own wording is fine
            add(first, f'Wording is almost identical to review #{second}')
            add(second, f'Wording is almost identical to review #{first}')

    distinct = list(groups)
    for text, members in groups.items():                       # the very same wording used more than once
        for i, first in enumerate(members):
            for second in members[i + 1:]:
                flag_pair(first, second)
    words = {text: set(text.split()) for text in distinct}
    for i, first_text in enumerate(distinct):
        matcher = SequenceMatcher(None)
        matcher.set_seq2(first_text)                           # difflib caches work on seq2, so set it once per text
        first_words = words[first_text]
        for second_text in distinct[i + 1:]:
            # cheap filters first: texts that are 85% the same letter-by-letter share most of their words
            second_words = words[second_text]
            if len(first_words & second_words) < WORD_OVERLAP * len(first_words | second_words):
                continue
            matcher.set_seq1(second_text)
            if (matcher.real_quick_ratio() >= SIMILARITY and matcher.quick_ratio() >= SIMILARITY
                    and matcher.ratio() >= SIMILARITY):
                for first in groups[first_text]:
                    for second in groups[second_text]:
                        flag_pair(first, second)

    # C18: keep only the largest qualifying 24-hour burst containing each review.
    # Overlapping windows must not produce several warnings on the same review.
    burst_counts = {}
    per_designer = {}
    for r in reviews:
        per_designer.setdefault(r['designer_id'], []).append(r)
    for designer_reviews in per_designer.values():
        stamped = sorted(((to_datetime(r['created']), r['id']) for r in designer_reviews
                          if to_datetime(r['created'])))
        for start_index, (start, _) in enumerate(stamped):
            window = [rid for t, rid in stamped[start_index:] if t - start <= BURST_WINDOW]
            if len(window) >= BURST_COUNT:
                for rid in window:
                    burst_counts[rid] = max(burst_counts.get(rid, 0), len(window))
    for rid, count in burst_counts.items():
        add(rid, f'{count} reviews for this designer within 24 hours')

    for r in reviews:
        created, joined = to_datetime(r['created']), to_datetime(r.get('customer_joined'))
        if created and joined and timedelta(0) <= created - joined < timedelta(days=1):
            add(r['id'], 'Reviewer account was less than a day old')
        job_start, job_end = to_datetime(r.get('job_created')), to_datetime(r.get('job_completed'))
        if job_start and job_end and job_end - job_start < timedelta(hours=1):
            add(r['id'], 'Job went from request to completed in under an hour')
        s = r.get('sentiment')
        if s is not None and ((r['rating'] >= 4 and s <= -0.4) or (r['rating'] <= 2 and s >= 0.4)):
            add(r['id'], f"{r['rating']} stars but the text reads the opposite way")
        if r.get('reported_reason'):
            add(r['id'], 'Reported by the designer: ' + r['reported_reason'])
    # C18: preserve every duplicate match; the moderation page collapses the evidence.
    return flags

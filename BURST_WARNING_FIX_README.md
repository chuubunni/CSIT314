# Review burst warning fix

Stop Flask, then extract this ZIP into the CSIT314 repository root and replace
idfinder/controller/review_integrity.py. Restart Flask and refresh Review Moderation.
No database reset, migration, seed or review deletion is needed.

Overlapping 24-hour windows previously added multiple warnings to the same review,
such as 5 reviews, 4 reviews and 3 reviews. Each review now gets ONE warning using
the largest qualifying window that actually contains that review.

The 24-hour interval and three-review threshold are unchanged. Separate designers
and separate time periods keep their own counts. Overlapping groups are not joined
into a group spanning more than 24 hours. Duplicate-text evidence, designer reports,
new-account, instant-job and rating-mismatch warnings remain enabled.

C18 comments identify the change. The supplied regression tests cover overlap,
separate groups/designers, the exact 24-hour boundary, retention of other warnings
and the rendered manager page. The relevant test run passed 39 tests.

Optional check (pytest must be installed):

  .venv\Scripts\python.exe -B -m pytest tests/test_PM21_PM23/test_review_burst_warnings.py -q

This ZIP contains only the fix, its tests and notes. No database, AI configuration,
uploads or private keys are included. Your local repo was not changed to create it.

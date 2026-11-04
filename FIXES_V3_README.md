# CSIT314 fixes v3 — complete replacement patch

Built on 4 November 2026 from current main b0e1a21, with the ten files in your
provided CSIT314_fixes_v2.zip applied first, then the corrections below.
This is a consolidated changed/new-files-only ZIP: it includes the v2 files
needed by these fixes and the missing entity, boundary and template changes.
No AI image-analysis integration, database, uploads or private key is included.
Your actual local repository and database were not changed during this work.

## Install

1. Stop Flask with Ctrl+C. Back up your repository.
2. Extract ALL files into the CSIT314 root (the folder containing requirements.txt
   and idfinder), replacing matching files. Do not copy only the controllers:
   the review/engagement entities and templates are necessary for the fix.
3. From the repository root, verify that the replacement files are present:

   .venv\Scripts\python.exe -B verify_fixes_v3.py

4. Restart Flask so it imports the new files:

   .venv\Scripts\python.exe -B -m flask --app idfinder run --debug

5. Refresh your browser. No reset, init-db command, data seed or database
   replacement is required. Existing accounts and reviews remain in place.

The supplied verifier compares installed source files against SHA256 hashes in
FIXES_V3_MANIFEST.json. If a file is missing or differs, it prints its path and
exits unsuccessfully. Resolve that before relying on the running application.
Restarting Flask is still necessary even when verification passes.

## Fixes and expected behaviour

1. Chart date underflow: the common parser used by weekly, trend, heatmap and
   category-trend rejects 0001 dates before any window subtraction. It enforces
   YYYY-MM-DD, a minimum date of 2000-01-01 and no future end dates. Invalid dates
   return JSON HTTP 400 on all four routes. The earliest supported date returns
   200 on all four routes. The supplied v2 controller already contained a lower
   date guard; this package retains it, makes parsing consistent, and tests the
   actual routes rather than only a helper or a note in documentation.

2. Published-only charts: draft, pending and rejected projects are excluded from
   new-project counts AND from views/favourites attributed to those projects.
   The same rule applies to daily/weekly/trend metrics, the heatmap, category
   totals, category trends and the dashboard report/interest list. New-user
   counts still include all users, independently of project publishing.

3. Oversized route IDs: an SQLite-sized integer converter validates IDs before
   a query is attempted. IDs above signed 64-bit range, including thousands of
   digits, return 404. This covers the existing integer-ID routes, not only
   /designers/<id>. Existing valid ID routes continue to work.

4. Double-submitted reviews: failed UNIQUE/trigger inserts roll back the
   transaction. The controller shows a controlled validation message instead of
   a server error. New forms carry the review ID and edit revision, so a stale
   create form cannot silently become an edit after another submit succeeds.
   An unchanged legacy POST also does not consume another edit.

5. Hidden reviews/edit limits: hidden reviews cannot be edited. A visible review
   allows at most three content edits (the policy already stated in v2). The
   database UPDATE checks visibility, owner, edit count and expected revision
   together, so concurrent editing/moderation cannot bypass those checks.
   Hidden and final reviews have no edit form. Stale edits show a reload message.
   Hidden review deletion remains blocked, and invalid delete requests return
   a controlled 400 response rather than an uncaught validation error.

6. Manager registration: removed the manager option from the public form and
   retained a strict server allow-list of customer/designer. Forged POSTs with
   type=manager create neither a user nor a manager profile. Existing manager
   accounts still work. There is no new public manager-creation endpoint.

7. SQLite contention: requests use a default one-second busy timeout, then real
   BUSY/LOCKED errors return 503 with Retry-After: 1 and a friendly message.
   Chart/JSON requests receive JSON errors. Failed writes roll back, so no partial
   review is left behind. After the competing transaction releases its lock, the
   request can succeed. This does not forcibly close another application's DB
   connection: finish/close that transaction if it keeps holding the database.
   There are no automatic write retries, which could otherwise duplicate actions.
   Unrelated SQL errors are not misreported as a busy database.

Also repaired a v2 integration mismatch: its engagement controller passed an
expected status to a two-argument entity method. The entity now supports the
atomic status update required by that controller, preserving the normal
hire/accept/complete/review flow. Both review and engagement write failures
explicitly roll back their transactions.

## Verification

- Baseline was current main plus your supplied v2 ZIP, in an isolated folder.
- The initial targeted run reproduced seven regression-test failures; other
  checks confirmed that some controller guards were already present in v2.
- Full suite after corrections: 367 passed, 84 subtests passed.
- Two further real-write-lock/dashboard cases were added afterward. The latest
  focused suite passed all 44 regression cases (369 distinct tests verified).
- Both BEGIN EXCLUSIVE read locks and BEGIN IMMEDIATE write locks were tested
  with real SQLite connections. Requests returned 503 without partial reviews,
  then recovered after unlocking. Tests used a 50 ms busy wait to stay fast;
  the application default is one second, configurable via SQLITE_TIMEOUT.
- No live Gemini requests or paid API calls were made.
- Original repository/source/database hashes remained unchanged.

To rerun the targeted checks (pytest must be available in the environment):

   .venv\Scripts\python.exe -B -m pytest tests/test_PM21_PM23/test_v3_route_regressions.py -q

For the full suite:

   .venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider

Do not run init-db to apply this package; that command clears application data.

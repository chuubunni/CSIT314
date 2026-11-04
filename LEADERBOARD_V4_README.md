# Leaderboard and moderation fixes v4 — fixes only

This ZIP contains leaderboard/review display and scoring fixes only. It does
NOT contain the AI analysis feature, app registration, database, sample-data
scripts, uploaded images, API keys or private configuration.

It is a follow-up to v3. Keep the installed v3 chart/date/ID/registration/SQLite
and atomic review safeguards. These files preserve the v3 review controller
rules while repairing compatibility with the compact moderation page.

## Install

1. Stop Flask with Ctrl+C and back up your code.
2. Extract ALL files into the CSIT314 repository root, replacing matching files.
3. Check that the matching files were installed:

   .venv\Scripts\python.exe -B verify_leaderboard_v4.py

4. Restart Flask and refresh the page:

   .venv\Scripts\python.exe -B -m flask --app idfinder run --debug

No database replacement, migration or data seeding is needed. Do not run init-db.
The older v3 verification manifest will no longer match the intentionally updated
review controller; use the v4 verifier for this patch's files.

## Fixes

- Every moderation row supplies flags, duplicate_flags and other_flags, including
  empty lists. This fixes the KeyError in the screenshot's duplicate-review test.
- Retain all duplicate-match IDs. The older v2 detector shortened evidence to
  three IDs plus a summary, which conflicts with the expanded-list interface.
  The page now handles compact display, with all matches in a closed expandable
  section and a bounded scrolling area. Twelve copied reviews each retain eleven
  other matches, without eleven expanded warnings filling the page.
- Designer reports and all non-duplicate warnings render from other_flags. This
  restores the report reason in the hide/restore/dismiss moderation test.
- Keep hidden-review edit/delete protection, three-edit limit and atomic review
  updates from v3. Genuine duplicate and integrity checks remain enabled.
- Avoid a leaderboard division by zero when projects have views but no favourites.
- Use consistent default weights when every slider is zero. Browser score bars
  and score numbers use the same effective weights as the server. Out-of-range,
  non-finite and overflowing weights are rejected in favour of defaults.
- Explain empty rating breakdowns, the lack of completed jobs and one-month
  histories on designer profiles; show the completed-job count for experience.

## Local AI change made separately

The AI analysis implementation files were already installed in the local repo.
The v3 app initialization had overwritten their registration, so the local
idfinder/__init__.py was repaired to restore GEMINI_IMAGE_MODEL and the single
image_analysis blueprint/rate limiter, preserving all its v3 request safeguards.
The previous __init__.py was backed up outside the repository.

That local AI repair is NOT part of this ZIP. This ZIP does not overwrite
__init__.py, so applying it cannot remove the restored AI registration again.
No database data was changed in either operation. No commit or push was made.

## Verification

- Full combined suite: 401 tests and 84 subtests passed.
- Both tests shown in the screenshots passed, including the original compact
  moderation regression copied into the isolated verification environment.
- Extra checks cover report visibility through hide/restore/dismiss, empty flag
  lists, all v3 routes, scoring edge cases and browser/server weight consistency.
- Browser checks passed for leaderboard scores and the existing AI analysis UI.
- The actual local app was tested against a disposable database: the AI route
  is registered exactly once, the designer form renders and a form token is
  required. No live Gemini API call was made.
- Outside the local AI registration repair, local source and database hashes
  are unchanged. Leaderboard updates remain in this ZIP until you install it.

Optional verification commands (pytest / Node.js required respectively):

   .venv\Scripts\python.exe -B -m pytest tests/test_PM21_PM23/test_moderation_flag_compatibility.py tests/test_PM21_PM23/test_leaderboard_review_regressions.py -q
   node tests/test_leaderboard_client.cjs

The test in an earlier package named test_moderation_sample_corrections.py can
remain in your repo if you installed that package's sample-data helpers. The
new compatibility test here does not depend on any sample-data script.

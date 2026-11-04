# Leaderboard fixes and sample history — current pull db08b4d

This package was built from your 4 November 2026 pull (db08b4d). It contains only
eight modified website source files, the updated database, the sample-data
script, three new test files, these instructions and a validation report.
Your local repository was not edited when this ZIP was prepared.

## Install

1. Stop Flask with Ctrl+C and close DB Browser for SQLite.
2. Save a backup of your repository, especially instance/idfinder.sqLite.
3. Extract this ZIP into the CSIT314 repository root (the folder containing
   requirements.txt and idfinder), replacing matching files.
4. The supplied instance/idfinder.sqLite already contains the new sample data.
   You do NOT need to run the seed script after replacing the database.
5. Start the website in Command Prompt or PowerShell:

   .venv\Scripts\python.exe -B -m flask --app idfinder run --debug

6. Open /leaderboard and a designer profile. Try the sliders, minimum-review
   filter, rating breakdown, experience score and monthly rating chart.

If your database has gained additional changes since this package was made,
extract the code files but KEEP YOUR CURRENT DATABASE instead of replacing it.
Then add the sample data to that database with:

   .venv\Scripts\python.exe seed_review_sample_data.py

The script makes a timestamped database backup, uses one transaction for its
inserts, and tracks its own jobs so reruns do not duplicate the sample history.
For a custom database path, add --database "path\to\database.sqlite".

## What changed

- No division by zero when projects have views but the platform has no favourites.
- All-zero leaderboard weights use the same defaults in the browser and server.
  Score bars use the same effective weights as the score number. Invalid or
  extreme weights cannot overflow the score or produce invalid JSON.
- Delayed job updates cannot overwrite a newer job status. This protects
  completed/reviewed jobs and the reliability and experience calculations.
- Customers cannot delete hidden reviews and repost them to bypass moderation.
  The database deletion also checks status in case moderation happens concurrently.
- Designer profiles explain empty ratings, one-month histories and experience,
  and show how many completed hiring jobs contribute to the experience score.
- The current image-review approval rules remain in place. Unapproved projects
  remain excluded from public leaderboard project filters and project listings.

C18 comments identify the relevant ranking and review integration corrections.

## Data added to a copy of your CURRENT database

- 1,019 jobs: 777 completed, 29 ongoing, 24 requested, 80 declined, 109 cancelled.
- 645 reviews with 1–5 star ratings, varied text/sentiment and 291 designer replies.
- Review history across July–November 2026, respecting account creation dates.
- 151 designers remain in the leaderboard; 139 have completed-job history.
  Newer designers can correctly have no completed jobs yet.

This is fictional coursework activity using the existing accounts. It is not
genuine customer feedback. No existing accounts, passwords, companies, projects,
images, categories, views, favourites, image fingerprints or moderation decisions
were changed. The supplied database retains all 356 users and 251 projects.
Existing jobs and reviews, if present, are preserved by the seed script.

## Verification

- Full current suite plus regression and seed-data checks: 342 passed, 84 subtests.
- Node browser-scoring checks passed for zero, custom and extreme weights.
- Seeded leaderboard HTML/JSON and designer profile returned HTTP 200.
- Database integrity passed; zero foreign-key violations.
- Existing non-history tables compared exactly to the pre-seed snapshot.
- Rerunning the seed added zero jobs, reviews or replies.
- Original local repository source files and database hashes were unchanged.

Optional test commands (pytest / Node.js must be installed for these):

   .venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
   node tests/test_leaderboard_client.cjs

No API key, private config, database backup or uploaded images is included.
The existing uploads folder is used. Gemini is not needed for the leaderboard.

# Start here — CSIT314 merged local repo + CSIT314 (2).zip

Complete merged project, built on 4 November 2026. The local source was based on
main c012212 (Integrated AI image analysis with latest project features). Incoming
code, fixes, review history and sample-data tools came from CSIT314 (2).zip.
The original local repository and both original databases were not modified.

## Run this complete project

1. Extract the ZIP into a NEW folder. The application is inside CSIT314/.
   Keep your existing checkout as a backup until you have checked this version.
2. Open Command Prompt or PowerShell in the extracted CSIT314 folder.
3. Create a fresh virtual environment using Python 3.12 or newer:

   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt

   The root requirements include Flask, NumPy, Pillow and VADER. The original
   idfinder/requirements-image-review.txt is retained and compatible.
4. If using the chatbot or image analysis, set the API key before starting Flask.

   PowerShell:
   $env:GEMINI_API_KEY = "YOUR_API_KEY"
   $env:GEMINI_MODEL = "gemini-3.5-flash-lite"

   Command Prompt:
   set "GEMINI_API_KEY=YOUR_API_KEY"
   set "GEMINI_MODEL=gemini-3.5-flash-lite"

   Alternatively, recreate your private instance/config.py outside Git.
   Your private key/configuration is deliberately not included in this ZIP.
5. Verify the package, then start:

   .venv\Scripts\python.exe -B verify_merged_project.py
   .venv\Scripts\python.exe -B -m flask --app idfinder run --debug

6. Open http://127.0.0.1:5000.

The merged database and its matching uploaded images/review evidence are already
included. Do NOT run init-db, test_data.sql or a seed script to start this copy.
init-db clears application data. No new seeding is necessary for the charts.

## Features retained from both versions

- Customer project favourites and two-project comparison.
- Designer portfolio sorting by newest, views and favourites.
- Uncle David chatbot and its existing project/designer/leaderboard searches.
- AI image analysis with preview and explicit Apply. Exactly one analysis
  endpoint is registered, using the existing server API-key/model configuration.
- Original-image duplicate/fingerprint checking, private pending projects,
  comparison evidence and manager approval/rejection.
- Leaderboard scoring, browser sliders, designer profiles, rating breakdowns,
  experience and monthly history.
- v3 chart date guards, approved-only reporting, oversized-ID handling, duplicate
  review handling, hidden-review/three-edit safeguards, manager-registration
  restriction and controlled SQLite busy responses.
- v4 compact moderation, complete duplicate evidence and visible designer reports.
- Sample-history seed/repair tools and the supplied regression tests. They are
  optional maintenance utilities and are not run automatically on startup.

## Database merge

Used the local database as the foundation. The shared account/company/property
identities were checked before importing history. No local account, password,
portfolio record, image, favourite, fingerprint or review decision was replaced.
All original local view rows were retained.

Copied the incoming 1,019 jobs, 645 reviews and their 1,019 seed markers, plus the
one additional incoming view event. The history rows were verified against the
incoming database. Existing sample dates, ratings, text, replies and moderation
state were retained exactly; no new reviews were invented during the merge.

Final counts:
- 356 accounts.
- 252 projects and 252 project image records, including the extra local project.
- 45,870 project views.
- 1,019 jobs and 645 reviews.

This includes fictional coursework sample feedback from the incoming repo;
it is not genuine customer testimony. The existing accounts/passwords remain
unchanged. No account-password export is included.

## Issues found and resolved

1. Incoming app initialization omitted the AI image-analysis registration and
   GEMINI_IMAGE_MODEL setting even though the feature files were present. Merged
   both back into the initialization containing the request/review safeguards.
2. Incoming shared portfolio files were older and would remove current sorting.
   Kept the local boundary/controller/entity/template together.
3. Incoming favourites code and CSS would remove customer comparison. Kept the
   local comparison implementation, template and styles.
4. Incoming project form would remove AI controls. Kept the current local form.
5. Replacing the local database with the incoming one would lose a local project.
   Combined compatible records instead, preserving local records and incoming
   review history with valid relationships.
6. Several old patch manifests/readmes no longer described the combined files.
   Replaced that patch-installation metadata with this guide, a fresh report,
   source manifest and verifier. No partial patch needs applying to this ZIP.
7. The archive reintroduced idfinder/test_data.sql, intentionally deleted by main
   commit 7f3ea46. Kept that deletion; current seed/repair utilities remain present.

## Checks completed

- 403 Python tests and 84 subtests passed with NumPy 2.5.4, Pillow 13.0.0 and
  VADER 3.3.2 available. Both VADER and fallback sentiment checks ran.
- Browser scoring and AI analysis interaction checks passed.
- 144 page requests across anonymous/customer/designer/manager roles completed
  without a server error. Comparison, profiles, moderation and chart routes were
  also exercised against a COPY of the combined database.
- All four dated chart routes reject 0001-01-01 with HTTP 400.
- Oversized designer IDs return 404, with one AI analysis route registered.
- Database integrity passed; zero foreign-key errors. Every project image and
  review-evidence reference resolves to an included file.
- Local core data was compared exactly to the pre-merge local snapshot, while
  incoming jobs/reviews/seed markers were compared exactly to the incoming data.
- No live Gemini request was made, so API-key/model access and live generated
  output still need to be checked with your own configured key.

Optional test commands (pytest / Node.js needed respectively):

   .venv\Scripts\python.exe -m pip install pytest
   .venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
   node tests/test_leaderboard_client.cjs
   node tests/test_image_analysis_client.cjs

The verifier checks code/template/asset-source files against the merged
manifest. It does not open or change the database and ignores runtime data.

Excluded: .git history, virtual environments, dependency caches, compiled Python
files, private config/API keys, .env files and old database/code backups.
Nothing was committed or pushed.

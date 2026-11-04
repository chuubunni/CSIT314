# CSIT314 1.zip merged with current pull b0e1a21

This package merges the supplied CSIT314 1.zip with the current local/GitHub main
at b0e1a21 (customer comparison function), verified on 4 November 2026.
Only the merge and its conflict resolutions are included. The v3 chart/review/
registration/database-lock fixes are NOT included, as requested.

## Apply

1. Stop Flask with Ctrl+C and back up the current repository.
2. Extract ALL files from this ZIP into the current CSIT314 repository root,
   replacing matching files. Do not choose individual files to copy: this ZIP
   includes the current versions of shared files that the incoming archive had
   overwritten with older code. This removes the legacy duplicate analysis route
   and keeps comparison/sorting together with their templates and data queries.
3. Verify the installed files:

   .venv\Scripts\python.exe -B verify_merged_files.py

4. Set your API key/model as usual before starting Flask, in the same window:

   PowerShell:
   $env:GEMINI_API_KEY = "YOUR_API_KEY"
   $env:GEMINI_MODEL = "gemini-3.5-flash-lite"

   Command Prompt:
   set "GEMINI_API_KEY=YOUR_API_KEY"
   set "GEMINI_MODEL=gemini-3.5-flash-lite"

5. Restart:

   .venv\Scripts\python.exe -B -m flask --app idfinder run --debug

Keep your current instance database, config and uploads. There is no database
replacement, migration, seed or init-db step for this merge. If dependencies are
not installed, use both existing requirement files:

   .venv\Scripts\python.exe -m pip install -r requirements.txt
   .venv\Scripts\python.exe -m pip install -r idfinder\requirements-image-review.txt

## Merge decisions

- Kept current main's customer favourites comparison, including its route,
  controller, database query, favourites UI, comparison template and CSS.
- Kept current main's portfolio sorting by newest, views and favourites.
- Retained the incoming dedicated image-analysis boundary/service, preview UI,
  configuration and tests. The model reads the API key set before Flask starts.
- Kept exactly ONE POST /api/analyze-image route. The archive also had an older
  designer.analyze_image route at the same URL, registered earlier and shadowing
  the dedicated endpoint. That legacy route and its global Google SDK client
  have not been carried over. The current designer boundary is used instead.
- Kept current requirements: the retained image service uses the standard HTTP
  client already used by the chatbot, plus Pillow from the image-review
  requirements. The legacy google-genai dependency is not needed.
- Kept the existing project save/edit/upload pipeline, image fingerprinting,
  duplicate comparison and manager review rules. Analysis only suggests form
  details; it cannot approve or publish a project. The original upload files
  still go through duplicate review on Save.
- Did not import the incoming database, backups or three extra test uploads.
  Your current data and uploaded images remain in place.

Use the image assistant from New project/Edit project: select images, click
Analyse first image, review the suggestions and choose Use these suggestions.
Then complete the remaining fields and save normally. The first newly selected
image is used for analysis. Customer comparison remains under My favourites
once at least two available projects have been saved.

## Verification

- Full merged suite: 337 tests and 84 subtests passed.
- Browser checks passed for explicit apply, original file preservation, session
  token submission, stale image response handling and error recovery.
- New merge checks prove there is exactly one analysis endpoint, customer
  comparison still renders and restricts access to the customer's saved projects,
  and actual portfolio ordering changes correctly for all three sorting modes.
- Existing image-analysis tests prove copied images remain pending/private
  after create/edit saves until the manager approves them.
- The listed v3 source files were compared with current main and remain unchanged.
- Original local source/database hashes remained unchanged while building the merge.
- No live Gemini call was made; tests used simulated API responses.

Optional checks (pytest/Node.js must be available for the respective command):

   .venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
   node tests/test_image_analysis_client.cjs

No .git folder, virtual environment, API key, private config, database or uploads
are included. This is an overlay ZIP of all required merge resolutions and
additions, not an independent clone. Extract it over your current pull.

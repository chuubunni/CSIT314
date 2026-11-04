# Review moderation display and sample-data correction

The prior sample data used too few review templates, so the duplicate-wording
warnings were valid. This package corrects that sample wording and groups
duplicate evidence into an expandable summary on the moderation page.
The similarity threshold, detector and manager moderation controls are unchanged.
All matches remain available inside the expandable section, which has a bounded
scrolling height so it cannot push the moderation controls far down the page.

## Apply

1. Stop Flask with Ctrl+C and close DB Browser for SQLite.
2. Back up your current repository and instance/idfinder.sqLite.
3. Extract this ZIP into your CSIT314 repository root, replacing matching files.
4. The included database is a corrected copy of your current local database,
   made after you installed the leaderboard package. It already contains the
   corrected comments, so you do not need to run either data script.
5. Restart and refresh the moderation page:

   .venvScriptspython.exe -B -m flask --app idfinder run --debug

If your database has additional changes since this package was prepared,
KEEP YOUR OWN DATABASE and extract the other files. Then run:

   .venvScriptspython.exe repair_sample_review_text.py

This makes a timestamped backup and corrects only untouched, visible, unreported
reviews that belong to the original review-history-v1 seed and still contain its
recognised old template text. Genuine reviews, edited sample reviews, hidden
reviews and reported reviews are left alone. The repair is repeatable: a second
run changes zero reviews. A custom database can be supplied with --database.

The updated seed_review_sample_data.py uses the varied wording for future samples.
It still skips previously inserted jobs; it does not replace existing records.

## Data and verification

- Corrected 645 original sample comments and their computed sentiment/aspects.
- All jobs, accounts, ratings, dates, replies, reports and moderation decisions
  were preserved; all non-review tables were compared exactly to the original.
- All 645 reviews remain present. None now trigger duplicate-text warnings.
- Other integrity checks remain active: 64 other warnings still apply to the
  sample history. A warning is a reason to investigate, not proof of abuse.
- Genuine copied reviews from different customers still trigger duplicate checks.
- The moderation page returned HTTP 200 with the corrected database.
- Database integrity and foreign-key checks passed.
- 344 distinct Python tests and 84 subtests verified, including focused reruns
  of the two new correction tests after correcting their test fixture.
- The local repository and database were not changed to create this ZIP.

This remains fictional coursework feedback, not genuine customer testimony.
No private configuration, API key, database backup or image upload is included.
The changes include C18 comments on the relevant additions.

r"""C18: correct only untouched seed-owned review wording, keeping all review history.

Stop Flask and run: .venv\Scripts\python.exe repair_sample_review_text.py
No accounts, jobs, ratings, timestamps, reports or moderation decisions are changed.
"""
import argparse
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3

from idfinder.controller.review_text import analyse
from idfinder.services.sample_review_text import sample_comment
from seed_review_sample_data import COMMENTS, DETAILS, PLACES, TASKS

ROOT = Path(__file__).resolve().parent


def repair(db):
    db.row_factory = sqlite3.Row
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='review_sample_seed_job'").fetchone():
        return {'updated': 0, 'skipped': 0}
    legacy = {rating: {text.format(detail=detail) + f' This was for our home in {place}.'
                       for text in texts for detail in DETAILS for place in PLACES}
              for rating, texts in COMMENTS.items()}
    db.execute('BEGIN IMMEDIATE')
    try:
        rows = db.execute('''SELECT r.*, e.title, s.seed_key FROM review r
            JOIN review_sample_seed_job s ON s.engagement_id=r.engagement_id
            JOIN engagement e ON e.id=r.engagement_id
            WHERE s.seed_key LIKE 'review-history-v1:%' ORDER BY r.id''').fetchall()
        targets = [r for r in rows if r['edit_count'] == 0 and r['status'] == 'visible'
                   and not r['reported_reason'] and r['comment'] in legacy.get(r['rating'], set())]
        target_ids = {r['id'] for r in targets}
        comments = [r['comment'] for r in db.execute('SELECT id,comment FROM review') if r['id'] not in target_ids]
        for row in targets:
            title, _, place = row['title'].partition(' - ')
            task = TASKS.index(title) if title in TASKS else 0
            comment = sample_comment(row['seed_key'], row['rating'], task, place or 'Singapore', comments)
            sentiment, aspects = analyse(comment)
            db.execute('UPDATE review SET comment=?,sentiment=?,aspects=? WHERE id=?',
                       (comment, sentiment, json.dumps(aspects), row['id']))
            comments.append(comment)
        db.commit()
        return {'updated': len(targets), 'skipped': len(rows) - len(targets)}
    except Exception:
        db.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT/'instance/idfinder.sqlite')
    args = parser.parse_args()
    database = args.database.resolve()
    if not database.is_file():
        parser.error('Existing database not found; supply --database with the correct path.')
    backup = database.with_name(database.name+'.before-review-text-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.bak')
    with closing(sqlite3.connect(database.as_uri()+'?mode=rw',uri=True)) as db:
        with closing(sqlite3.connect(backup)) as dst:
            db.backup(dst)
        print(json.dumps(repair(db)))
    print('Backup:', backup.name)


if __name__ == '__main__':
    main()

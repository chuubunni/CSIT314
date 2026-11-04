"""Add fictional but realistic hiring/review history to existing accounts.

Run from the repository root: python seed_review_sample_data.py
Optional: --database path/to/database.sqlite
No accounts, passwords, portfolio projects or existing reviews are changed.
The script backs up the database first and records its own inserts so reruns
do not duplicate jobs. Historical dates never precede either user's account.
"""
import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random
import sqlite3

from idfinder.controller.review_text import analyse
from idfinder.services.sample_review_text import sample_comment

ROOT = Path(__file__).resolve().parent
PLACES = ('Bishan', 'Lentor', 'Tampines', 'Punggol', 'Toa Payoh', 'Bedok',
          'Sengkang', 'Queenstown', 'Bukit Batok', 'Woodlands', 'Pasir Ris')
TASKS = ('Space planning consultation', 'Kitchen layout review',
         'Material selection consultation', 'Lighting layout consultation',
         'Renovation planning consultation', 'Storage design consultation')
DETAILS = ('storage needs and daily routines', 'the kitchen workflow and ventilation',
           'easy-care materials within our budget', 'lighting for work and relaxation',
           'the renovation schedule and estimated costs', 'storage for a growing family')
COMMENTS = {
    5: (
        'The designer listened carefully and explained the trade-offs clearly. The proposal addressed {detail}.',
        'Excellent communication throughout. We received practical suggestions for {detail} and the drawings arrived on time.',
        'Very professional and patient with our questions. The revised layout made better use of the available space.',
        'We appreciated the clear budget breakdown and thoughtful recommendations. The final plan was easy to understand.',
    ),
    4: (
        'The advice on {detail} was helpful. One revision took a little longer than expected, but the designer kept us updated.',
        'Good ideas and a practical layout. We needed another meeting to clarify the material options before finalising.',
        'The consultation was useful and the designer respected our budget. Communication could have been slightly faster.',
    ),
    3: (
        'Some useful ideas for {detail}, but we had to follow up twice for the revised drawings.',
        'The proposal covered our main requirements. The initial cost estimate needed clarification and a second revision.',
        'The layout was workable, although a few preferences from our first meeting were missed.',
    ),
    2: (
        'The revised proposal arrived late and still missed our priorities for {detail}. Communication needs improvement.',
        'We had to chase updates several times. The suggestions were too general for the measurements we provided.',
    ),
    1: (
        'Repeated delays and poor communication made the process frustrating. The delivered proposal did not address {detail}.',
        'The agreed follow-up was missed and the final plan still contained the issues we had raised earlier.',
    ),
}
REPLIES = (
    'Thank you for sharing your feedback. We appreciate the opportunity to help with your home.',
    'Thank you for the detailed feedback. We will take these points into our next design review.',
    'We appreciate your comments and will improve how we communicate timelines and revisions.',
)


def parsed(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result.astimezone(timezone.utc).replace(tzinfo=None) if result.tzinfo else result
    except (TypeError, ValueError):
        return None


def stamp(value):
    return value.strftime('%Y-%m-%d %H:%M:%S')


def seed(connection, now=None):
    """Insert into the supplied connection only; return counts for this run."""
    now = (now or datetime.now(timezone.utc).replace(tzinfo=None)).replace(microsecond=0)
    year, month = now.year, now.month
    for _ in range(5):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    earliest = datetime(year, month, 1)
    connection.row_factory = sqlite3.Row
    designers = connection.execute(
        'SELECT u.id,u.created FROM designer d JOIN user u ON u.id=d.userID ORDER BY u.id').fetchall()
    customers = [(r['id'], parsed(r['created']) or now) for r in connection.execute(
        'SELECT u.id,u.created FROM customer c JOIN user u ON u.id=c.cust_id ORDER BY u.id')]
    if not designers or not customers:
        raise ValueError('Existing designer and customer accounts are required; no accounts were created.')
    existing_comments = [r['comment'] for r in connection.execute('SELECT comment FROM review')]
    counts = {'jobs': 0, 'completed_jobs': 0, 'reviews': 0, 'replies': 0}
    # C18: sample history supplies leaderboard experience and rating evidence.
    # All inserts, including the rerun markers, succeed or roll back together.
    with connection:
        connection.execute('''CREATE TABLE IF NOT EXISTS review_sample_seed_job (
            seed_key TEXT PRIMARY KEY, engagement_id INTEGER NOT NULL UNIQUE
                REFERENCES engagement(id) ON DELETE CASCADE)''')
        for designer in designers:
            rng = random.Random(314000 + designer['id'])
            start = max(earliest, parsed(designer['created']) or now)
            available = (now - start).total_seconds()
            if available < 2 * 86400:
                continue
            count = rng.randint(4, 16) if available >= 30 * 86400 else rng.randint(1, 3)
            quality = rng.uniform(3.1, 4.8)
            for i in range(count):
                key = f'review-history-v1:{designer["id"]}:{i}'
                if connection.execute('SELECT 1 FROM review_sample_seed_job WHERE seed_key=?', (key,)).fetchone():
                    continue
                created = start + timedelta(seconds=rng.uniform(0, available - 86400))
                eligible = [c for c in customers if c[1] <= created]
                if not eligible:
                    continue
                customer_id = rng.choice(eligible)[0]
                days_left = (now - created).total_seconds() / 86400
                status = rng.choices(['completed', 'declined', 'cancelled'], [80, 9, 11])[0]
                if days_left < 4:
                    status = rng.choice(['requested', 'ongoing', 'completed'])
                finished = min(created + timedelta(days=rng.uniform(1, 14)), now - timedelta(hours=1))
                if finished <= created:
                    continue
                task = rng.randrange(len(TASKS))
                title = f'{TASKS[task]} - {rng.choice(PLACES)}'
                updated = finished if status in ('completed', 'declined', 'cancelled') else created
                job = connection.execute('''INSERT INTO engagement
                    (customer_id,designer_id,title,message,status,created,updated,completed_at)
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (customer_id, designer['id'], title,
                     f'Please advise on {DETAILS[task]} and explain the available options.',
                     status, stamp(created), stamp(updated), stamp(finished) if status == 'completed' else None)).lastrowid
                connection.execute('INSERT INTO review_sample_seed_job VALUES (?,?)', (key, job))
                counts['jobs'] += 1
                counts['completed_jobs'] += status == 'completed'
                if status != 'completed' or rng.random() > 0.85:
                    continue
                rating = max(1, min(5, round(rng.gauss(quality, 0.85))))
                # C18: varied sample wording avoids flooding the copied-text review queue.
                comment = sample_comment(key, rating, task, title.split(" - ")[-1], existing_comments)
                existing_comments.append(comment)
                sentiment, aspects = analyse(comment)
                reviewed = min(finished + timedelta(days=rng.uniform(0.25, 7)), now)
                reply = rng.choice(REPLIES) if rng.random() < 0.6 and (now-reviewed).total_seconds() > 86400 else None
                replied = min(reviewed + timedelta(days=1), now) if reply else None
                connection.execute('''INSERT INTO review
                    (engagement_id,customer_id,designer_id,rating,comment,sentiment,aspects,
                     created,updated,designer_reply,replied_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                    (job, customer_id, designer['id'], rating, comment, sentiment,
                     json.dumps(aspects), stamp(reviewed), stamp(replied or reviewed),
                     reply, stamp(replied) if replied else None))
                counts['reviews'] += 1
                counts['replies'] += bool(reply)
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT / 'instance' / 'idfinder.sqlite')
    args = parser.parse_args()
    database = args.database.resolve()
    if not database.is_file():
        parser.error('Database not found. Supply the existing database path with --database.')
    connection = sqlite3.connect(database.as_uri() + '?mode=rw', uri=True)
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        backup = database.with_name(database.name + '.before-review-samples-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
        with closing(sqlite3.connect(backup)) as target:
            connection.backup(target)
        connection.executescript((ROOT / 'idfinder' / 'review_schema.sql').read_text(encoding='utf-8'))
        counts = seed(connection)
        print('Added:', json.dumps(counts))
        print('A database backup was saved beside the original file.')
        print('Sample history uses existing accounts; accounts and portfolio projects were not changed.')
    finally:
        connection.close()


if __name__ == '__main__':
    main()

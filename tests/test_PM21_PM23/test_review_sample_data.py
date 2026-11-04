from datetime import datetime

from idfinder.db import get_db
from seed_review_sample_data import seed


def test_sample_history_is_repeatable_and_preserves_existing_data(make):
    designer = make.user('designer', created='2026-05-01 09:00:00')
    customer = make.user(created='2026-05-01 09:00:00')
    project = make.project(designer)
    old_job = make.engagement(customer, designer)
    old_review = make.review(old_job, comment='Existing review')
    db = get_db()
    accounts = [tuple(r) for r in db.execute('SELECT * FROM user ORDER BY id')]
    projects = [tuple(r) for r in db.execute('SELECT * FROM idp ORDER BY id')]
    old = tuple(db.execute('SELECT * FROM review WHERE id=?', (old_review,)).fetchone())
    counts = seed(db, datetime(2026, 11, 3, 12))
    assert counts['jobs'] > 0 and counts['reviews'] > 0
    assert all(v == 0 for v in seed(db, datetime(2026, 11, 3, 12)).values())
    assert [tuple(r) for r in db.execute('SELECT * FROM user ORDER BY id')] == accounts
    assert [tuple(r) for r in db.execute('SELECT * FROM idp ORDER BY id')] == projects
    assert tuple(db.execute('SELECT * FROM review WHERE id=?', (old_review,)).fetchone()) == old
    assert db.execute('''SELECT COUNT(*) FROM review r JOIN engagement e ON e.id=r.engagement_id
        WHERE e.status!='completed' OR r.created<e.completed_at''').fetchone()[0] == 0
    assert db.execute('''SELECT COUNT(*) FROM engagement e
        JOIN user c ON c.id=e.customer_id JOIN user d ON d.id=e.designer_id
        WHERE e.created<c.created OR e.created<d.created''').fetchone()[0] == 0


def test_new_accounts_are_not_given_impossible_past_jobs(make):
    make.user('designer', created='2026-11-03 10:00:00')
    make.user(created='2026-11-03 10:00:00')
    assert seed(get_db(), datetime(2026, 11, 3, 12))['jobs'] == 0

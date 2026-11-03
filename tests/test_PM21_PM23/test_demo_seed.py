"""The optional demo-data seeder: idempotent, removable, and it never touches real rows."""
import sqlite3

import pytest

from idfinder import create_app
from idfinder.db import init_db
from idfinder.demo_seed import DemoSeeder


@pytest.fixture
def paths(tmp_path):
    db = str(tmp_path / 't.sqlite')
    app = create_app({'TESTING': True, 'DATABASE': db, 'UPLOAD_FOLDER': str(tmp_path / 'up'), 'SECRET_KEY': 'x'})
    with app.app_context():
        init_db()
    return db, str(tmp_path / 'up')


def counts(db):
    c = sqlite3.connect(db)
    return {t: c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
            for t in ('user', 'idp', 'idp_view', 'favourite_idp', 'engagement', 'review')}


def test_seed_adds_data_and_is_idempotent(paths):
    db, up = paths
    first = DemoSeeder(db, up, with_images=False).seed()
    assert first
    before = counts(db)
    assert before['user'] >= 150 and before['idp_view'] >= 4000 and before['review'] > 50
    assert DemoSeeder(db, up, with_images=False).seed() is None
    assert counts(db) == before


def test_seed_covers_every_job_status_and_the_moderation_cases(paths):
    db, up = paths
    DemoSeeder(db, up, with_images=False).seed()
    c = sqlite3.connect(db)
    assert {r[0] for r in c.execute('SELECT DISTINCT status FROM engagement')} == \
        {'requested', 'ongoing', 'completed', 'declined', 'cancelled'}
    assert c.execute("SELECT COUNT(*) FROM review WHERE status = 'hidden'").fetchone()[0] >= 1
    assert c.execute('SELECT COUNT(*) FROM review WHERE reported_reason IS NOT NULL').fetchone()[0] >= 1
    assert c.execute("SELECT COUNT(*) FROM review r JOIN engagement e ON e.id = r.engagement_id WHERE e.status != 'completed'").fetchone()[0] == 0


def test_clean_removes_only_demo_rows(paths):
    db, up = paths
    c = sqlite3.connect(db)
    c.execute("INSERT INTO user (name,password,email,phone,Usertype) VALUES ('Real','x','real@school.edu','91234567','customer')")
    c.commit(); c.close()
    seeder = DemoSeeder(db, up, with_images=False)
    seeder.seed()
    seeder.clean()
    after = counts(db)
    assert after['user'] == 1 and after['idp'] == 0 and after['idp_view'] == 0 and after['review'] == 0 and after['engagement'] == 0
    DemoSeeder(db, up, with_images=False).seed()                    # can be seeded again after a clean
    assert counts(db)['user'] >= 150


def test_use_existing_keeps_designers_and_projects(paths):
    db, up = paths
    c = sqlite3.connect(db)
    c.execute("INSERT INTO user (name,password,email,phone,Usertype) VALUES ('Real Designer','x','rd@school.edu','91234567','designer')")
    uid = c.execute("SELECT id FROM user WHERE email='rd@school.edu'").fetchone()[0]
    cid = c.execute("INSERT INTO company (companyName, companyLine, companyEmail) VALUES ('Real Co','L1','r@co.edu')").lastrowid
    c.execute('INSERT INTO designer (userID, companyID) VALUES (?, ?)', (uid, cid))
    c.execute("INSERT INTO category (name, active) VALUES ('Modern', 1)")
    for i in range(3):
        c.execute("INSERT INTO idp (designer_id,title,description,property_type,price,status,created) VALUES (?,?,?,?,?,?,?)",
                  (uid, f'Real project {i}', 'd', 'HDB', 10000, 'completed', '2026-09-01 10:00:00'))
    c.commit(); c.close()
    DemoSeeder(db, up, use_existing=True).seed()
    c = sqlite3.connect(db)
    assert c.execute('SELECT COUNT(*) FROM idp').fetchone()[0] == 3                       # no demo projects added
    assert c.execute("SELECT COUNT(*) FROM user WHERE Usertype='designer'").fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM category").fetchone()[0] == 1                  # no demo categories added
    assert c.execute('SELECT COUNT(*) FROM idp_view').fetchone()[0] > 100
    assert c.execute('SELECT COUNT(*) FROM engagement WHERE designer_id = ?', (uid,)).fetchone()[0] >= 1

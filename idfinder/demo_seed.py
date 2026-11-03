"""Demo / presentation data: users, projects, views, favourites, hiring jobs and reviews.

It exists so the graphs, the designer ratings and the leaderboard have something to show.
Everything it creates is marked (emails end with @demo.test, company lines start with DEMO-),
so clean() removes only demo rows and never touches your teammates' real test accounts.

HOW TO USE (pick one)
  1. By hand:      python seed_demo_data.py            add the data (does nothing if already there)
                   python seed_demo_data.py --clean    remove it again
  2. On start-up:  set IDFINDER_DEMO_DATA=1 before `flask --app idfinder run`  (see __init__.py)
  3. From code:    DemoSeeder(db_path).seed()

Log in as the demo platform manager:  manager@demo.test / Demo1234!
(designers: designer1@demo.test ...  customers: customer1@demo.test ...  same password)

What the data is designed to show (Ctrl+F "SEED"):
  * activity grows over 90 days, is busier on weekends and in the evening, and has one spike day
    (so the forecast, moving average, heatmap and anomaly marker all have something to find)
  * some design categories get lots of views but few shortlists (the bubble chart)
  * designers of different quality: excellent, average, poor, and brand new with no reviews
  * a ring of near-identical 5-star reviews, one reported review and one hidden review for the
    manager's moderation page
"""
import json
import math
import os
import random
import sqlite3
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

from idfinder.controller import review_text

PASSWORD = 'Demo1234!'
BASE = os.path.dirname(__file__)
SCHEMA_PATH = os.path.join(BASE, 'schema.sql')
DEFAULT_UPLOADS = os.path.join(BASE, 'static', 'uploads')

CATEGORIES = {
    'Modern': ['Sleek', 'Urban', 'Glass-and-Steel'], 'Minimalist': ['Clean-Line', 'Pared-Back', 'Calm'],
    'Scandinavian': ['Nordic', 'Light Oak', 'Hygge'], 'Industrial': ['Exposed Brick', 'Loft-Style', 'Concrete'],
    'Contemporary': ['Bold', 'Refined', 'Open-Plan'], 'Japandi': ['Zen', 'Warm Wood', 'Muji-Inspired'],
    'Classic': ['Timeless', 'Elegant', 'Heritage'], 'Rustic': ['Cosy', 'Natural Timber', 'Farmhouse'],
    'Tropical': ['Resort-Style', 'Green', 'Breezy'], 'Luxury': ['Marble', 'Statement', 'Hotel-Style'],
}
# SEED: how likely a viewer is to shortlist, per category (some are looked at a lot but rarely saved)
CONVERSION = {'Traditional': 0.07, 'Coastal': 0.15, 'Modern': 0.05, 'Minimalist': 0.17, 'Scandinavian': 0.20, 'Industrial': 0.06, 'Contemporary': 0.10,
              'Japandi': 0.19, 'Classic': 0.07, 'Rustic': 0.12, 'Tropical': 0.15, 'Luxury': 0.08}
CATEGORY_APPEAL = {'Traditional': 1.6, 'Coastal': 0.9, 'Modern': 2.4, 'Minimalist': 1.2, 'Scandinavian': 1.4, 'Industrial': 1.9, 'Contemporary': 1.1,
                   'Japandi': 1.0, 'Classic': 1.6, 'Rustic': 0.7, 'Tropical': 0.9, 'Luxury': 1.3}
ROOMS = ['Living Room', 'Kitchen', 'Master Bedroom', 'Full Home', 'Study', 'Bathroom', 'Dining Area']
FIRST = ['Aiden', 'Mei', 'Priya', 'Hao', 'Sofia', 'Daniel', 'Nur', 'Jun', 'Aisha', 'Ethan', 'Wei', 'Grace',
         'Raj', 'Chloe', 'Zhi', 'Hana', 'Kai', 'Lena', 'Omar', 'Yuki', 'Marcus', 'Elena', 'Farid', 'Isabelle']
LAST = ['Tan', 'Lim', 'Ng', 'Wong', 'Lee', 'Chua', 'Koh', 'Goh', 'Teo', 'Ong', 'Singh', 'Rahman', 'Chen', 'Ho', 'Yeo']
COMPANIES = ['Nest & Grain', 'Studio Merlion', 'Lumen Interiors', 'Pebble Design', 'Rooted Spaces', 'Oak & Ivory']
JOBS = ['Full renovation of my 4-room HDB', 'Living room refresh', 'Kitchen makeover', 'Master bedroom redesign',
        'BTO renovation package', 'Condo interior styling', 'Study room and storage', 'Bathroom upgrade',
        'Open-plan living and dining', 'Landed house revamp']
GROUPS = ['Kitchens', 'Bedrooms', 'Featured', 'Budget Friendly']

# SEED: review sentences. Each one talks about one topic, so the topic tags have something to find.
POSITIVE = {
    'communication': ['{d} was very responsive and kept me informed at every step.', 'Great communication, replies came within the hour.',
                      'Always listened to what we wanted and explained every option clearly.'],
    'timeliness': ['Everything was finished on time, ahead of the schedule.', 'Prompt and punctual, no delays at all.'],
    'budget': ['Stayed within our budget and the price was fair for the quality.', 'Clear quote with no hidden fees, great value.'],
    'creativity': ['Such creative ideas, the layout feels unique and so us.', 'Loved the concept and the stunning style choices.'],
    'quality': ['The quality of the finish is excellent and the craftsmanship is neat.', 'Beautiful result, great attention to detail.'],
    'professionalism': ['Very professional, honest and reliable throughout.', 'Courteous team, patient with all our changes.'],
}
NEGATIVE = {
    'communication': ['Poor communication, messages were ignored for days.', 'Hard to reach and slow to reply, I had to chase for updates.'],
    'timeliness': ['The project was badly delayed by weeks.', 'Always late and the schedule kept slipping.'],
    'budget': ['The final cost was far above the quote, with hidden fees.', 'Overpriced for what we got.'],
    'creativity': ['The ideas felt generic and not what we asked for.', 'No real concept, the layout was uninspired.'],
    'quality': ['There were many defects and mistakes in the finish.', 'The workmanship was sloppy and messy.'],
    'professionalism': ['Rude and pushy, a very unprofessional attitude.', 'Not reliable at all, would not trust again.'],
}
MIXED = ['It was okay overall, nothing special.', 'Decent result but there were some problems along the way.',
         'Average experience, some good moments and some not so good.']


def _stamp(moment):
    return moment.strftime('%Y-%m-%d %H:%M:%S')            # the text SQLite's CURRENT_TIMESTAMP writes


class DemoSeeder:
    def __init__(self, db_path, upload_folder=None, designers=24, customers=150, projects=120,
                 days=90, with_images=True, scale=1.0, use_existing=False):
        self.db_path = db_path
        self.upload_folder = upload_folder or DEFAULT_UPLOADS
        self.designers, self.customers, self.projects = designers, customers, projects
        self.days, self.with_images, self.scale = days, with_images, scale
        # use_existing=True: build ON TOP of a database that already has designers, projects and pictures
        # (for example a teammate's data). Nothing is created for those; only customers, views, shortlists,
        # jobs and reviews are added. (Use a COPY of the database: --clean cannot undo this mode fully.)
        self.use_existing = use_existing

    # ------------------------------------------------------------------ helpers
    def _connect(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
        return db

    def _make_image(self, project_id, colour_seed):
        """A small coloured placeholder picture (needs Pillow; skipped quietly if missing)."""
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return None
        os.makedirs(self.upload_folder, exist_ok=True)
        name = f'demo_{project_id}.jpg'
        rng = random.Random(colour_seed)
        top = tuple(rng.randint(90, 230) for _ in range(3))
        bottom = tuple(max(0, c - 70) for c in top)
        image = Image.new('RGB', (480, 320))
        draw = ImageDraw.Draw(image)
        for y in range(320):
            mix = y / 319
            draw.line([(0, y), (480, y)], fill=tuple(int(top[i] * (1 - mix) + bottom[i] * mix) for i in range(3)))
        draw.rectangle([60, 200, 420, 260], fill=tuple(max(0, c - 40) for c in bottom))
        draw.rectangle([200, 60, 280, 150], fill=tuple(min(255, c + 40) for c in top))
        image.save(os.path.join(self.upload_folder, name), quality=80)
        return name

    # ------------------------------------------------------------------ clean
    def clean(self):
        """Removes every demo row (and the pictures this script made). Returns how many users went."""
        db = self._connect()
        try:
            users = [r[0] for r in db.execute("SELECT id FROM user WHERE email LIKE '%@demo.test'")]
            if not users:
                return 0
            marks = ','.join('?' * len(users))
            projects = [r[0] for r in db.execute(f'SELECT id FROM idp WHERE designer_id IN ({marks})', users)]
            pmarks = ','.join('?' * len(projects)) or 'NULL'
            for row in db.execute(f'SELECT link FROM idp_media WHERE idp_id IN ({pmarks})', projects).fetchall():
                if row['link'].startswith('demo_'):
                    path = os.path.join(self.upload_folder, row['link'])
                    if os.path.exists(path):
                        os.remove(path)
            if db.execute("SELECT 1 FROM sqlite_master WHERE name = 'engagement'").fetchone():
                db.execute(f'DELETE FROM review WHERE customer_id IN ({marks}) OR designer_id IN ({marks})', users + users)
                db.execute(f'DELETE FROM engagement WHERE customer_id IN ({marks}) OR designer_id IN ({marks})', users + users)
            db.execute(f'DELETE FROM idp_view WHERE idp_id IN ({pmarks})', projects)
            db.execute(f'DELETE FROM favourite_idp WHERE idp_id IN ({pmarks}) OR customer_id IN ({marks})', projects + users)
            db.execute(f'DELETE FROM favourite_designer WHERE designer_id IN ({marks}) OR customer_id IN ({marks})', users + users)
            db.execute(f'DELETE FROM idp_group_member WHERE idp_id IN ({pmarks})', projects)
            db.execute(f'DELETE FROM idp_group WHERE designer_id IN ({marks})', users)
            db.execute(f'DELETE FROM idp_category WHERE idp_id IN ({pmarks})', projects)
            db.execute(f'DELETE FROM idp_media WHERE idp_id IN ({pmarks})', projects)
            db.execute(f'DELETE FROM idp WHERE id IN ({pmarks})', projects)
            for table, column in (('designer', 'userID'), ('customer', 'cust_id'), ('platform', 'managerID')):
                db.execute(f'DELETE FROM {table} WHERE {column} IN ({marks})', users)
            db.execute(f'DELETE FROM user WHERE id IN ({marks})', users)
            db.execute("DELETE FROM company WHERE companyLine LIKE 'DEMO-%'")
            db.commit()
            return len(users)
        finally:
            db.close()

    # ------------------------------------------------------------------ seed
    def seed(self):
        """Adds the demo data. Returns a short summary, or None if it was already there."""
        db = self._connect()
        try:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'idp_view'").fetchone():
                with open(SCHEMA_PATH, encoding='utf-8') as f:          # first run, before init-db
                    db.executescript(f.read())
            from idfinder.entities import review_schema
            review_schema.ensure(db)
            if db.execute("SELECT 1 FROM user WHERE email = 'manager@demo.test'").fetchone():
                return None
            return self._seed(db)
        finally:
            db.close()

    def _seed(self, db):
        rng = random.Random(314)                                       # fixed seed: same data every time
        now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
        start = (now - timedelta(days=self.days)).replace(hour=0, minute=0, second=0)   # midnight UTC, so hours below are exact
        password_hash = generate_password_hash(PASSWORD)

        def at(day_fraction):                                          # 0 = start of window, 1 = now
            return start + timedelta(seconds=int(self.days * 86400 * day_fraction))

        def add_user(name, email, kind, created):
            return db.execute(
                'INSERT INTO user (name, password, email, phone, Usertype, created) VALUES (?,?,?,?,?,?)',
                (name, password_hash, email, f'9{rng.randint(1000000, 9999999)}', kind, _stamp(created))).lastrowid

        def person():
            return f'{rng.choice(FIRST)} {rng.choice(LAST)}'

        # ---- categories, housing options (from the schema), companies
        category_ids = {}
        if self.use_existing:
            category_ids = {r['name']: r['id'] for r in db.execute('SELECT id, name FROM category WHERE active = 1 ORDER BY id')}
        else:
            for name in CATEGORIES:
                row = db.execute('SELECT id FROM category WHERE name = ?', (name,)).fetchone()
                category_ids[name] = row[0] if row else db.execute(
                    'INSERT INTO category (name, active) VALUES (?, 1)', (name,)).lastrowid
        names = list(category_ids)
        appeal = [CATEGORY_APPEAL.get(n, 1.0) for n in names]
        types = [r['code'] for r in db.execute('SELECT code FROM property_type ORDER BY id')]
        subtypes = {}
        for row in db.execute('SELECT s.id, t.code FROM property_subtype s JOIN property_type t ON t.id = s.property_type_id'):
            subtypes.setdefault(row['code'], []).append(row['id'])

        manager = add_user('Demo Manager', 'manager@demo.test', 'manager', start)
        db.execute('INSERT INTO platform (managerID) VALUES (?)', (manager,))
        companies = [] if self.use_existing else [db.execute('INSERT INTO company (companyName, companyLine, companyEmail) VALUES (?,?,?)',
                                (name, f'DEMO-{n}', f'hello@demo{n}.test')).lastrowid
                     for n, name in enumerate(COMPANIES, 1)]

        # ---- designers: quality decides how customers rate them (SEED: excellent / average / poor / new)
        designers, quality = {}, {}
        if self.use_existing:
            # the designers that are already in the database, in id order; the last two are "brand new"
            rows = db.execute("SELECT id, created FROM user WHERE Usertype = 'designer' AND email NOT LIKE '%@demo.test' ORDER BY id").fetchall()
            cycle = ['excellent', 'good', 'average', 'good', 'poor', 'average', 'excellent', 'good', 'average', 'poor', 'excellent']
            for n, row in enumerate(rows):
                has_projects = db.execute('SELECT 1 FROM idp WHERE designer_id = ?', (row['id'],)).fetchone()
                profile = 'new' if (n >= len(rows) - 2 and len(rows) > 6) or not has_projects else cycle[n % len(cycle)]
                joined = datetime.strptime(row['created'], '%Y-%m-%d %H:%M:%S') if row['created'] else start
                designers[row['id']] = min(joined, start + timedelta(days=1)) if profile != 'new' else at(0.93)
                quality[row['id']] = profile
        else:
            profiles = (['excellent'] * 6 + ['good'] * 7 + ['average'] * 6 + ['poor'] * 3 + ['new'] * 2)
            profiles = (profiles * 2)[:self.designers]
            for n, profile in enumerate(profiles, 1):
                joined = at(rng.uniform(0.0, 0.25)) if profile != 'new' else at(rng.uniform(0.9, 0.97))
                uid = add_user(person(), f'designer{n}@demo.test', 'designer', joined)
                db.execute('INSERT INTO designer (userID, companyID) VALUES (?, ?)', (uid, rng.choice(companies)))
                designers[uid], quality[uid] = joined, profile

        # ---- customers: sign-ups grow over time (SEED: a rising "new users" curve)
        customers = {}
        for n in range(1, self.customers + 1):
            joined = at(rng.random() ** 0.7 * 0.97)
            uid = add_user(person(), f'customer{n}@demo.test', 'customer', joined)
            db.execute('INSERT INTO customer (cust_id, current_property_type, received_keys) VALUES (?,?,?)',
                       (uid, rng.choice(types), rng.choice((0, 1, None))))
            customers[uid] = joined
        cids = list(customers)

        # ---- projects, spread over the window; the most "appealing" categories get most projects
        projects, project_category, popularity, images = {}, {}, {}, 0
        active_designers = [d for d in designers if quality[d] != 'new']
        if self.use_existing:
            # the projects (and pictures) that are already there; views and shortlists will be added to them
            for row in db.execute('SELECT i.id, i.created, c.name FROM idp i LEFT JOIN idp_category ic ON ic.idp_id = i.id '
                                  'LEFT JOIN category c ON c.id = ic.category_id GROUP BY i.id ORDER BY i.id'):
                pid = row['id']
                projects[pid] = datetime.strptime(row['created'], '%Y-%m-%d %H:%M:%S') if row['created'] else start
                project_category[pid] = row['name'] if row['name'] in category_ids else names[0]
                popularity[pid] = math.exp(rng.gauss(0, 0.8)) * CATEGORY_APPEAL.get(project_category[pid], 1.0)
        else:
            for n in range(1, self.projects + 1):
                created = at(rng.uniform(0.02, 0.97))
                able = [d for d in active_designers if designers[d] <= created] or active_designers
                designer_id = rng.choice(able)
                chosen = sorted(set(rng.choices(names, weights=appeal, k=rng.randint(1, 2))))
                ptype = rng.choice(types)
                subtype = rng.choice(subtypes[ptype]) if subtypes.get(ptype) else None
                title = f'{rng.choice(CATEGORIES[chosen[0]])} {chosen[0]} {rng.choice(ROOMS)}'
                pid = db.execute(
                    'INSERT INTO idp (designer_id, title, description, property_type, property_subtype_id, price, status, created)'
                    ' VALUES (?,?,?,?,?,?,?,?)',
                    (designer_id, title, f'A {chosen[0].lower()} interior design project (demo data).', ptype, subtype,
                     rng.randint(8, 120) * 1000, rng.choice(('ongoing', 'completed')), _stamp(created))).lastrowid
                projects[pid] = created
                project_category[pid] = chosen[0]
                popularity[pid] = math.exp(rng.gauss(0, 0.8)) * CATEGORY_APPEAL.get(chosen[0], 1.0)
                for name in chosen:
                    db.execute('INSERT INTO idp_category (idp_id, category_id) VALUES (?, ?)', (pid, category_ids[name]))
                if self.with_images:
                    link = self._make_image(pid, n)
                    if link:
                        db.execute('INSERT INTO idp_media (idp_id, link, created) VALUES (?,?,?)', (pid, link, _stamp(created)))
                        images += 1
        project_ids = sorted(projects, key=projects.get)

        # ---- views and shortlists, day by day (SEED: growth + weekend lift + evening peak + one spike day)
        spike_day = self.days - 11                                    # a day about 10 days ago
        hour_weights = [1, 1, 1, 1, 1, 2, 3, 4, 5, 5, 5, 6, 6, 6, 6, 6, 7, 8, 9, 10, 10, 9, 6, 3]   # SINGAPORE hours: evening peak
        views = favourites = 0
        favourite_pairs = set()
        for day in range(self.days):
            date = start + timedelta(days=day)
            growth = 0.55 + 0.9 * day / self.days
            weekend = 1.35 if date.weekday() >= 5 else 1.0
            expected = 42 * growth * weekend * self.scale * (3.2 if day == spike_day else 1.0)
            count = max(0, int(rng.gauss(expected, expected ** 0.5 * 1.4)))
            existing = [p for p in project_ids if projects[p] <= date + timedelta(days=1)]
            if not existing:
                continue
            weights = [popularity[p] for p in existing]
            for _ in range(count):
                pid = rng.choices(existing, weights=weights)[0]
                # the weights above are Singapore clock hours; the database stores UTC (Singapore = UTC+8)
                local_hour = rng.choices(range(24), weights=hour_weights)[0]
                moment = date + timedelta(hours=local_hour - 8, minutes=rng.randrange(60), seconds=rng.randrange(60))
                if moment > now or moment < projects[pid]:
                    continue
                viewer = rng.choice(cids) if rng.random() < 0.55 else None
                if viewer is not None and customers[viewer] > moment:
                    viewer = None
                db.execute('INSERT INTO idp_view (idp_id, viewer_id, viewed_at) VALUES (?,?,?)', (pid, viewer, _stamp(moment)))
                views += 1
                if viewer is not None and (viewer, pid) not in favourite_pairs and rng.random() < CONVERSION.get(project_category[pid], 0.1) * 2:
                    later = min(now, moment + timedelta(minutes=rng.randint(1, 90)))
                    favourite_pairs.add((viewer, pid))
                    db.execute('INSERT INTO favourite_idp (customer_id, idp_id, created) VALUES (?,?,?)', (viewer, pid, _stamp(later)))
                    favourites += 1

        # ---- favourite designers and groups
        dids = list(designers)
        fav_designers = set()
        for _ in range(self.customers * 2):
            fav_designers.add((rng.choice(cids), rng.choice(dids)))
        for cust, des in fav_designers:
            db.execute('INSERT INTO favourite_designer (customer_id, designer_id, created) VALUES (?,?,?)',
                       (cust, des, _stamp(at(rng.uniform(0.1, 0.99)))))
        group_count = 0
        own = {}
        for pid, designer_id in db.execute('SELECT id, designer_id FROM idp WHERE designer_id IN (%s)' % ','.join('?' * len(dids)), dids):
            own.setdefault(designer_id, []).append(pid)
        for designer_id, mine in own.items():
            if len(mine) >= 2:
                for name in rng.sample(GROUPS, k=2):
                    gid = db.execute('INSERT INTO idp_group (designer_id, name) VALUES (?, ?)', (designer_id, name)).lastrowid
                    group_count += 1
                    for pid in rng.sample(mine, k=min(len(mine), rng.randint(2, 4))):
                        db.execute('INSERT INTO idp_group_member (group_id, idp_id) VALUES (?, ?)', (gid, pid))

        # ---- hiring jobs and reviews (SEED: ratings follow each designer's quality)
        rating_weights = {'excellent': [0, 0, 3, 22, 75], 'good': [1, 3, 10, 40, 46], 'average': [5, 12, 33, 35, 15],
                          'poor': [30, 30, 22, 12, 6], 'new': [0, 0, 20, 40, 40]}
        aspect_names = list(POSITIVE)
        job_count = review_count = 0
        review_rows = []

        def sentence_set(rating, designer_name):
            if rating >= 4:
                pool, k = POSITIVE, rng.choice((1, 2, 2, 3))
            elif rating <= 2:
                pool, k = NEGATIVE, rng.choice((1, 2, 2))
            else:
                return rng.choice(MIXED) + ' ' + rng.choice(POSITIVE[rng.choice(aspect_names)]).format(d=designer_name.split()[0])
            return ' '.join(rng.choice(pool[a]).format(d=designer_name.split()[0]) for a in rng.sample(aspect_names, k))

        for designer_id, profile in quality.items():
            jobs_for_designer = {'excellent': 14, 'good': 10, 'average': 8, 'poor': 6, 'new': 0}[profile]
            designer_name = db.execute('SELECT name FROM user WHERE id = ?', (designer_id,)).fetchone()[0]
            for _ in range(int(jobs_for_designer * self.scale) + rng.randint(0, 2)):
                customer = rng.choice(cids)
                roll = rng.random()
                status = ('completed' if roll < 0.72 else 'ongoing' if roll < 0.82 else 'requested' if roll < 0.90
                          else 'declined' if roll < 0.96 else 'cancelled')
                earliest = max(customers[customer], designers[designer_id]) + timedelta(hours=1)
                completed_at = None
                if status == 'completed':
                    # HARD PART: plan the job BACKWARDS from when it finished, so jobs (and their reviews)
                    # are spread over the whole window instead of piling up on "today".
                    completed_at = at(rng.uniform(0.12, 0.99)) - timedelta(hours=3)
                    created = max(earliest, completed_at - timedelta(days=rng.uniform(8, 45)))
                    completed_at = min(max(completed_at, created + timedelta(days=1)), now - timedelta(hours=3))
                    created = min(created, completed_at - timedelta(hours=1))
                else:
                    created = min(max(earliest, at(rng.uniform(0.5, 0.99))), now - timedelta(hours=1))
                project = rng.choice(own.get(designer_id, [None]))
                job = db.execute(
                    'INSERT INTO engagement (customer_id, designer_id, idp_id, title, message, status, created, updated, completed_at)'
                    ' VALUES (?,?,?,?,?,?,?,?,?)',
                    (customer, designer_id, project, rng.choice(JOBS), '', status, _stamp(created),
                     _stamp(completed_at or created), _stamp(completed_at) if completed_at else None)).lastrowid
                job_count += 1
                if status == 'completed' and rng.random() < 0.8:
                    rating = rng.choices([1, 2, 3, 4, 5], weights=rating_weights[profile])[0]
                    comment = sentence_set(rating, designer_name) if rng.random() < 0.9 else ''
                    reviewed_at = min(now - timedelta(minutes=5), completed_at + timedelta(days=rng.uniform(0.2, 12)))
                    review_rows.append((job, customer, designer_id, rating, comment, reviewed_at))

        # ---- SEED: things for the moderation page to catch
        ring_designer = next((d for d, q in quality.items() if q == 'average'), next(iter(quality)))
        ring_text = 'Absolutely the best designer in Singapore, highly recommend, five stars for the whole team!'
        ring_time = now - timedelta(days=6, hours=2)
        for n in range(4):
            joined = ring_time - timedelta(hours=rng.uniform(1, 5))
            uid = add_user(person(), f'ringcustomer{n + 1}@demo.test', 'customer', joined)
            db.execute('INSERT INTO customer (cust_id, current_property_type, received_keys) VALUES (?,?,?)', (uid, 'HDB', 1))
            job = db.execute(
                'INSERT INTO engagement (customer_id, designer_id, title, status, created, updated, completed_at)'
                " VALUES (?,?,?,'completed',?,?,?)",
                (uid, ring_designer, 'Quick job', _stamp(joined + timedelta(minutes=10)), _stamp(joined + timedelta(minutes=40)),
                 _stamp(joined + timedelta(minutes=40)))).lastrowid
            review_rows.append((job, uid, ring_designer, 5, ring_text, ring_time + timedelta(minutes=25 * n)))

        flagged = {}
        for job, customer, designer_id, rating, comment, reviewed_at in review_rows:
            sentiment, aspects = review_text.analyse(comment)
            review_id = db.execute(
                'INSERT INTO review (engagement_id, customer_id, designer_id, rating, comment, sentiment, aspects, created, updated)'
                ' VALUES (?,?,?,?,?,?,?,?,?)',
                (job, customer, designer_id, rating, comment, sentiment, json.dumps(aspects),
                 _stamp(reviewed_at), _stamp(reviewed_at))).lastrowid
            review_count += 1
            flagged.setdefault(designer_id, []).append((review_id, rating))
        # one review where stars and words disagree, one reported by its designer, one hidden by the manager
        low = db.execute("SELECT id FROM review WHERE comment != '' AND rating <= 2 ORDER BY id LIMIT 3").fetchall()
        if low:
            db.execute('UPDATE review SET rating = 5 WHERE id = ?', (low[0][0],))              # 5 stars, angry words
        if len(low) > 1:
            db.execute("UPDATE review SET reported_reason = 'I never worked with this customer', reported_at = ? WHERE id = ?",
                       (_stamp(now - timedelta(days=1)), low[1][0]))
        if len(low) > 2:
            db.execute("UPDATE review SET status = 'hidden', hidden_reason = 'Abusive language', moderated_at = ? WHERE id = ?",
                       (_stamp(now - timedelta(days=2)), low[2][0]))
        # designers reply to a share of the good reviews
        for row in db.execute("SELECT id FROM review WHERE rating >= 4 AND comment != '' AND status = 'visible'").fetchall():
            if rng.random() < 0.4:
                db.execute("UPDATE review SET designer_reply = ?, replied_at = created WHERE id = ?",
                           (rng.choice(['Thank you so much, it was a pleasure working with you!', 'Glad you love the result!',
                                        'Thanks for the kind words, enjoy your new home.']), row[0]))
        db.commit()
        return (f'Demo data added: {len(designers)} designers, {self.customers + 4} customers, {len(projects)} projects '
                f'({images} pictures), {views} views, {favourites} favourites, {len(fav_designers)} favourite designers, '
                f'{group_count} groups, {job_count + 4} jobs, {review_count} reviews. '
                f'Manager login: manager@demo.test / {PASSWORD}')

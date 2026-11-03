"""Adds MORE demo data to a database that already has demo data: new customers, designers and projects.

    python seed_demo_data.py --db copy.sqlite --extend                       # 45 customers, 137 designers, 200 projects
    python seed_demo_data.py --db copy.sqlite --extend --new-designers 50 --new-customers 10 --new-projects 80

How it follows the existing projects: titles, descriptions, housing types, estates and the pictures are copied
from the pattern of the projects that are already in the database. Every new project gets the picture of its
design category, exactly like the existing ones. Everything it adds is marked (emails start with `newdesigner` /
`newcustomer` and end with @demo.test, company lines start with DEMO-), so `--clean` still removes it.
Running it a second time does nothing.
"""
import json
import math
import random
import re
import sqlite3
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

from idfinder.controller import review_text
from idfinder.demo_seed import (
    CONVERSION, CATEGORY_APPEAL, FIRST, LAST, JOBS, MIXED, NEGATIVE, PASSWORD, POSITIVE, _stamp)

MORE_FIRST = ['Jia', 'Wen', 'Siti', 'Arjun', 'Beatrice', 'Darren', 'Eunice', 'Faith', 'Gavin', 'Hui', 'Irfan', 'Jasmine',
              'Kelvin', 'Li', 'Mohan', 'Natalie', 'Owen', 'Pei', 'Qi', 'Ravi', 'Sharon', 'Timothy', 'Uma', 'Vincent',
              'Xin', 'Yan', 'Zara', 'Amir', 'Bryan', 'Cheryl']
MORE_LAST = ['Tay', 'Sim', 'Foo', 'Lau', 'Quek', 'Ang', 'Phua', 'Tham', 'Kumar', 'Nair', 'Abdullah', 'Ismail', 'Lai', 'Toh', 'Soh']

# Extra title styles per design category (the first one of each is the style already used in the database).
# Same idea as the existing titles: "<style> at <estate>".
TITLE_STYLES = {
    'Modern': ['Oak and Light', 'Clean Slate', 'Glass and Grain', 'Urban Pulse'],
    'Minimalist': ['Quiet Corners', 'Pure Lines', 'White Space', 'Less is Home'],
    'Scandinavian': ['Nordic Haven', 'Birch and Linen', 'Hygge House', 'Frost and Fir'],
    'Industrial': ['Brick and Steel', 'Concrete Loft', 'Iron and Ember', 'The Warehouse Home'],
    'Contemporary': ['The Open House', 'Fresh Edge', 'Soft Geometry', 'Bright Spaces'],
    'Japandi': ['Soft Timber', 'Zen Living', 'Calm and Craft', 'Bamboo Quiet'],
    'Traditional': ['Heritage Lines', 'Teak and Tradition', 'Old World Charm', 'The Family Home'],
    'Luxury': ['Stone and Gold', 'Velvet and Marble', 'Grand Residence', 'Crown Interiors'],
    'Coastal': ['Coastal Calm', 'Sand and Sea', 'Breezy Living', 'Salt and Linen'],
    'Rustic': ['Earth and Grain', 'Barn and Brick', 'Warm Hearth', 'Timber Lodge'],
}
# Extra "The design combines..." sentences (the first one of each category is the one already in the database).
MIDDLES = {
    'Modern': ['The design combines oak cabinetry, a slim stone feature wall and layered lighting to create an open living area with concealed storage and a practical dining nook.',
               'The design combines handleless cabinetry, a matte black accent and warm cove lighting to create a sleek home with generous hidden storage.'],
    'Minimalist': ['The design combines clean white cabinetry, muted finishes and integrated appliances to create an uncluttered home with built-in wardrobes and a flexible study space.',
                   'The design combines flush panels, a pale oak floor and concealed lighting to create a calm home where everything has a place.'],
    'Scandinavian': ['The design combines light birch finishes, soft textiles and bright lighting to create a cosy, airy home with a family-friendly living area.',
                     'The design combines pale timber, white walls and woven accents to create a bright home with a relaxed reading corner.'],
    'Industrial': ['The design combines exposed brick, black steel framing and polished concrete to create a bold loft-style home with an open kitchen.',
                   'The design combines a concrete feature wall, metal shelving and track lighting to create a raw but comfortable open-plan home.'],
    'Contemporary': ['The design combines open-plan zones, a statement ceiling and neutral tones to create a bright home that is easy to entertain in.',
                     'The design combines curved details, a soft neutral palette and a floating console to create a fresh, flexible living space.'],
    'Japandi': ['The design combines warm timber, low furniture and paper-soft lighting to create a calm home with a quiet tea corner.',
                'The design combines light oak, neutral linen and slim black accents to create a serene home with clean storage.'],
    'Traditional': ['The design combines carved timber details, rich fabrics and classic lighting to create a home with a warm, lived-in feel.',
                    'The design combines teak panelling, heritage tiles and brass fittings to create a timeless home for a growing family.'],
    'Luxury': ['The design combines marble surfaces, brass accents and bespoke joinery to create a refined home with a hotel-style master suite.',
               'The design combines velvet seating, a marble feature wall and statement lighting to create a grand and polished home.'],
    'Coastal': ['The design combines soft blues, whitewashed timber and natural fibres to create a light home with a breezy living area.',
                'The design combines sand tones, rattan details and open shelving to create a relaxed home that feels like a holiday.'],
    'Rustic': ['The design combines textured timber, natural stone and earthy upholstery to create a warm home with tactile finishes, layered rugs and a relaxed dining space.',
               'The design combines reclaimed wood, exposed beams and woven baskets to create a cosy home with a farmhouse kitchen.'],
}
ESTATES = ['Ang Mo Kio', 'Bedok', 'Bishan', 'Bukit Panjang', 'Bukit Timah', 'Clementi', 'Hougang', 'Jurong East', 'Kovan',
           'Marine Parade', 'Pasir Ris', 'Punggol', 'Queenstown', 'Sengkang', 'Serangoon', 'Tampines', 'Telok Blangah',
           'Toa Payoh', 'Woodlands', 'Yishun']
SCOPE = 'living and dining areas, kitchen cabinetry, bedroom storage and lighting coordination'
# a typical price for each kind of home (the existing projects sit between 22,000 and 427,400)
PRICE_BASE = {
    'HDB': {'2-Room': 24000, '3-Room': 38000, '4-Room': 55000, '5-Room': 70000, '3Gen': 85000, 'Maisonette': 90000,
            'Jumbo': 95000, 'Studio Apartment': 22000},
    'Condo': {'Studio': 26000, '1-Bedroom': 40000, '2-Bedroom': 62000, '3-Bedroom': 90000, '4-Bedroom': 120000,
              '5+ Bedrooms': 150000, 'Penthouse': 165000},
    'Landed': {'Terrace House': 120000, 'Townhouse': 180000, 'Semi-Detached House': 220000,
               'Bungalow / Detached House': 320000, 'Good Class Bungalow (GCB)': 420000},
}
COMPANY_WORDS = (['Oak', 'Lumen', 'Nest', 'Urban', 'Pebble', 'Rooted', 'Ivory', 'Merlion', 'Atlas', 'Cedar', 'Harbour',
                  'Indigo', 'Juniper', 'Kopi', 'Linen', 'Maple', 'Nova', 'Olive', 'Palm', 'Quartz'],
                 ['Studio', 'Interiors', 'Design Co', 'Atelier', 'Collective', 'Spaces', 'Works', 'House'])
HOUR_WEIGHTS = [1, 1, 1, 1, 1, 2, 3, 4, 5, 5, 5, 6, 6, 6, 6, 6, 7, 8, 9, 10, 10, 9, 6, 3]     # Singapore clock hours
PROFILES = [('excellent', 18), ('good', 28), ('average', 28), ('poor', 10), ('new', 16)]       # share of designers (%)
RATING_WEIGHTS = {'excellent': [0, 0, 3, 22, 75], 'good': [1, 3, 10, 40, 46], 'average': [5, 12, 33, 35, 15],
                  'poor': [30, 30, 22, 12, 6]}
JOBS_PER_DESIGNER = {'excellent': 8, 'good': 6, 'average': 5, 'poor': 4}
MARKER = 'newdesigner1@demo.test'


def extend(db_path, designers=137, customers=45, projects=200, days=90, seed=2026):
    """Adds the extra demo data. Returns a summary text, or None if it was added before."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    try:
        if db.execute('SELECT 1 FROM user WHERE email = ?', (MARKER,)).fetchone():
            return None
        from idfinder.entities import review_schema
        review_schema.ensure(db)
        return _extend(db, designers, customers, projects, days, random.Random(seed))
    finally:
        db.close()


def _extend(db, n_designers, n_customers, n_projects, days, rng):
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0)
    password_hash = generate_password_hash(PASSWORD)

    # ---- what the database already has: categories, their pictures, housing types
    category_rows = db.execute('SELECT id, name FROM category WHERE active = 1 ORDER BY id').fetchall()
    categories = {r['name']: r['id'] for r in category_rows}
    if not categories:
        raise RuntimeError('The database has no design categories yet.')
    names = list(categories)
    picture = {}
    for row in db.execute('SELECT c.name, m.link FROM idp_media m JOIN idp_category ic ON ic.idp_id = m.idp_id '
                          'JOIN category c ON c.id = ic.category_id ORDER BY m.mediaID'):
        picture.setdefault(row['name'], row['link'])                      # the picture the existing projects of that category use
    subtypes = {}
    for row in db.execute('SELECT s.id, s.name, t.code FROM property_subtype s JOIN property_type t ON t.id = s.property_type_id'):
        subtypes.setdefault(row['code'], []).append((row['id'], row['name']))
    types = [t for t in subtypes if t in PRICE_BASE]

    # ---- new customers, numbered after the ones that exist
    taken = {r['name'].lower() for r in db.execute('SELECT name FROM user')}

    def person():
        for _ in range(1000):
            name = f'{rng.choice(FIRST + MORE_FIRST)} {rng.choice(LAST + MORE_LAST)}'
            if name.lower() not in taken:
                taken.add(name.lower())
                return name
        raise RuntimeError('Ran out of unused names.')

    def add_user(name, email, kind, created, phone):
        return db.execute('INSERT INTO user (name, password, email, phone, Usertype, created) VALUES (?,?,?,?,?,?)',
                          (name, password_hash, email, phone, kind, _stamp(created))).lastrowid

    property_types = [r['code'] for r in db.execute('SELECT code FROM property_type ORDER BY id')]
    new_customers = {}
    for n in range(1, n_customers + 1):
        joined = start + timedelta(seconds=int(days * 86400 * rng.random() ** 0.7 * 0.97))
        uid = add_user(person(), f'newcustomer{n}@demo.test', 'customer', joined, f'9{rng.randint(1000000, 9999999)}')
        db.execute('INSERT INTO customer (cust_id, current_property_type, received_keys) VALUES (?,?,?)',
                   (uid, rng.choice(property_types), rng.choice((0, 1, None))))
        new_customers[uid] = joined
    all_customers = {r['id']: _to_dt(r['created']) or start for r in db.execute("SELECT id, created FROM user WHERE Usertype = 'customer'")}

    # ---- new companies and designers
    companies = []
    used = set()
    for k in range(1, max(2, n_designers // 5) + 1):
        for _ in range(100):
            name = f'{rng.choice(COMPANY_WORDS[0])} {rng.choice(COMPANY_WORDS[1])}'
            if name not in used:
                break
        used.add(name)
        slug = re.sub(r'[^a-z]+', '', name.lower())
        companies.append(db.execute('INSERT INTO company (companyName, companyLine, companyEmail) VALUES (?,?,?)',
                                    (name, f'DEMO-X{k}', f'hello@{slug}.demo.test')).lastrowid)
    profile_list = [p for p, share in PROFILES for _ in range(round(n_designers * share / 100))]
    while len(profile_list) < n_designers:
        profile_list.append('average')
    rng.shuffle(profile_list)
    new_designers, quality = {}, {}
    for n, profile in enumerate(profile_list[:n_designers], 1):
        joined = datetime(2026, 5, 1, 9) + timedelta(days=rng.uniform(0, 120)) if profile != 'new' else start + timedelta(days=days * rng.uniform(0.88, 0.96))
        uid = add_user(person(), f'newdesigner{n}@demo.test', 'designer', joined, f'+65 8{rng.randint(100, 999)} {rng.randint(1000, 9999)}')
        db.execute('INSERT INTO designer (userID, companyID) VALUES (?, ?)', (uid, companies[(n - 1) % len(companies)]))
        new_designers[uid], quality[uid] = joined, profile

    # ---- new projects: same format as the existing ones, each with its category's picture
    able = [d for d, q in quality.items() if q != 'new']
    weight = {d: {'excellent': 2.2, 'good': 1.4, 'average': 1.0, 'poor': 0.6}[quality[d]] for d in able}
    category_weights = [CATEGORY_APPEAL.get(n, 1.0) for n in names]
    titles_used = {r[0] for r in db.execute('SELECT title FROM idp')}
    projects_made, project_category, popularity = {}, {}, {}
    first_day = datetime(2026, 5, 21, 11)
    last_day = now.replace(hour=11, minute=0, second=0)
    if last_day > now:
        last_day -= timedelta(days=1)
    span_days = max(1, (last_day - first_day).days)
    for _ in range(n_projects):
        designer_id = rng.choices(able, weights=[weight[d] for d in able])[0]
        category = rng.choices(names, weights=category_weights)[0]
        ptype = rng.choice(types)
        sub_id, sub_name = rng.choice(subtypes[ptype])
        for _try in range(60):                                       # a title nobody used yet
            style = rng.choice(TITLE_STYLES.get(category, [category]))
            estate = rng.choice(ESTATES)
            title = f'{style} at {estate}'
            if title not in titles_used:
                break
        titles_used.add(title)
        middle = rng.choice(MIDDLES.get(category, [f'The design combines {category.lower()} finishes into a practical home.']))
        description = f'A {category.lower()} renovation for a {sub_name} {ptype} home in {estate}. {middle} The scope includes {SCOPE}.'
        base = PRICE_BASE[ptype].get(sub_name, 60000)
        price = int(round(base * rng.uniform(0.85, 1.3), -2))
        created = max(first_day + timedelta(days=rng.randrange(span_days + 1)), new_designers[designer_id] + timedelta(days=1))
        created = min(created, last_day)
        status = 'ongoing' if rng.random() < 0.13 else 'completed'
        pid = db.execute('INSERT INTO idp (designer_id, title, description, property_type, property_subtype_id, price, status, created)'
                         ' VALUES (?,?,?,?,?,?,?,?)',
                         (designer_id, title, description, ptype, sub_id, price, status, _stamp(created))).lastrowid
        db.execute('INSERT INTO idp_category (idp_id, category_id) VALUES (?, ?)', (pid, categories[category]))
        if picture.get(category):
            db.execute('INSERT INTO idp_media (idp_id, link, created) VALUES (?,?,?)', (pid, picture[category], _stamp(created)))
        projects_made[pid] = created
        project_category[pid] = category
        popularity[pid] = math.exp(rng.gauss(0, 0.8)) * CATEGORY_APPEAL.get(category, 1.0)

    # ---- views and shortlists for the new projects, over the last `days` days
    day_weights = []
    for d in range(days):
        date = start + timedelta(days=d)
        day_weights.append((0.55 + 0.9 * d / days) * (1.35 if date.weekday() >= 5 else 1.0))
    customer_ids = list(all_customers)
    pairs = {(r[0], r[1]) for r in db.execute('SELECT customer_id, idp_id FROM favourite_idp')}
    views = favourites = 0
    for pid, created in projects_made.items():
        count = int(max(3, rng.gauss(28, 14)) * popularity[pid] / 1.5)
        for _ in range(count):
            day = rng.choices(range(days), weights=day_weights)[0]
            local_hour = rng.choices(range(24), weights=HOUR_WEIGHTS)[0]
            moment = start + timedelta(days=day, hours=local_hour - 8, minutes=rng.randrange(60), seconds=rng.randrange(60))
            if moment > now or moment < created:
                continue
            viewer = rng.choice(customer_ids) if rng.random() < 0.55 else None
            if viewer is not None and all_customers[viewer] > moment:
                viewer = None
            db.execute('INSERT INTO idp_view (idp_id, viewer_id, viewed_at) VALUES (?,?,?)', (pid, viewer, _stamp(moment)))
            views += 1
            if viewer is not None and (viewer, pid) not in pairs and rng.random() < CONVERSION.get(project_category[pid], 0.1) * 2:
                pairs.add((viewer, pid))
                db.execute('INSERT INTO favourite_idp (customer_id, idp_id, created) VALUES (?,?,?)',
                           (viewer, pid, _stamp(min(now, moment + timedelta(minutes=rng.randint(1, 90))))))
                favourites += 1

    # ---- shortlisted designers
    all_designers = [r[0] for r in db.execute("SELECT id FROM user WHERE Usertype = 'designer'")]
    fav_pairs = {(r[0], r[1]) for r in db.execute('SELECT customer_id, designer_id FROM favourite_designer')}
    for customer, joined in new_customers.items():
        for designer_id in rng.sample(all_designers, k=min(len(all_designers), rng.randint(1, 4))):
            if (customer, designer_id) not in fav_pairs:
                fav_pairs.add((customer, designer_id))
                db.execute('INSERT INTO favourite_designer (customer_id, designer_id, created) VALUES (?,?,?)',
                           (customer, designer_id, _stamp(min(now, joined + timedelta(days=rng.uniform(0.1, 20))))))

    # ---- hiring jobs and reviews for the new designers (ratings follow each designer's quality)
    aspect_names = list(POSITIVE)

    ROOMS = ['living room', 'kitchen', 'master bedroom', 'whole flat', 'study', 'bathroom', 'dining area']
    OPENERS = ['We renovated our {room} in {estate} with {d}.', 'Our {room} project in {estate} took {weeks} weeks.',
               'Hired {d} for the {room} at our place in {estate}.', 'Did up our {room} ({estate}) over {weeks} weeks.',
               'Moved into {estate} and {d} handled the {room}.']

    def context(first):
        # real reviews are not word-for-word the same, so each one gets its own detail (room, estate, weeks)
        return rng.choice(OPENERS).format(d=first, room=rng.choice(ROOMS), estate=rng.choice(ESTATES), weeks=rng.randint(3, 16))

    def sentences(rating, designer_name):
        first = designer_name.split()[0]
        return context(first) + ' ' + core_sentences(rating, designer_name, first)

    def core_sentences(rating, designer_name, first):
        if rating >= 4:
            pool, k = POSITIVE, rng.choice((1, 2, 2, 3))
        elif rating <= 2:
            pool, k = NEGATIVE, rng.choice((1, 2, 2))
        else:
            return rng.choice(MIXED) + ' ' + rng.choice(POSITIVE[rng.choice(aspect_names)]).format(d=first)
        return ' '.join(rng.choice(pool[a]).format(d=first) for a in rng.sample(aspect_names, k))

    own = {}
    for pid, designer_id in db.execute('SELECT id, designer_id FROM idp WHERE designer_id IN (%s)' % ','.join('?' * len(new_designers)),
                                       list(new_designers)):
        own.setdefault(designer_id, []).append(pid)
    jobs = reviews = 0
    for designer_id, profile in quality.items():
        if profile == 'new':
            continue
        name = db.execute('SELECT name FROM user WHERE id = ?', (designer_id,)).fetchone()[0]
        for _ in range(JOBS_PER_DESIGNER[profile] + rng.randint(0, 2)):
            customer = rng.choice(customer_ids)
            roll = rng.random()
            status = ('completed' if roll < 0.72 else 'ongoing' if roll < 0.82 else 'requested' if roll < 0.90
                      else 'declined' if roll < 0.96 else 'cancelled')
            earliest = max(all_customers[customer], new_designers[designer_id]) + timedelta(hours=1)
            completed_at = None
            if status == 'completed':
                completed_at = start + timedelta(seconds=int(days * 86400 * rng.uniform(0.12, 0.99))) - timedelta(hours=3)
                created = max(earliest, completed_at - timedelta(days=rng.uniform(8, 45)))
                completed_at = min(max(completed_at, created + timedelta(days=1)), now - timedelta(hours=3))
                created = min(created, completed_at - timedelta(hours=1))
            else:
                created = min(max(earliest, start + timedelta(seconds=int(days * 86400 * rng.uniform(0.5, 0.99)))), now - timedelta(hours=1))
            job = db.execute(
                'INSERT INTO engagement (customer_id, designer_id, idp_id, title, message, status, created, updated, completed_at)'
                ' VALUES (?,?,?,?,?,?,?,?,?)',
                (customer, designer_id, rng.choice(own.get(designer_id, [None])), rng.choice(JOBS), '', status,
                 _stamp(created), _stamp(completed_at or created), _stamp(completed_at) if completed_at else None)).lastrowid
            jobs += 1
            if status == 'completed' and rng.random() < 0.8:
                rating = rng.choices([1, 2, 3, 4, 5], weights=RATING_WEIGHTS[profile])[0]
                comment = sentences(rating, name) if rng.random() < 0.9 else ''
                reviewed_at = min(now - timedelta(minutes=5), completed_at + timedelta(days=rng.uniform(0.2, 12)))
                sentiment, aspects = review_text.analyse(comment)
                review_id = db.execute(
                    'INSERT INTO review (engagement_id, customer_id, designer_id, rating, comment, sentiment, aspects, created, updated)'
                    ' VALUES (?,?,?,?,?,?,?,?,?)',
                    (job, customer, designer_id, rating, comment, sentiment, json.dumps(aspects),
                     _stamp(reviewed_at), _stamp(reviewed_at))).lastrowid
                reviews += 1
                if rating >= 4 and comment and rng.random() < 0.4:
                    db.execute('UPDATE review SET designer_reply = ?, replied_at = created WHERE id = ?',
                               (rng.choice(['Thank you so much, it was a pleasure working with you!', 'Glad you love the result!',
                                            'Thanks for the kind words, enjoy your new home.']), review_id))
    db.commit()
    return (f'Added {len(new_designers)} designers ({sum(1 for q in quality.values() if q == "new")} brand new), '
            f'{len(new_customers)} customers, {len(projects_made)} projects, {views} views, {favourites} shortlists, '
            f'{jobs} jobs, {reviews} reviews. Logins: newcustomerN@demo.test / newdesignerN@demo.test, password {PASSWORD}')


def _to_dt(text):
    try:
        return datetime.strptime(text, '%Y-%m-%d %H:%M:%S') if text else None
    except ValueError:
        return None

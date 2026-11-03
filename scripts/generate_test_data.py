"""Generate idfinder/test_data.sql: sample accounts, projects and activity for testing and demos.

From the project folder in cmd, with the virtual environment active (.venv\\Scripts\\activate):

    python scripts\\generate_test_data.py              (re)write idfinder\\test_data.sql
    flask --app idfinder load-test-data --reset       empty the database, then load the test data

The output is the same every run (fixed random seed). Change the counts below to make more
records, e.g. 100 of each for the final live demo. Every account's password is TEST_PASSWORD.
"""
import random
from datetime import datetime, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

DESIGNERS = 25
COMPANIES = 10
CUSTOMERS = 45
MANAGERS = 2
PROJECTS_PER_DESIGNER = (2, 3)       # each designer gets 2 or 3 projects
FAVOURITES = 130
VIEWS = 650

TEST_PASSWORD = 'Test1234!'
NOW = datetime(2026, 10, 28, 12, 0, 0)          # newest timestamp in the data (UTC)
START = NOW - timedelta(days=90)                 # oldest
FIRST_USER_ID = 1001                             # high ids so a database with a few real rows is unaffected
FIRST_COMPANY_ID = 501
FIRST_IDP_ID = 2001

OUTPUT = Path(__file__).resolve().parent.parent / 'idfinder' / 'test_data.sql'

FIRST_NAMES = ['Wei Ling', 'Jun Jie', 'Siti', 'Arjun', 'Mei Xin', 'Daniel', 'Nur Aisyah', 'Ryan', 'Priya',
               'Kai Wen', 'Hui Min', 'Farhan', 'Rachel', 'Marcus', 'Li Ting', 'Hafiz', 'Shu Fen', 'Ethan',
               'Kavitha', 'Zhi Hao', 'Amanda', 'Irfan', 'Jia Yi', 'Gabriel', 'Divya', 'Yong Sheng',
               'Clarissa', 'Ahmad', 'Xin Yi', 'Nicholas', 'Meera', 'Bryan', 'Hannah', 'Rizwan', 'Pei Shan',
               'Joshua', 'Aditi', 'Wen Hao', 'Sarah', 'Faizal', 'Ying Xuan', 'Vincent', 'Lakshmi', 'Jia Hui',
               'Aaron', 'Nadia', 'Zi Xuan', 'Sean', 'Anjali', 'Kelvin']
LAST_NAMES = ['Tan', 'Lim', 'Lee', 'Ng', 'Wong', 'Goh', 'Chua', 'Ong', 'Koh', 'Teo', 'Chan', 'Yeo', 'Ho',
              'Rahman', 'Ismail', 'Kumar', 'Nair', 'Pillai', 'Low', 'Sim', 'Toh', 'Seah', 'Quek', 'Aziz']
COMPANY_WORDS = ['Haven', 'Atelier', 'Nest', 'Studio Ember', 'Linear', 'Oak & Ivory', 'Kinfolk', 'Monoform',
                 'Verdant', 'Arcadia', 'Bloom', 'Northlight']
COMPANY_SUFFIX = ['Interiors', 'Design Studio', 'Design Co.', 'Living', 'Spaces']
CATEGORIES = ['Modern', 'Minimalist', 'Scandinavian', 'Industrial', 'Contemporary', 'Japandi',
              'Luxury', 'Traditional']
AREAS = ['Tampines', 'Punggol', 'Bishan', 'Jurong East', 'Sengkang', 'Toa Payoh', 'Ang Mo Kio', 'Bukit Timah',
         'Clementi', 'Woodlands', 'Queenstown', 'Pasir Ris', 'Serangoon', 'Bedok', 'Holland Village',
         'Tiong Bahru', 'Yishun', 'Novena']
ROOMS = ['kitchen', 'living room', 'master bedroom', 'study', 'bathrooms', 'dining area', 'balcony']
FINISHES = ['warm oak', 'matte black fittings', 'terrazzo', 'light ash veneer', 'quartz counters',
            'rattan accents', 'concrete-look tiles', 'brass trims', 'built-in storage', 'cove lighting']
SUBTYPES = {   # matches the property_subtype seed rows in schema.sql
    'HDB': ['2-Room', '3-Room', '4-Room', '5-Room', '3Gen', 'Maisonette', 'Jumbo', 'Studio Apartment'],
    'Condo': ['Studio', '1-Bedroom', '2-Bedroom', '3-Bedroom', '4-Bedroom', '5+ Bedrooms', 'Penthouse'],
    'Landed': ['Terrace House', 'Semi-Detached House', 'Bungalow / Detached House',
               'Good Class Bungalow (GCB)', 'Townhouse'],
}
PRICE_RANGE = {'HDB': (25_000, 80_000), 'Condo': (40_000, 150_000), 'Landed': (120_000, 450_000)}
TYPE_WEIGHTS = (('HDB', 6), ('Condo', 3), ('Landed', 1))

rng = random.Random(314)


def q(value):
    """SQL literal."""
    if value is None:
        return 'NULL'
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def ts(moment):
    return moment.strftime('%Y-%m-%d %H:%M:%S')


def between(start, end):
    return start + timedelta(seconds=rng.randint(0, max(0, int((end - start).total_seconds()))))


def people(count, used):
    names = []
    while len(names) < count:
        name = f'{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}'
        if name not in used:
            used.add(name)
            names.append(name)
    return names


def email(name, domain, used):
    base = name.lower().replace(' ', '.')
    address, n = f'{base}@{domain}', 2
    while address in used:
        address, n = f'{base}{n}@{domain}', n + 1
    used.add(address)
    return address


def phone(used, first_digits='89'):
    while True:
        number = rng.choice(first_digits) + ''.join(rng.choice('0123456789') for _ in range(7))
        if number not in used:
            used.add(number)
            return number


def subtype_id(code, name):
    return (f"(SELECT s.id FROM property_subtype s JOIN property_type t ON t.id = s.property_type_id"
            f" WHERE t.code = {q(code)} AND s.name = {q(name)})")


def main():
    password = generate_password_hash(TEST_PASSWORD)
    used_names, used_emails, used_phones = set(), set(), set()
    out = []
    add = out.append

    add('-- Test data for idfinder: generated by scripts/generate_test_data.py; edit that script, not this file.')
    add(f'-- {DESIGNERS} interior designers ({COMPANIES} companies), {CUSTOMERS} customers, {MANAGERS} platform managers,')
    add('-- their projects, design categories, favourites and project views over the last 90 days.')
    add(f'-- Every account logs in with its email and the password: {TEST_PASSWORD}')
    add('-- Load it from cmd (virtual environment active):  flask --app idfinder load-test-data --reset')
    add('-- (--reset empties the database first). It runs as one transaction, so if any id is')
    add('-- already taken nothing is inserted.')
    add('')
    add('BEGIN;')
    add('')

    # ---- categories (names are unique; existing ones are kept) ----
    add('-- Design categories')
    for name in CATEGORIES:
        add(f'INSERT OR IGNORE INTO category (name, active) VALUES ({q(name)}, 1);')
    add('')

    # ---- companies ----
    add('-- Companies')
    companies = []
    names = rng.sample([f'{w} {s}' for w in COMPANY_WORDS for s in COMPANY_SUFFIX], COMPANIES)
    for i, name in enumerate(names):
        cid = FIRST_COMPANY_ID + i
        slug = ''.join(ch for ch in name.lower() if ch.isalnum())
        companies.append(cid)
        add(f'INSERT INTO company (companyID, companyName, companyLine, companyEmail) VALUES '
            f'({cid}, {q(name)}, {q(phone(used_phones, "6"))}, {q("hello@" + slug + ".test")});')
    add('')

    # ---- users ----
    next_id = FIRST_USER_ID
    designers, customers, managers = [], [], []

    def user(name, kind, created):
        nonlocal next_id
        uid = next_id
        next_id += 1
        add(f'INSERT INTO user (id, name, password, email, phone, Usertype, created) VALUES '
            f'({uid}, {q(name)}, {q(password)}, {q(email(name, "idfinder.test", used_emails))}, '
            f'{q(phone(used_phones))}, {q(kind)}, {q(ts(created))});')
        return uid

    add('-- Platform managers')
    for i, name in enumerate(people(MANAGERS, used_names)):
        uid = user(name, 'manager', START - timedelta(days=30 - i))
        managers.append(uid)
        add(f'INSERT INTO platform (managerID) VALUES ({uid});')
    add('')

    add('-- Interior designers (every company has at least one)')
    for i, name in enumerate(people(DESIGNERS, used_names)):
        created = between(START - timedelta(days=20), START + timedelta(days=30))
        uid = user(name, 'designer', created)
        company = companies[i] if i < len(companies) else rng.choice(companies)
        designers.append((uid, created))
        add(f'INSERT INTO designer (userID, companyID) VALUES ({uid}, {company});')
    add('')

    add('-- Customers')
    for name in people(CUSTOMERS, used_names):
        created = between(START, NOW - timedelta(days=2))
        uid = user(name, 'customer', created)
        home = rng.choices([c for c, _ in TYPE_WEIGHTS], [w for _, w in TYPE_WEIGHTS])[0]
        keys = rng.choice([1, 1, 0, None])
        customers.append((uid, created))
        add(f'INSERT INTO customer (cust_id, current_property_type, received_keys) VALUES '
            f'({uid}, {q(home)}, {q(keys)});')
    add('')

    # ---- projects ----
    add('-- Interior design projects')
    projects = []
    category_links = []
    next_idp = FIRST_IDP_ID
    for designer_id, joined in designers:
        for _ in range(rng.randint(*PROJECTS_PER_DESIGNER)):
            code = rng.choices([c for c, _ in TYPE_WEIGHTS], [w for _, w in TYPE_WEIGHTS])[0]
            sub = rng.choice(SUBTYPES[code])
            styles = rng.sample(CATEGORIES, rng.randint(1, 3))
            area = rng.choice(AREAS)
            rooms = rng.sample(ROOMS, 2)
            title = f'{styles[0]} {sub} in {area}'
            description = (f'A {styles[0].lower()} renovation of a {sub} home in {area}, reworking the '
                           f'{rooms[0]} and {rooms[1]} with {rng.choice(FINISHES)} and {rng.choice(FINISHES)}.')
            low, high = PRICE_RANGE[code]
            price = rng.randrange(low, high, 500)
            created = between(max(joined, START), NOW - timedelta(days=1))
            status = 'ongoing' if created > NOW - timedelta(days=21) and rng.random() < 0.6 else 'completed'
            add(f'INSERT INTO idp (id, designer_id, title, description, property_type, property_subtype_id,'
                f' price, status, created) VALUES ({next_idp}, {designer_id}, {q(title)}, {q(description)},'
                f' {q(code)}, {subtype_id(code, sub)}, {price}, {q(status)}, {q(ts(created))});')
            projects.append((next_idp, created))
            category_links += [(next_idp, style) for style in styles]
            next_idp += 1
    add('')

    add('-- Project categories')
    for idp_id, style in category_links:
        add(f'INSERT INTO idp_category (idp_id, category_id) VALUES '
            f'({idp_id}, (SELECT id FROM category WHERE name = {q(style)}));')
    add('')

    # ---- activity: favourites and views (popular projects get more) ----
    weights = [rng.paretovariate(1.5) for _ in projects]

    add('-- Customer favourites')
    saved = set()
    while len(saved) < min(FAVOURITES, len(customers) * len(projects)):
        customer_id, customer_joined = rng.choice(customers)
        (idp_id, idp_created), = rng.choices(projects, weights)
        if (customer_id, idp_id) in saved:
            continue
        saved.add((customer_id, idp_id))
        when = between(max(customer_joined, idp_created), NOW)
        add(f'INSERT INTO favourite_idp (customer_id, idp_id, created) VALUES '
            f'({customer_id}, {idp_id}, {q(ts(when))});')
    add('')

    add('-- Project page views (viewer_id NULL = visitor who was not logged in)')
    for _ in range(VIEWS):
        (idp_id, idp_created), = rng.choices(projects, weights)
        viewer = None
        earliest = idp_created
        if rng.random() < 0.6:
            viewer, joined = rng.choice(customers)
            earliest = max(earliest, joined)
        add(f'INSERT INTO idp_view (idp_id, viewer_id, viewed_at) VALUES '
            f'({idp_id}, {q(viewer)}, {q(ts(between(earliest, NOW)))});')
    add('')
    add('COMMIT;')

    OUTPUT.write_text('\n'.join(out) + '\n', encoding='utf-8')
    print(f'Wrote {OUTPUT}: {len(designers)} designers, {len(customers)} customers, {len(managers)} managers, '
          f'{len(projects)} projects, {len(saved)} favourites, {VIEWS} views')


if __name__ == '__main__':
    main()

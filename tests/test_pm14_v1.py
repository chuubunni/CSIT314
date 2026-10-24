import os, tempfile
from idfinder import create_app
from idfinder.db import init_db, get_db
from idfinder.entities.user import Users, customers, designers, managers
from idfinder.entities.idp import IDP
from idfinder.entities.housing import Housing

d = tempfile.mkdtemp()
app = create_app({'TESTING': True, 'DATABASE': os.path.join(d, 't.sqlite'), 'SECRET_KEY': 'x', 'UPLOAD_FOLDER': d})
with app.app_context():
    init_db()
    db = get_db()
    cid = Users.create_user('Cathy', 'customer1', 'c@x.com', '1', 'customer'); customers.create_customer(cid, 'HDB')
    did = Users.create_user('Dee', 'pw', 'd@x.com', '1', 'designer'); designers.register_designer(did, 'Co', '1', 'co@x.com') if hasattr(designers, 'register_designer') else None
    mid = Users.create_user('Mgr', 'manager1', 'm@x.com', '1', 'manager'); managers.create_manager(mid)
    landed_sub = Housing.find_type('Landed') and db.execute("SELECT id FROM property_subtype WHERE property_type_id=(SELECT id FROM property_type WHERE code='Landed') LIMIT 1").fetchone()[0]
    IDP.create(did, 'Landed job', 'x', 'Landed', 100, 'ongoing', (), landed_sub)          # Landed is in use by a project
    db.execute("INSERT INTO property_type (code, name) VALUES ('Shophouse', 'Shophouse')")
    sid = db.execute("SELECT id FROM property_type WHERE code='Shophouse'").fetchone()[0]
    db.execute("INSERT INTO property_subtype (property_type_id, name) VALUES (?, 'Conservation')", (sid,))
    db.commit()
    ids = {r['code']: r['id'] for r in Housing.types()}

c = app.test_client()
def login(email, pw): c.get('/auth/logout'); return c.post('/auth/login', data={'email': email, 'password': pw})
url = lambda i: f'/platform/property-types/{i}/delete'

# access control
assert c.post(url(ids['Shophouse'])).status_code == 302                                   # logged out
login('c@x.com', 'customer1'); assert c.post(url(ids['Shophouse'])).status_code == 403    # customer
login('m@x.com', 'manager1')
assert c.get(url(ids['Shophouse'])).status_code == 405                                    # destructive action is POST only
assert c.post(url(9999)).status_code == 404                                               # unknown id

# dashboard lists types with usage
t = c.get('/platform/dashboard').data.decode()
assert 'Property Types' in t and 'Shophouse' in t and 'Condominium' in t

# in use -> refused, nothing deleted
r = c.post(url(ids['HDB']), follow_redirects=True).data.decode()
assert 'Cannot remove HDB' in r and '1 customer(s)' in r
r = c.post(url(ids['Landed']), follow_redirects=True).data.decode()
assert 'Cannot remove Landed' in r and '1 project(s)' in r
with app.app_context():
    assert {'HDB', 'Condo', 'Landed', 'Shophouse'} <= set(Housing.codes())

# the unused type is forms-visible, then removed
r = c.post(url(ids['Shophouse']), follow_redirects=True).data.decode()
assert 'Property type Shophouse removed.' in r
with app.app_context():
    assert 'Shophouse' not in Housing.codes()
    assert db is not None and get_db().execute("SELECT COUNT(*) FROM property_subtype WHERE name='Conservation'").fetchone()[0] == 0  # subtypes go too
    assert get_db().execute('SELECT COUNT(*) FROM idp').fetchone()[0] == 1                                                            # projects untouched

# projects page still works after removal (project form reads types from the database)
login('d@x.com', 'pw')
r = c.get('/portfolio/new'); assert r.status_code == 200 and b'Shophouse' not in r.data

# last remaining type can't be removed
login('m@x.com', 'manager1')
with app.app_context():
    db = get_db(); db.execute("DELETE FROM property_subtype WHERE property_type_id != ?", (ids['Condo'],))
    db.execute("DELETE FROM property_type WHERE id != ?", (ids['Condo'],)); db.commit()
r = c.post(url(ids['Condo']), follow_redirects=True).data.decode()
assert 'At least one property type must remain' in r
print('ALL PM14 CHECKS PASSED')

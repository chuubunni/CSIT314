import os, tempfile, sqlite3
from idfinder import create_app
from idfinder.db import init_db, get_db
from idfinder.housing_migration import migrate_housing
from idfinder.entities.user import Users, customers, designers, managers

d = tempfile.mkdtemp()
app = create_app({'TESTING': True, 'DATABASE': os.path.join(d, 't.sqlite'), 'SECRET_KEY': 'x', 'UPLOAD_FOLDER': d})
with app.app_context():
    init_db(); migrate_housing(get_db())
    cid = Users.create_user('Cathy', 'customer1', 'c@x.com', '1', 'customer'); customers.create_customer(cid, 'HDB')
    for n, e, co in [('Alice Tan', 'a@x.com', 'Alpha Interiors'), ('bob TANaka', 'b@x.com', 'Beta Design'),
                     ('Carl Lim', 'l@x.com', 'Alpha Interiors'), ('100%_Real', 'r@x.com', 'Gamma')]:
        u = Users.create_user(n, 'pw', e, '1', 'designer')
        designers.register_designer(u, co, 'L' + e, e) if co != 'Alpha Interiors' or n == 'Alice Tan' else designers.create_designer(u, 1)
    mid = Users.create_user('Mgr', 'manager1', 'm@x.com', '1', 'manager'); managers.create_manager(mid)

c = app.test_client()
def login(email, pw):
    c.get('/auth/logout'); return c.post('/auth/login', data={'email': email, 'password': pw})

# access control
assert c.get('/designers').status_code == 302                       # logged out -> login
login('m@x.com', 'manager1'); assert c.get('/designers').status_code == 403
login('a@x.com', 'pw'); assert c.get('/designers').status_code == 403
login('c@x.com', 'customer1')
r = c.get('/designers'); assert r.status_code == 200 and b'4 designers found' in r.data       # blank = all
r = c.get('/designers?name=tan'); t = r.data.decode()
assert '2 designers found' in t and 'Alice Tan' in t and 'bob TANaka' in t and 'Carl' not in t  # case-insens, substring
assert 'Alpha Interiors' in t
r = c.get('/designers?name=%25'); assert b'1 designer found' in r.data and b'100%_Real' in r.data  # % literal
r = c.get('/designers?name=_'); assert b'1 designer found' in r.data                              # _ literal
r = c.get('/designers?name=zzz'); assert b'0 designers found' in r.data and b'No designers match' in r.data
r = c.get("/designers?name=' OR 1=1 --"); assert b'0 designers found' in r.data                   # SQLi-safe
r = c.get('/designers?name=' + 'a' * 101); assert r.status_code == 400 and b'100 characters' in r.data
r = c.get('/designers?name=%3Cscript%3E'); assert b'<script>' not in r.data                        # escaped
assert b'Cathy' not in c.get('/designers?name=Cathy').data.replace(b'Cathy</span>', b'') or b'0 designers' in c.get('/designers?name=Cathy').data  # customers not listed
assert b'Find Designers' in c.get('/').data
print('ALL C19 CHECKS PASSED')

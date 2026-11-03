import pytest
from werkzeug.security import generate_password_hash

from idfinder import create_app
from idfinder.db import get_db, init_db


@pytest.fixture
def app(tmp_path):
    """A fresh app with its own empty SQLite file for every test."""
    app = create_app({
        'TESTING': True,
        'SECRET_KEY': 'test',
        'DATABASE': str(tmp_path / 'test.sqlite'),
        'UPLOAD_FOLDER': str(tmp_path / 'uploads'),
    })
    with app.app_context():
        init_db()
    return app


@pytest.fixture
def ctx(app):
    """App context: the entities call get_db(), which needs one."""
    with app.app_context():
        yield


class Factory:
    """Tiny helpers that insert rows with explicit timestamps, so tests control the dates."""

    def __init__(self):
        self.db = get_db()
        self._n = 0

    def _next(self):
        self._n += 1
        return self._n

    def _run(self, sql, params=()):
        cursor = self.db.execute(sql, params)
        self.db.commit()
        return cursor.lastrowid

    def user(self, kind='customer', created='2026-09-01 09:00:00', password='pw', name=None):
        n = self._next()
        user_id = self._run(
            'INSERT INTO user (name, password, email, phone, Usertype, created) VALUES (?,?,?,?,?,?)',
            (name or f'user{n} Tester', generate_password_hash(password, method='pbkdf2:sha256:1000'),
             f'user{n}@test.com', '91234567', kind, created))
        if kind == 'customer':
            self._run('INSERT INTO customer (cust_id, current_property_type) VALUES (?, ?)', (user_id, 'HDB'))
        elif kind == 'manager':
            self._run('INSERT INTO platform (managerID) VALUES (?)', (user_id,))
        elif kind == 'designer':
            company_id = self._run(
                'INSERT INTO company (companyName, companyLine) VALUES (?, ?)', (f'Co{n}', f'6000{n:04d}'))
            self._run('INSERT INTO designer (userID, companyID) VALUES (?, ?)', (user_id, company_id))
        return user_id

    def email(self, user_id):
        return self.db.execute('SELECT email FROM user WHERE id = ?', (user_id,)).fetchone()[0]

    def project(self, designer_id, created='2026-10-01 09:00:00', property_type='HDB'):
        n = self._next()
        return self._run(
            'INSERT INTO idp (designer_id, title, property_type, price, created) VALUES (?,?,?,?,?)',
            (designer_id, f'Project {n}', property_type, 1000, created))

    def category(self, name, active=1):
        return self._run('INSERT INTO category (name, active) VALUES (?, ?)', (name, active))

    def tag(self, idp_id, category_id):
        self._run('INSERT INTO idp_category (idp_id, category_id) VALUES (?, ?)', (idp_id, category_id))

    def view(self, idp_id, at):
        self._run('INSERT INTO idp_view (idp_id, viewed_at) VALUES (?, ?)', (idp_id, at))

    def favourite(self, customer_id, idp_id, at='2026-10-01 09:00:00'):
        self._run('INSERT INTO favourite_idp (customer_id, idp_id, created) VALUES (?, ?, ?)',
                  (customer_id, idp_id, at))

    def engagement(self, customer_id, designer_id, status='completed', title='Kitchen makeover',
                   created='2026-10-01 09:00:00', completed_at='2026-10-10 09:00:00'):
        return self._run(
            'INSERT INTO engagement (customer_id, designer_id, title, status, created, completed_at)'
            ' VALUES (?,?,?,?,?,?)',
            (customer_id, designer_id, title, status, created,
             completed_at if status == 'completed' else None))

    def review(self, engagement_id, rating=5, comment='', sentiment=None, created='2026-10-12 09:00:00',
               status='visible', aspects='[]', reported_reason=None):
        row = self.db.execute('SELECT customer_id, designer_id FROM engagement WHERE id = ?',
                              (engagement_id,)).fetchone()
        return self._run(
            'INSERT INTO review (engagement_id, customer_id, designer_id, rating, comment, sentiment,'
            ' aspects, created, status, reported_reason) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (engagement_id, row['customer_id'], row['designer_id'], rating, comment, sentiment,
             aspects, created, status, reported_reason))

    def reviewed_job(self, designer_id, rating=5, comment='', sentiment=None, created='2026-10-12 09:00:00', **kw):
        """A new customer, a completed job with the designer, and a review of it. Returns the review id."""
        customer = self.user('customer')
        job = self.engagement(customer, designer_id)
        return self.review(job, rating, comment, sentiment, created, **kw)


@pytest.fixture
def make(ctx):
    return Factory()


class Client:
    """Test client that logs in through the real /auth/login route and handles the form token."""

    def __init__(self, client):
        self.client = client

    def login(self, email, password='pw'):
        return self.client.post('/auth/login', data={'email': email, 'password': password})

    def get(self, *args, **kwargs):
        return self.client.get(*args, **kwargs)

    def token(self):
        # any page that renders a form puts the token in the session
        self.client.get('/leaderboard')
        with self.client.session_transaction() as session:
            if 'story_form_token' not in session:
                import secrets
                session['story_form_token'] = secrets.token_hex(8)
            return session['story_form_token']

    def post(self, url, data=None, token=True, **kwargs):
        data = dict(data or {})
        if token:
            data['form_token'] = self.token()
        return self.client.post(url, data=data, **kwargs)


@pytest.fixture
def client(app):
    return Client(app.test_client())

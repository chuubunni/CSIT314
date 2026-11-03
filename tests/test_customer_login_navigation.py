"""C19: customer login must render navigation to registered routes."""
from story_fixture import StoryFixture


class CustomerLoginNavigationTests(StoryFixture):
    def test_customer_login_renders_homepage_and_search_link(self):
        response = self.client.post('/auth/login', data={
            'email': '3@example.test', 'password': 'test-pass'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Find Designers', response.data)
        self.assertIn(b'/designers', response.data)
        with self.client.session_transaction() as session:
            self.assertEqual(session['user_id'], 3)

    def test_customer_can_follow_navigation_links(self):
        self.login(3)
        for path in ('/', '/designers', '/customer/profile', '/favourites/'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_customer_designer_name_search(self):
        self.login(3)
        response = self.client.get('/designers?name=designer')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Studio A', response.data)

    def test_guest_search_requires_login(self):
        response = self.client.get('/designers')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login', response.headers['Location'])

    def test_other_roles_cannot_access_customer_search(self):
        for user_id in (1, 4):
            with self.subTest(user_id=user_id):
                self.login(user_id)
                self.assertEqual(self.client.get('/designers').status_code, 403)

    def test_invalid_login_stays_on_login_page(self):
        response = self.client.post('/auth/login', data={
            'email': '3@example.test', 'password': 'wrong-password'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Incorrect password', response.data)
        with self.client.session_transaction() as session:
            self.assertNotIn('user_id', session)

    def test_public_homepage_still_loads(self):
        self.assertEqual(self.client.get('/').status_code, 200)

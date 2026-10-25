# C09: tests for the customer's favourites page.
from story_fixture import StoryFixture
from idfinder.db import get_db
from idfinder.controller.favourites_controller import FavouritesController


class C09Tests(StoryFixture):
    def favourite(self, customer_id, idp_id, created):
        get_db().execute('INSERT INTO favourite_idp(customer_id,idp_id,created) VALUES (?,?,?)',
                         (customer_id, idp_id, created))
        get_db().commit()

    def test_c09_controller_lists_own_favourites_newest_first(self):
        self.favourite(3, 1, '2026-10-01 10:00:00')
        self.favourite(3, 3, '2026-10-02 10:00:00')
        self.favourite(5, 2, '2026-10-03 10:00:00')
        projects = FavouritesController().list_favourites(3)
        self.assertEqual([p['id'] for p in projects], [3, 1])
        first = projects[0]
        self.assertEqual(first['title'], 'Other designer')
        self.assertEqual(first['company_name'], 'Studio B')
        self.assertEqual(first['property_type'], 'HDB')
        self.assertEqual(first['category_names'], 'Minimalist')
        self.assertEqual(str(first['saved_at'])[:10], '2026-10-02')

    def test_c09_page_shows_saved_projects_with_links(self):
        self.favourite(3, 2, '2026-10-01 10:00:00')
        self.login(3)
        response = self.client.get('/favourites/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Second', response.data)
        self.assertIn(b'href="/projects/2"', response.data)
        self.assertNotIn(b'First', response.data)

    def test_c09_page_shows_only_the_logged_in_customers_favourites(self):
        self.favourite(5, 1, '2026-10-01 10:00:00')
        self.login(3)
        response = self.client.get('/favourites/')
        self.assertNotIn(b'href="/projects/1"', response.data)
        self.assertIn(b'You have not saved any projects yet.', response.data)

    def test_c09_empty_state_links_to_browse(self):
        self.login(3)
        response = self.client.get('/favourites/')
        self.assertIn(b'You have not saved any projects yet.', response.data)
        self.assertIn(b'href="/"', response.data)

    def test_c09_deleted_project_disappears(self):
        self.favourite(3, 1, '2026-10-01 10:00:00')
        self.ctrl.delete_idp(1, 1)
        self.assertEqual(FavouritesController().list_favourites(3), [])

    def test_c09_only_customers_can_open_the_page(self):
        self.assertEqual(self.client.get('/favourites/').status_code, 302)   # not logged in -> login
        for user_id in (1, 4):                                                # designer, manager
            self.login(user_id)
            self.assertEqual(self.client.get('/favourites/').status_code, 403)

    def test_c09_saved_project_appears_after_saving(self):
        self.login(3)
        self.save(1)
        self.assertIn(b'href="/projects/1"', self.client.get('/favourites/').data)

    def test_c09_homepage_links_to_favourites_for_customers_only(self):
        self.login(3)
        self.assertIn(b'href="/favourites/"', self.client.get('/').data)
        self.login(1)
        self.assertNotIn(b'href="/favourites/"', self.client.get('/').data)

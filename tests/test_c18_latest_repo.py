"""C18: the assistant must coexist with the newer review and category features."""
from urllib.parse import parse_qs, urlsplit
from story_fixture import StoryFixture


class LatestRepoChatIntegrationTests(StoryFixture):
    def test_c18_widget_coexists_with_review_pages_and_navigation(self):
        self.login(3)
        for path in ('/', '/designers', '/designers/1', '/leaderboard', '/my-jobs'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data.count(b'id="chatbot"'), 1)
                self.assertIn(b'/leaderboard', response.data)
                self.assertIn(b'/my-jobs', response.data)

    def test_c18_stays_customer_only_on_public_review_pages(self):
        for user_id in (None, 1, 4):
            if user_id is None:
                with self.client.session_transaction() as session:
                    session.clear()
            else:
                self.login(user_id)
            for path in ('/leaderboard', '/designers/1'):
                with self.subTest(user_id=user_id, path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertNotIn(b'id="chatbot"', response.data)

    def test_c08_save_keeps_new_category_filter_with_chat_enabled(self):
        self.login(3)
        response = self.save(category_id='1', property_type='HDB')
        query = parse_qs(urlsplit(response.headers['Location']).query)
        self.assertEqual(query['category_id'], ['1'])
        self.assertEqual(query['property_type'], ['HDB'])
        page = self.client.get(response.headers['Location'])
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.data.count(b'id="chatbot"'), 1)
        self.assertIn(b'Saved to favourites', page.data)

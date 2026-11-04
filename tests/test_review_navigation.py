"""Public review pages must not advertise a customer-only search to other roles."""
from story_fixture import StoryFixture


class ReviewNavigationTests(StoryFixture):
    def test_find_designers_navigation_matches_customer_permission(self):
        for user_id in (None, 1, 3, 4):
            if user_id is None:
                with self.client.session_transaction() as session:
                    session.clear()
            else:
                self.login(user_id)
            for path in ('/leaderboard', '/designers/1'):
                with self.subTest(user_id=user_id, path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(b'>Find designers</a>' in response.data, user_id == 3)
            # Public designer profiles stay reachable for everyone; search retains its role rule.
            self.assertEqual(self.client.get('/designers').status_code,
                             302 if user_id is None else 200 if user_id == 3 else 403)

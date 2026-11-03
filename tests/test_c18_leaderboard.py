"""C18: rank real fixture designers through the existing leaderboard, without live AI."""
from datetime import datetime
import json
import re
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from story_fixture import StoryFixture
from idfinder.controller import ranking
from idfinder.controller.chatbot_leaderboard import ChatbotLeaderboard
from idfinder.controller.errors import ValidationError
from idfinder.controller.leaderboard_controller import LeaderboardController
from idfinder.db import get_db
from idfinder.services.gemini_chat import GeminiChat, SCHEMA, SYSTEM


class C18LeaderboardTests(StoryFixture):
    def setUp(self):
        super().setUp()
        self.app.config['GEMINI_API_KEY'] = 'test-only-not-a-real-key'
        clock = patch('idfinder.controller.leaderboard_controller._utc_now', return_value=datetime(2026, 11, 3, 12))
        clock.start(); self.addCleanup(clock.stop)
        db = get_db()
        for designer_id, rating, status in [(1, 5, 'visible'), (2, 3, 'visible'), (2, 5, 'hidden')]:
            job = db.execute("INSERT INTO engagement(customer_id,designer_id,title,status,completed_at) "
                             "VALUES (3,?,'Renovation','completed','2026-10-29')", (designer_id,)).lastrowid
            db.execute("INSERT INTO review(engagement_id,customer_id,designer_id,rating,comment,status,created) "
                       "VALUES (?,3,?,?,'Good communication',?,'2026-10-30')", (job, designer_id, rating, status))
        db.commit()
        self.login(3)
        self.csrf = self.token('/chat/')

    def ask(self, options=None, message='Show the top 5 designers', inherit=False, **values):
        action = {'intent': 'search_leaderboard', 'filters': {}, 'leaderboard': options,
                  'inherit_filters': inherit, **values}
        with patch.object(GeminiChat, 'interpret', return_value=action) as mocked:
            response = self.client.post('/chat/message', data={'message': message, 'form_token': self.csrf})
        return response, mocked

    def test_c18_order_scores_and_profile_links_match_existing_leaderboard(self):
        expected = LeaderboardController().leaderboard()['rows']
        response, _ = self.ask()
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual([(r['id'], r['rank'], r['score']) for r in data['leaderboard']],
                         [(r['id'], r['rank'], r['score']) for r in expected])
        for row in data['leaderboard']:
            self.assertEqual(row['url'], f"/designers/{row['id']}")
            self.assertEqual(self.client.get(row['url']).status_code, 200)
            self.assertNotIn('email', row)
            self.assertNotIn('password', row)

    def test_c18_category_housing_minimum_and_weights_are_preserved_in_board_link(self):
        weights = {key: 100 if key == 'rating' else 0 for key in ranking.COMPONENTS}
        response, _ = self.ask({'category': 'modern', 'property_type': 'hdb', 'min_reviews': 1, 'limit': 1, 'weights': weights})
        self.assertEqual(response.status_code, 200)
        data = response.get_json(); self.assertEqual(len(data['leaderboard']), 1)
        self.assertEqual(data['leaderboard'][0]['id'], 1)
        url = data['actions'][0]['url']; params = parse_qs(urlsplit(url).query)
        self.assertEqual(params['category_id'], ['1']); self.assertEqual(params['property_type'], ['HDB'])
        self.assertEqual(params['min_reviews'], ['1']); self.assertEqual(float(params['w_rating'][0]), 100)
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        board = json.loads(re.search(rb'id="leaderboard-data">(.*?)</script>', page.data, re.S).group(1))
        self.assertEqual(board['rows'][0]['score'], data['leaderboard'][0]['score'])
        self.assertEqual(board['weights'], data['ranking_weights'])

    def test_c18_hidden_reviews_do_not_satisfy_minimum(self):
        response, _ = self.ask({'min_reviews': 2})
        data = response.get_json()
        self.assertEqual(response.status_code, 200); self.assertEqual(data['total'], 0)
        self.assertEqual(data['leaderboard'], [])
        self.assertIn('No designers match', data['reply'])
        self.assertEqual(self.client.get(data['actions'][0]['url']).status_code, 200)

    def test_c18_no_review_designer_is_not_given_a_fake_average(self):
        db = get_db(); db.execute('DELETE FROM review'); db.commit()
        response, _ = self.ask()
        data = response.get_json()
        self.assertIn('no visible reviews yet', data['reply'])
        self.assertTrue(all(row['avg_rating'] is None and row['reviews'] == 0 for row in data['leaderboard']))

    def test_c18_ranked_follow_up_keeps_context_but_fresh_search_clears_it(self):
        self.ask({'category': 'Modern', 'min_reviews': 1})
        response, interpreter = self.ask({'property_type': 'HDB'}, 'only HDB designers', inherit=True)
        params = parse_qs(urlsplit(response.get_json()['actions'][0]['url']).query)
        self.assertEqual(params['category_id'], ['1']); self.assertEqual(params['min_reviews'], ['1'])
        context = interpreter.call_args.args[1]
        self.assertEqual(context['previous_intent'], 'search_leaderboard')
        self.assertEqual(context['previous_leaderboard']['category'], 'Modern')
        response, interpreter = self.ask({}, 'Show top designers overall', inherit=True)
        params = parse_qs(urlsplit(response.get_json()['actions'][0]['url']).query)
        self.assertNotIn('category_id', params); self.assertNotIn('property_type', params)
        self.assertEqual(params['min_reviews'], ['0'])
        self.assertEqual(interpreter.call_args.args[1]['previous_leaderboard'], {})

    def test_c18_explicit_clear_and_weight_reset(self):
        old = ChatbotLeaderboard.clean({'category': 'Modern', 'property_type': 'HDB',
                                       'weights': {key: 100 if key == 'experience' else 0 for key in ranking.COMPONENTS}})
        clean = ChatbotLeaderboard.clean({'category': '', 'property_type': '', 'weights': {}}, old)
        self.assertNotIn('category_id', clean); self.assertNotIn('property_type', clean)
        self.assertEqual(clean['weights'], ranking.DEFAULT_WEIGHTS)

    def test_c18_invalid_ranking_options_are_rejected(self):
        invalid = [[], '', {'sql': 'SELECT * FROM user'}, {'category': 'Inactive'}, {'category': 'unknown'},
                   {'property_type': '4-Room'}, {'category': ['Modern', 'Minimalist']},
                   {'min_reviews': True}, {'min_reviews': -1}, {'min_reviews': 51}, {'min_reviews': '2'},
                   {'limit': 0}, {'limit': 11}, {'limit': 1.5},
                   {'weights': {'unknown': 5}}, {'weights': {'rating': True}},
                   {'weights': {'rating': float('nan')}}, {'weights': {'rating': float('inf')}},
                   {'weights': {'rating': 10**400}}, {'weights': {'rating': -1}},
                   {'weights': {key: 0 for key in ranking.COMPONENTS}}]
        for value in invalid:
            with self.subTest(value=str(value)[:80]), self.assertRaises(ValidationError):
                ChatbotLeaderboard.clean(value)
        response, _ = self.ask([])
        self.assertEqual(response.status_code, 422)

    def test_c18_project_constraints_are_not_silently_dropped_in_ranking(self):
        response, _ = self.ask({}, filters={'max_price': 50000})
        self.assertEqual(response.status_code, 422)
        self.assertIn('Use project search', response.get_json()['reply'])

    def test_c18_rankings_do_not_write_business_data_and_restore_in_history(self):
        db = get_db(); tables = ['idp','favourite_idp','review','engagement','idp_view']
        before = {t: list(db.execute('SELECT * FROM '+t)) for t in tables}
        response, _ = self.ask({'limit': 1})
        self.assertEqual(response.status_code, 200)
        after = {t: list(db.execute('SELECT * FROM '+t)) for t in tables}
        self.assertEqual(before, after)
        history = self.client.get('/chat/history').get_json()['messages']
        self.assertEqual(history[-1]['data']['leaderboard'], response.get_json()['leaderboard'])

    def test_c18_leaderboard_navigation_help_and_suggestion(self):
        self.assertIn(b'Top designers', self.client.get('/').data)
        for values in [{'intent':'navigate','page':'leaderboard'}, {'intent':'help','topic':'leaderboard'}]:
            response, _ = self.ask(**values)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['actions'][0]['url'], '/leaderboard')
        self.assertIn('search_leaderboard', SCHEMA['properties']['intent']['enum'])
        self.assertIn('leaderboard', SCHEMA['required'])
        self.assertIn('Python retrieves the actual ranks', SYSTEM)

    def test_c18_project_search_filters_do_not_leak_into_ranking(self):
        with patch.object(GeminiChat, 'interpret', return_value={
                'intent':'search_projects','filters':{'category':'Modern','max_price':15000},'inherit_filters':False}):
            self.client.post('/chat/message',data={'message':'Modern projects below 15k','form_token':self.csrf})
        response, _ = self.ask({}, 'Show top designers', inherit=True)
        params = parse_qs(urlsplit(response.get_json()['actions'][0]['url']).query)
        self.assertNotIn('category_id', params)
        self.assertNotIn('max_price', params)

    def test_c18_leaderboard_retains_existing_customer_role_and_csrf_checks(self):
        with patch.object(GeminiChat, 'interpret') as interpreter:
            response = self.client.post('/chat/message',data={'message':'top designers','form_token':'wrong'})
            self.assertEqual(response.status_code, 400)
            self.login(1)
            self.assertEqual(self.client.post('/chat/message').status_code, 403)
            interpreter.assert_not_called()

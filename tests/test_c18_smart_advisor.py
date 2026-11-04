"""C18: grounded SQLite results and confirmed choices, without paid Gemini calls."""
from unittest.mock import patch
from story_fixture import StoryFixture
from idfinder.db import get_db
from idfinder.entities.favourites import Favourites
from idfinder.services.gemini_chat import GeminiChat


class SmartAdvisorTests(StoryFixture):
    def setUp(self):
        super().setUp()
        self.app.config['GEMINI_API_KEY'] = 'test-key-not-real'
        self.login(3)
        self.csrf = self.token('/chat/')

    def ask(self, text, action=None):
        with patch.object(GeminiChat, 'interpret', return_value=action or {'intent': 'help', 'topic': 'search'}) as model:
            response = self.client.post('/chat/message', data={'message': text, 'form_token': self.csrf})
        return response, model

    def search(self, filters, text='Find projects'):
        return self.ask(text, {'intent': 'search_projects', 'filters': filters, 'inherit_filters': False})[0]

    def test_match_reasons_reference_actual_records_and_filters(self):
        db = get_db()
        db.execute("UPDATE idp SET title='Bishan home',description='A home with concealed storage' WHERE id=1")
        db.commit()
        response = self.search({'max_price': 10000, 'categories': ['Modern'], 'keywords': ['Bishan'],
                                'housing_options': [{'property_type': 'HDB'}]})
        self.assertEqual(response.status_code, 200)
        projects = response.json['projects']
        self.assertEqual([p['id'] for p in projects], [1])
        reasons = ' '.join(projects[0]['match_reasons'])
        self.assertIn('S$10,000', reasons)
        self.assertIn('Matching style tags: Modern', reasons)
        self.assertIn('appears in the title', reasons)
        self.assertNotIn('Japandi', reasons)

    def test_empty_results_offer_verified_alternatives_without_changing_constraints(self):
        response = self.search({'max_price': 5000, 'categories': ['Modern']})
        self.assertEqual(response.json['total'], 0)
        self.assertEqual(response.json['filters']['max_price'], 5000)
        self.assertEqual(response.json['projects'], [])
        self.assertIn('matches)', response.json['suggestions'][0]['label'])
        selected, model = self.ask(response.json['suggestions'][0]['message'])
        self.assertEqual(selected.status_code, 200)
        self.assertGreater(selected.json['total'], 0)
        self.assertEqual(selected.json['filters']['max_price'], 15000)
        model.assert_not_called()

    def test_inferred_styles_require_confirmation_and_retain_budget(self):
        response, _ = self.ask('Warm wood and neutral colours under 10000',
                              {'intent': 'search_projects', 'filters': {'max_price': 10000},
                               'inherit_filters': False, 'suggested_styles': ['Modern', 'Minimalist']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['projects'], [])
        self.assertIn('style interpretation', response.json['reply'])
        confirmed, model = self.ask(response.json['suggestions'][0]['message'])
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json['filters']['max_price'], 10000)
        self.assertEqual(set(confirmed.json['filters']['categories']), {'Modern', 'Minimalist'})
        self.assertEqual(confirmed.json['filters']['category_mode'], 'any')
        model.assert_not_called()

    def test_inactive_or_invented_style_proposals_are_rejected(self):
        for names in (['Inactive'], ['Invented'], ['Modern', True]):
            with self.subTest(names=names):
                response, _ = self.ask('warm and calm', {'intent': 'clarify', 'suggested_styles': names, 'filters': {}})
                self.assertEqual(response.status_code, 422)

    def test_vague_recommendation_asks_for_a_brief(self):
        response, model = self.ask('Find a designer for my house')
        self.assertEqual(response.status_code, 200)
        self.assertIn('property type', response.json['reply'])
        model.assert_not_called()
        response, model = self.ask('HDB under 10000', {'intent': 'search_projects', 'filters': {'property_type': 'HDB', 'max_price': 10000}, 'inherit_filters': True})
        self.assertEqual(response.json['total'], 3)
        self.assertEqual(model.call_args.args[1]['request_scope'], 'follow_up')

    def test_clarifications_retain_partial_requirements(self):
        response, _ = self.ask('I have a budget of 10000', {'intent': 'clarify', 'question': 'Which property type?',
                                                        'filters': {'max_price': 10000}})
        self.assertEqual(response.status_code, 200)
        response, model = self.ask('HDB', {'intent': 'search_projects', 'filters': {'property_type': 'HDB'}, 'inherit_filters': True})
        self.assertEqual(response.json['filters']['max_price'], 10000)
        self.assertEqual(model.call_args.args[1]['previous_filters']['max_price'], 10000)

    def test_start_over_after_clarification_resets_requirements(self):
        self.ask('budget 10000', {'intent': 'clarify', 'question': 'Style?', 'filters': {'max_price': 10000}})
        response, model = self.ask('Start over', {'intent': 'search_projects', 'filters': {}, 'inherit_filters': False})
        self.assertEqual(response.json['filters'], {})
        self.assertEqual(model.call_args.args[1]['request_scope'], 'new_search')






    def test_expired_options_do_not_apply_after_new_request(self):
        first = self.search({'max_price': 5000}).json['suggestions'][0]['message']
        self.ask('Explain categories', {'intent': 'help', 'topic': 'categories'})
        response, _ = self.ask(first)
        self.assertEqual(response.status_code, 422)

    def test_old_option_cannot_apply_a_new_choice_with_the_same_number(self):
        old = self.search({'max_price': 5000}).json['suggestions'][0]['message']
        self.search({'max_price': 5000, 'categories': ['Modern']})
        response, _ = self.ask(old)
        self.assertEqual(response.status_code, 422)

    def test_compare_selected_favourites_uses_current_record_values(self):
        Favourites.add(3, 1); Favourites.add(3, 2)
        get_db().execute('UPDATE idp SET price=20000 WHERE id=2');get_db().commit()
        response, _ = self.ask('Compare my favourites')
        self.assertEqual({p['id'] for p in response.json['comparison_choices']}, {1, 2})
        response, model = self.ask('Compare saved projects 1 and 2')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p['price'] for p in response.json['comparison']], [10000, 20000])
        self.assertIn('S$10,000 less', ' '.join(response.json['comparison_summary']))
        model.assert_not_called()

    def test_comparison_rejects_unselected_other_customer_and_unavailable_projects(self):
        Favourites.add(3, 1); Favourites.add(3, 2);Favourites.add(5, 3)
        self.ask('Compare my favourites')
        for text in ('Compare saved projects 1 and 3', 'Compare saved projects 1 and 1',
                     'Compare saved projects 1 and 9999999999999999999'):
            with self.subTest(text=text):
                response, _ = self.ask(text)
                self.assertEqual(response.status_code, 422)
        get_db().execute("UPDATE idp SET approval_status='rejected' WHERE id=2");get_db().commit()
        response, _ = self.ask('Compare saved projects 1 and 2')
        self.assertEqual(response.status_code, 422)

    def test_smart_controls_keep_authentication_and_form_token_checks(self):
        self.assertEqual(self.client.post('/chat/message', data={'message': 'Remember my search preferences'}).status_code, 400)
        self.login(4)
        self.assertEqual(self.ask('Remember my search preferences')[0].status_code, 403)
        self.client.get('/auth/logout')
        self.assertEqual(self.ask('Compare my favourites')[0].status_code, 401)

    def test_preferences_are_not_saved_or_advertised(self):
        before = [tuple(r) for r in get_db().execute('SELECT name FROM sqlite_master ORDER BY name')]
        response, model = self.ask('Remember my search preferences')
        self.assertEqual(response.status_code, 200)
        self.assertIn('do not save preferences', response.json['reply'])
        model.assert_not_called()
        self.assertEqual(before, [tuple(r) for r in get_db().execute('SELECT name FROM sqlite_master ORDER BY name')])
        self.assertNotIn(b'chat-preferences', self.client.get('/chat/').data)

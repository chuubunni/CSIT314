# C18: AI customer chat assistant, search results and relevant page navigation.
"""C18: actual Flask routes and SQLite queries, with no live Google calls."""
from io import BytesIO
import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from story_fixture import StoryFixture
from idfinder.db import get_db
from idfinder.services.gemini_chat import GeminiChat, ChatbotUnavailable
from idfinder.services.chatbot_state import ChatbotState


def action(intent='help', **values):
    data = {'intent': intent, 'filters': {}, 'inherit_filters': False,
            'designer_name': None, 'result_number': None, 'page': None,
            'topic': 'search', 'question': None}
    data.update(values)
    return data


class ChatbotTests(StoryFixture):
    def setUp(self):
        super().setUp()
        self.app.config.update(GEMINI_API_KEY='test-only-not-a-real-key')
        self.login(3)
        self.csrf = self.token('/chat/')
        get_db().execute('UPDATE idp SET price=8000 WHERE id=1')
        get_db().execute('UPDATE idp SET price=15000 WHERE id=2')
        get_db().execute('UPDATE idp SET price=40000 WHERE id=3')
        get_db().commit()

    def post(self, interpretation=None, text='Find projects', **values):
        with patch.object(GeminiChat, 'interpret', return_value=interpretation or action()) as mocked:
            response = self.client.post('/chat/message', data={'message': text, 'form_token': self.csrf, **values})
        return response, mocked

    def test_customer_page_and_homepage_navigation(self):
        page = self.client.get('/chat/')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Google Gemini', page.data)
        self.assertIn(b'/chat/', self.client.get('/').data)
        self.assertNotIn(b'test-only-not-a-real-key', page.data)
        self.assertEqual(page.headers['Cache-Control'], 'no-store')

    def test_guest_and_role_restrictions(self):
        self.client.get('/auth/logout')
        self.assertEqual(self.client.get('/chat/').status_code, 302)
        self.assertEqual(self.client.post('/chat/message').status_code, 401)
        for role_id in (1, 4):
            self.login(role_id)
            self.assertEqual(self.client.get('/chat/').status_code, 403)
            self.assertEqual(self.client.post('/chat/message').status_code, 403)

    def test_post_only_and_csrf_before_provider(self):
        self.assertEqual(self.client.get('/chat/message').status_code, 405)
        for token in ('', 'wrong'):
            response, mocked = self.post(form_token=token)
            self.assertEqual(response.status_code, 400)
            self.assertTrue(response.is_json)
            mocked.assert_not_called()

    def test_message_length_and_empty_input(self):
        for text in ('', '  ', 'x' * 601):
            response, mocked = self.post(text=text)
            self.assertEqual(response.status_code, 400)
            mocked.assert_not_called()

    def test_oversized_request(self):
        response, mocked = self.post(text='x' * 9000)
        self.assertEqual(response.status_code, 413)
        mocked.assert_not_called()

    def test_real_project_filtering_and_generated_links(self):
        response, _ = self.post(action('search_projects', filters={
            'property_type': 'HDB', 'max_price': 10000, 'category': 'Modern'}))
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['projects'][0]['id'], 1)
        self.assertEqual(data['projects'][0]['url'], '/projects/1')
        self.assertEqual(data['filters']['max_price'], 10000)

    def test_follow_up_inherits_and_new_search_replaces_filters(self):
        self.post(action('search_projects', filters={'property_type': 'HDB', 'category': 'Modern'}))
        response, mocked = self.post(action('search_projects', filters={'max_price': 10000}, inherit_filters=True), text='Only below 10000')
        self.assertEqual(response.get_json()['total'], 1)
        self.assertEqual(response.get_json()['filters']['category'], 'Modern')
        self.assertIn('previous_filters', mocked.call_args.args[1])
        response, _ = self.post(action('search_projects', filters={}))
        self.assertEqual(response.get_json()['total'], 3)
        self.assertEqual(response.get_json()['filters'], {})

    def test_subtype_filters(self):
        response, _ = self.post(action('search_projects', filters={'property_type': 'HDB', 'subtype_name': '2-Room'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['total'], 3)

    def test_invalid_filters_fail_instead_of_broadening_search(self):
        for filters in ({'property_type': 'Unknown'}, {'category': 'Inactive'},
                        {'subtype_name': 'Nonexistent'}, {'max_price': -1},
                        {'max_price': True}, {'max_price': '10000'},
                        {'min_price': 50000, 'max_price': 10000},
                        {'property_type': 'Condo', 'subtype_name': '2-Room'},
                        {'sql': 'DROP TABLE user'}):
            # Each case gets a clean limiter, not a new account or production bypass.
            self.app.extensions['chatbot_state'] = ChatbotState()
            response, _ = self.post(action('search_projects', filters=filters))
            self.assertEqual(response.status_code, 422, filters)

    def test_no_results_and_literal_sql_like_characters(self):
        for keyword in ("' OR 1=1 --", '%', '_', 'nonexistent'):
            response, _ = self.post(action('search_projects', filters={'keyword': keyword}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['projects'], [])
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM idp').fetchone()[0], 3)

    def test_designer_search_and_known_navigation(self):
        response, _ = self.post(action('search_designers', designer_name='designer'))
        data = response.get_json()
        self.assertEqual(len(data['designers']), 2)
        self.assertTrue(data['actions'][0]['url'].startswith('/designers?name='))
        self.assertEqual(data['designers'][0]['company_name'], 'Studio A')

    def test_previous_result_reference_and_deleted_project(self):
        response, _ = self.post(action('search_projects'))
        second_id = response.get_json()['projects'][1]['id']
        response, _ = self.post(action('project_details', result_number=2))
        self.assertEqual(response.get_json()['projects'][0]['id'], second_id)
        get_db().execute('DELETE FROM idp WHERE id=?', (second_id,)); get_db().commit()
        response, _ = self.post(action('project_details', result_number=2))
        self.assertEqual(response.status_code, 422)

    def test_out_of_range_and_missing_result_reference(self):
        for number in (None, 1, -1, True):
            response, _ = self.post(action('project_details', result_number=number))
            self.assertEqual(response.status_code, 422)

    def test_favourites_profile_and_home_links(self):
        for page, path in [('favourites', '/favourites/'), ('profile', '/customer/profile'), ('home', '/')]:
            response, _ = self.post(action('navigate', page=page))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['actions'][0]['url'], path)

    def test_external_or_privileged_destination_is_rejected(self):
        for page in ('https://evil.example', '//evil.example', 'platform.dashboard', ['profile']):
            response, _ = self.post(action('navigate', page=page))
            self.assertEqual(response.status_code, 422)

    def test_help_uses_grounded_template(self):
        response, _ = self.post(action('help', topic='saving'))
        self.assertIn('Save to favourites', response.get_json()['reply'])
        self.assertEqual(response.get_json()['actions'][0]['url'], '/favourites/')

    def test_missing_key_returns_safe_setup_error(self):
        self.app.config['GEMINI_API_KEY'] = ''
        response = self.client.post('/chat/message', data={'message': 'Hello', 'form_token': self.csrf})
        self.assertEqual(response.status_code, 503)
        self.assertIn('not configured', response.get_json()['reply'])

    def test_usage_limit_and_reset_cannot_bypass_it(self):
        for _ in range(10):
            self.assertEqual(self.post()[0].status_code, 200)
        self.assertEqual(self.client.post('/chat/reset', data={'form_token': self.csrf}).status_code, 200)
        response, mocked = self.post()
        self.assertEqual(response.status_code, 429)
        mocked.assert_not_called()

    def test_reset_clears_filters_and_result_context(self):
        self.post(action('search_projects', filters={'max_price': 10000}))
        self.client.post('/chat/reset', data={'form_token': self.csrf})
        response, mocked = self.post(action('project_details', result_number=1))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(mocked.call_args.args[1]['previous_results'], [])

    def test_customers_have_separate_conversations(self):
        self.post(action('search_projects', filters={'max_price': 10000}))
        self.login(5); self.csrf = self.token('/chat/')
        response, mocked = self.post(action('project_details', result_number=1))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(mocked.call_args.args[1]['previous_filters'], {})

    def test_untrusted_output_types(self):
        for output in (['not an action'], action('help', topic=['bad']), action('execute_sql'),
                       action('search_projects', filters=[]), action('search_projects', inherit_filters='true')):
            response, _ = self.post(output)
            self.assertEqual(response.status_code, 422)

    def test_chat_does_not_write_business_records(self):
        before = [tuple(r) for r in get_db().execute('SELECT * FROM favourite_idp')]
        self.post(action('help', topic='saving'))
        self.post(action('navigate', page='profile'))
        self.post(action('search_projects'))
        self.assertEqual(before, [tuple(r) for r in get_db().execute('SELECT * FROM favourite_idp')])

    def test_widget_appears_once_on_every_customer_page(self):
        for path in ('/', '/customer/profile', '/customer/profile/edit', '/favourites/', '/designers', '/projects/1', '/chat/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data.count(b'id="chatbot"'), 1)
                self.assertIn(b'id="chat-launcher"', response.data)
                self.assertIn(b'id="chat-minimise"', response.data)

    def test_widget_hidden_for_guests_and_other_roles(self):
        self.client.get('/auth/logout')
        self.assertNotIn(b'id="chatbot"', self.client.get('/').data)
        for user_id in (1, 4):
            self.login(user_id)
            self.assertNotIn(b'id="chatbot"', self.client.get('/').data)

    def test_history_restores_messages_and_result_links_after_navigation(self):
        self.post(action('search_projects', filters={'max_price': 10000}), text='Projects below 10000')
        self.client.get('/customer/profile')
        history = self.client.get('/chat/history')
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.headers['Cache-Control'], 'no-store')
        entries = history.get_json()['messages']
        self.assertEqual(entries[0]['text'], 'Projects below 10000')
        self.assertEqual(entries[1]['data']['projects'][0]['url'], '/projects/1')
        response, _ = self.post(action('project_details', result_number=1))
        self.assertEqual(response.status_code, 200)

    def test_history_is_private_and_reset_removes_transcript(self):
        self.post(action('help', topic='saving'))
        self.assertEqual(len(self.client.get('/chat/history').get_json()['messages']), 2)
        self.client.post('/chat/reset', data={'form_token': self.csrf})
        self.assertEqual(self.client.get('/chat/history').get_json()['messages'], [])
        self.post(action('help', topic='saving'))
        self.login(5)
        self.assertEqual(self.client.get('/chat/history').get_json()['messages'], [])
        self.client.get('/auth/logout')
        self.assertEqual(self.client.get('/chat/history').status_code, 401)
        self.login(1)
        self.assertEqual(self.client.get('/chat/history').status_code, 403)

    def test_restoring_history_does_not_call_gemini_or_consume_limit(self):
        self.post(action('help'))
        with patch.object(GeminiChat, 'interpret') as interpreter:
            for _ in range(12):
                self.assertEqual(self.client.get('/chat/history').status_code, 200)
            interpreter.assert_not_called()
        self.assertEqual(self.post()[0].status_code, 200)

    def test_session_history_expires(self):
        self.post(action('help'))
        store = self.app.extensions['chatbot_state']
        for key, entry in list(store.conversations.items()):
            store.conversations[key] = (entry[0] - 1801, entry[1])
        self.assertEqual(self.client.get('/chat/history').get_json()['messages'], [])

    def test_transport_sends_key_only_in_header_and_no_account_data(self):
        reply = action('navigate', page='profile')
        payload = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(reply)}]}}]}
        with patch('idfinder.services.gemini_chat.build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()
            result = GeminiChat('secret-example', 'gemini-2.5-flash-lite').interpret('Open my profile', {})
            request = opener.return_value.open.call_args.args[0]
        self.assertEqual(result['page'], 'profile')
        self.assertNotIn('secret-example', request.full_url)
        self.assertNotIn(b'secret-example', request.data)
        self.assertEqual(request.get_header('X-goog-api-key'), 'secret-example')

    def test_transport_handles_http_errors_without_leaking_details(self):
        for code, expected in [(429, 429), (403, 503), (500, 503)]:
            with patch('idfinder.services.gemini_chat.build_opener') as opener:
                opener.return_value.open.side_effect = HTTPError('https://example.test', code, 'sensitive-provider-detail', {}, BytesIO(b'private'))
                with self.assertRaises(ChatbotUnavailable) as result:
                    GeminiChat('secret-example', 'gemini-2.5-flash-lite').interpret('Hello', {})
                self.assertEqual(result.exception.status, expected)
                self.assertNotIn('sensitive-provider-detail', str(result.exception))

    def test_transport_invalid_json_timeout_and_blocked_output(self):
        for value in (b'not json', b'{}', json.dumps({'candidates': [{'finishReason': 'SAFETY'}]}).encode()):
            with patch('idfinder.services.gemini_chat.build_opener') as opener:
                opener.return_value.open.return_value.__enter__.return_value.read.return_value = value
                with self.assertRaises(ChatbotUnavailable):
                    GeminiChat('key', 'model').interpret('Hello', {})
        with patch('idfinder.services.gemini_chat.build_opener') as opener:
            opener.return_value.open.side_effect = URLError('private connection details')
            with self.assertRaises(ChatbotUnavailable) as result:
                GeminiChat('key', 'model').interpret('Hello', {})
            self.assertNotIn('private connection details', str(result.exception))

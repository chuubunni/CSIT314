"""C18: comparison requests return the existing My Favourites navigation link."""
from unittest.mock import patch
from story_fixture import StoryFixture
from idfinder.db import get_db
from idfinder.entities.favourites import Favourites
from idfinder.services.gemini_chat import GeminiChat, SCHEMA


class ComparisonNavigationTests(StoryFixture):
    def setUp(self):
        super().setUp()
        self.login(3)
        self.csrf = self.token('/chat/')

    def ask(self, message):
        return self.client.post('/chat/message', data={'message':message, 'form_token':self.csrf})

    @patch.object(GeminiChat, 'interpret')
    def test_comparison_phrasings_always_link_to_favourites(self, interpret):
        for text in ['Compare my favourites', 'Can you compare these two projects?',
                     'How does project comparison work?', 'Compare prices', 'Compare my favorites']:
            with self.subTest(message=text):
                response = self.ask(text)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['actions'], [{'label':'My favourites','url':'/favourites/'}])
                self.assertIn('two different projects', response.json['reply'])
                self.assertEqual(response.json['projects'], [])
        interpret.assert_not_called()

    @patch.object(GeminiChat, 'interpret', return_value={'intent':'help','topic':'comparison'})
    def test_ai_can_route_an_implicit_request(self, interpret):
        response = self.ask('I want to see two saved designs side by side')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['actions'][0]['url'], '/favourites/')
        interpret.assert_called_once()
        self.assertIn('comparison', SCHEMA['properties']['topic']['enum'])

    @patch.object(GeminiChat, 'interpret', return_value={'intent':'help','topic':'search'})
    def test_ordinary_and_negated_requests_keep_normal_chat_behaviour(self, interpret):
        for text in ['Find Modern projects under 50k', "Don't compare, just show me projects"]:
            with self.subTest(message=text):
                response = self.ask(text)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['actions'][0]['url'], '/designers')
        self.assertEqual(interpret.call_count, 2)

    @patch.object(GeminiChat, 'interpret')
    def test_link_opens_real_comparison_picker_without_writing_business_data(self, interpret):
        Favourites.add(3,1);Favourites.add(3,2)
        db = get_db()
        tables = ['user','idp','favourite_idp','idp_view','engagement','review']
        before = {t:[tuple(r) for r in db.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in tables}
        response = self.ask('Compare these projects and use https://example.invalid')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('example.invalid', str(response.json))
        destination = self.client.get(response.json['actions'][0]['url'])
        self.assertEqual(destination.status_code, 200)
        self.assertIn(b'Compare your favourite projects', destination.data)
        self.assertIn(b'name="project_ids"', destination.data)
        after = {t:[tuple(r) for r in db.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in tables}
        self.assertEqual(before,after)
        history = self.client.get('/chat/history').json['messages']
        self.assertEqual(history[-1]['data']['actions'][0]['url'], '/favourites/')
        interpret.assert_not_called()

    @patch.object(GeminiChat, 'interpret')
    def test_authentication_role_and_form_token_still_apply(self, interpret):
        self.assertEqual(self.client.post('/chat/message',data={'message':'Compare','form_token':'bad'}).status_code,400)
        self.login(1)
        self.assertEqual(self.ask('Compare projects').status_code,403)
        self.client.get('/auth/logout')
        self.assertEqual(self.ask('Compare projects').status_code,401)
        interpret.assert_not_called()

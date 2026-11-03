# C18: multi-style and title/description search through real Flask/SQLite flows.
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from story_fixture import StoryFixture
from idfinder.db import get_db
from idfinder.services.gemini_chat import GeminiChat, FIELDS, SYSTEM
from idfinder.services.chatbot_state import ChatbotState


class SmartSearchTests(StoryFixture):
    def setUp(self):
        super().setUp()
        self.app.config['GEMINI_API_KEY'] = 'test-only'
        db = get_db()
        db.execute('INSERT INTO category(id,name,active) VALUES(5,?,1)', ('Japandi',))
        db.execute('INSERT INTO idp_category VALUES(1,5)')
        db.execute('INSERT INTO idp_category VALUES(3,5)')
        db.execute('UPDATE idp SET title=?,description=?,price=40000 WHERE id=1', ('Bishan Loft', 'Warm oak cabinetry'))
        db.execute('UPDATE idp SET title=?,description=?,price=80000 WHERE id=2', ('Harbour Home', 'A renovation in BISHAN with concealed storage'))
        db.execute('UPDATE idp SET title=?,description=?,price=20000 WHERE id=3', ('Tampines Retreat', 'Light-filled living spaces'))
        # C18: deliberately different housing branches catch accidental cross-products.
        four = db.execute("SELECT id FROM property_subtype WHERE name='4-Room'").fetchone()[0]
        terrace = db.execute("SELECT id FROM property_subtype WHERE name='Terrace House'").fetchone()[0]
        db.execute('UPDATE idp SET property_subtype_id=? WHERE id=1', (four,))
        db.execute("UPDATE idp SET property_type='Landed',property_subtype_id=? WHERE id=2", (terrace,))
        db.commit()
        self.login(3)
        self.csrf = self.token('/chat/')

    def ask(self, filters, text=None, inherit=False):
        if text is None:
            if inherit:
                text = 'Only refine those results'
            elif filters.get('category_mode') == 'all':
                text = 'Projects with both styles'
            elif filters.get('keyword_mode') == 'all':
                text = 'Projects mentioning both content terms'
            else:
                text = 'Find projects'
        output = {'intent': 'search_projects', 'filters': filters, 'inherit_filters': inherit}
        with patch.object(GeminiChat, 'interpret', return_value=output):
            return self.client.post('/chat/message', data={'message': text, 'form_token': self.csrf})

    def test_either_style_returns_union_without_duplicate_projects(self):
        data = self.ask({'categories': ['Modern', 'Japandi'], 'category_mode': 'any'}, 'Modern or Japandi projects').get_json()
        self.assertEqual(data['total'], 3)
        self.assertEqual({p['id'] for p in data['projects']}, {1, 2, 3})
        self.assertEqual(len(data['projects']), 3)
        self.assertIn('Modern OR Japandi', data['reply'])

    def test_both_styles_requires_both_tags_not_words_in_description(self):
        get_db().execute('UPDATE idp SET description=? WHERE id=2', ('Modern and Japandi inspiration in Bishan',));get_db().commit()
        data = self.ask({'categories': ['Modern', 'Japandi'], 'category_mode': 'all'}, 'Projects with both styles').get_json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['projects'][0]['id'], 1)
        self.assertIn('Modern AND Japandi', data['reply'])

    def test_style_names_are_normalised_and_deduplicated(self):
        data = self.ask({'categories': ['modern', 'MODERN', 'japandi'], 'category_mode': 'all'}).get_json()
        self.assertEqual(data['filters']['categories'], ['Modern', 'Japandi'])
        self.assertEqual(data['total'], 1)

    def test_bishan_matches_title_or_description_case_insensitively(self):
        data = self.ask({'keyword': 'bIsHaN'}, 'All projects mentioning Bishan').get_json()
        self.assertEqual(data['total'], 2)
        self.assertEqual({p['id'] for p in data['projects']}, {1, 2})
        self.assertIn('BISHAN', next(p['description'] for p in data['projects'] if p['id'] == 2))

    def test_keyword_combines_with_styles_housing_and_budget(self):
        data = self.ask({'keyword': 'Bishan', 'categories': ['Modern', 'Japandi'], 'category_mode': 'any', 'property_type': 'HDB', 'max_price': 50000}).get_json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['projects'][0]['id'], 1)

    def test_description_phrase_search(self):
        data = self.ask({'keyword': 'concealed storage'}).get_json()
        self.assertEqual([p['id'] for p in data['projects']], [2])

    def test_follow_up_keeps_place_and_styles_then_changes_any_to_all(self):
        self.ask({'keyword': 'Bishan', 'categories': ['Modern', 'Japandi'], 'category_mode': 'any'})
        data = self.ask({'category_mode': 'all', 'max_price': 50000}, 'Both styles, under 50k', True).get_json()
        self.assertEqual(data['filters']['keyword'], 'Bishan')
        self.assertEqual(data['filters']['categories'], ['Modern', 'Japandi'])
        self.assertEqual(data['total'], 1)

    def test_new_category_replaces_inherited_styles_and_empty_list_clears_them(self):
        self.ask({'keyword': 'Bishan', 'categories': ['Modern', 'Japandi'], 'category_mode': 'all'})
        data = self.ask({'category': 'Minimalist'}, inherit=True).get_json()
        self.assertEqual(data['filters']['categories'], ['Minimalist'])
        self.assertNotIn('Modern', data['filters']['categories'])
        data = self.ask({'categories': []}, inherit=True).get_json()
        self.assertNotIn('category_ids', data['filters'])
        self.assertEqual(data['total'], 2)

    def test_unknown_styles_types_and_modes_are_rejected_not_partly_applied(self):
        invalid = [{'categories': ['Modern', 'Unknown']}, {'categories': 'Modern'}, {'categories': [None]},
                   {'categories': [True]}, {'categories': [['Modern']]}, {'categories': ['Modern'] * 11},
                   {'categories': ['Modern'], 'category_mode': 'either'}, {'category_mode': 'all'},
                   {'categories': ['Modern'], 'category_mode': ['all']},
                   {'category': 'Modern', 'categories': ['Japandi']}]
        for filters in invalid:
            self.app.extensions['chatbot_state'] = ChatbotState()
            with self.subTest(filters=filters):self.assertEqual(self.ask(filters).status_code, 422)

    def test_both_mode_has_honest_empty_state(self):
        data = self.ask({'categories': ['Modern', 'Minimalist'], 'category_mode': 'all'}).get_json()
        self.assertEqual(data['total'], 0)
        self.assertIn('No project has every requested style tag', data['reply'])
        self.assertEqual(data['actions'], [])

    def test_complete_results_link_retains_every_filter_and_needs_no_ai(self):
        data = self.ask({'categories': ['Modern', 'Japandi'], 'category_mode': 'any', 'keyword': 'Bishan', 'min_price': 0, 'max_price': 90000}).get_json()
        url = data['actions'][0]['url'];query = parse_qs(urlsplit(url).query)
        self.assertEqual(query['category'], ['Modern', 'Japandi'])
        self.assertEqual(query['keyword'], ['Bishan'])
        with patch.object(GeminiChat, 'interpret') as ai:
            page = self.client.get(url)
            self.assertEqual(page.status_code, 200)
            self.assertIn(b'Bishan Loft', page.data);self.assertIn(b'Harbour Home', page.data)
            self.assertNotIn(b'Tampines Retreat', page.data)
            ai.assert_not_called()

    def test_all_matching_projects_can_be_reached_beyond_chat_preview(self):
        db = get_db()
        for i in range(4, 29):
            db.execute('INSERT INTO idp(id,designer_id,title,description,property_type,price,status) VALUES(?,1,?,?,?,10000,?)',
                       (i, f'Bishan Residence {i}', 'A Bishan project', 'HDB', 'completed'))
            db.execute('INSERT INTO idp_category VALUES(?,1)', (i,))
        db.commit()
        data = self.ask({'keyword': 'Bishan'}).get_json()
        self.assertEqual(data['total'], 27)
        self.assertEqual(len(data['projects']), 6)
        self.assertEqual(self.client.get(data['actions'][0]['url']).status_code, 200)
        first = self.client.get('/chat/projects?keyword=Bishan')
        second = self.client.get('/chat/projects?keyword=Bishan&page=2')
        self.assertEqual(first.data.count(b'<article class="c18-project-result">'), 20)
        self.assertEqual(second.data.count(b'<article class="c18-project-result">'), 7)
        self.assertIn(b'keyword=Bishan', first.data)
        self.assertEqual(self.client.get('/chat/projects?keyword=Bishan&page=3').status_code, 404)

    def test_result_page_validates_queries_and_respects_customer_access(self):
        for query in ('mode=sql&category=Modern', 'min_price=-1', 'page=0', 'page=no', 'max_price=abc',
                      'sql=DROP', 'category=Inactive', 'category=Modern&category=Unknown', 'keyword_mode=sql'):
            with self.subTest(query=query):self.assertEqual(self.client.get('/chat/projects?' + query).status_code, 400)
        self.client.get('/auth/logout')
        self.assertEqual(self.client.get('/chat/projects?keyword=Bishan').status_code, 302)
        self.login(1);self.assertEqual(self.client.get('/chat/projects').status_code, 403)

    def test_result_page_escapes_project_text_and_search_terms(self):
        get_db().execute('UPDATE idp SET title=? WHERE id=1', ('Bishan <script>alert(1)</script>',));get_db().commit()
        page = self.client.get('/chat/projects?keyword=Bishan')
        self.assertNotIn(b'<script>alert(1)</script>', page.data)
        self.assertIn(b'&lt;script&gt;alert(1)&lt;/script&gt;', page.data)

    def test_provider_contract_includes_style_list_and_content_examples(self):
        self.assertEqual(FIELDS['categories']['type'], 'ARRAY')
        self.assertEqual(FIELDS['category_mode']['enum'], ['any', 'all'])
        self.assertIn('Bishan', SYSTEM)
        self.assertIn('titles OR descriptions', SYSTEM)

    def test_read_only_search_does_not_alter_favourites_or_business_records(self):
        db = get_db()
        tables=['user','idp','idp_category','favourite_idp','idp_view']
        before={t:[tuple(r) for r in db.execute('SELECT * FROM '+t)] for t in tables}
        self.ask({'keyword': 'Bishan', 'categories': ['Modern', 'Japandi'], 'category_mode': 'all'})
        self.client.get('/chat/projects?keyword=Bishan&category=Modern&category=Japandi&mode=all')
        self.assertEqual(before,{t:[tuple(r) for r in db.execute('SELECT * FROM '+t)] for t in tables})

    def test_four_room_or_landed_returns_both_valid_housing_branches(self):
        data = self.ask({'housing_options': [{'subtype_name': '4-Room'}, {'property_type': 'Landed'}]}, '4 room and Landed').get_json()
        self.assertEqual(data['total'], 2)
        self.assertEqual({p['id'] for p in data['projects']}, {1, 2})
        self.assertIn('HDB 4-Room OR Landed', data['reply'])
        self.assertNotIn('property_type', data['filters'])
        self.assertEqual(self.client.get(data['actions'][0]['url']).status_code, 200)

    def test_subtype_alternatives_do_not_leak_other_subtypes(self):
        data = self.ask({'housing_options': [{'subtype_name': '4-Room'}, {'subtype_name': '2-Room'}]}).get_json()
        self.assertEqual({p['id'] for p in data['projects']}, {1, 3})

    def test_bishan_or_lentor_matches_each_place_in_either_content_field(self):
        get_db().execute('UPDATE idp SET title=? WHERE id=3', ('Lentor Retreat',));get_db().commit()
        data = self.ask({'keywords': ['Bishan', 'Lentor'], 'keyword_mode': 'any'}, 'Bishan and Lentor').get_json()
        self.assertEqual(data['total'], 3)
        self.assertEqual({p['id'] for p in data['projects']}, {1, 2, 3})
        self.assertIn('Bishan OR Lentor', data['reply'])
        self.assertEqual(parse_qs(urlsplit(data['actions'][0]['url']).query)['keyword'], ['Bishan', 'Lentor'])
        page = self.client.get(data['actions'][0]['url'])
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Lentor Retreat', page.data)

    def test_all_content_terms_can_match_across_title_and_description(self):
        get_db().execute('UPDATE idp SET description=? WHERE id=1', ('A design inspired by Lentor homes',));get_db().commit()
        data = self.ask({'keywords': ['Bishan', 'Lentor'], 'keyword_mode': 'all'}).get_json()
        self.assertEqual([p['id'] for p in data['projects']], [1])
        self.assertIn('Bishan AND Lentor', data['reply'])

    def test_housing_styles_content_alternatives_and_budget_compose_correctly(self):
        filters = {'housing_options': [{'subtype_name': '4-Room'}, {'property_type': 'Landed'}],
                   'categories': ['Modern', 'Japandi'], 'category_mode': 'any',
                   'keywords': ['Bishan', 'Lentor'], 'keyword_mode': 'any', 'max_price': 50000}
        data = self.ask(filters).get_json()
        self.assertEqual([p['id'] for p in data['projects']], [1])
        page = self.client.get(data['actions'][0]['url'])
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Bishan Loft', page.data)
        self.assertNotIn(b'Harbour Home', page.data)

    def test_follow_up_preserves_alternative_groups_and_can_clear_them(self):
        self.ask({'housing_options': [{'subtype_name': '4-Room'}, {'property_type': 'Landed'}], 'keywords': ['Bishan', 'Lentor']})
        data = self.ask({'max_price': 50000}, inherit=True).get_json()
        self.assertEqual(len(data['filters']['housing_options']), 2)
        self.assertEqual(data['filters']['keywords'], ['Bishan', 'Lentor'])
        self.assertEqual([p['id'] for p in data['projects']], [1])
        data = self.ask({'housing_options': [], 'keywords': []}, inherit=True).get_json()
        self.assertNotIn('housing_options', data['filters']);self.assertNotIn('keywords', data['filters'])
        self.assertEqual(data['total'], 2)  # Retained budget.

    def test_invalid_housing_and_content_lists_fail_instead_of_dropping_terms(self):
        invalid = [{'housing_options': 'Landed'}, {'housing_options': [{}]}, {'housing_options': [None]},
                   {'housing_options': [{'property_type': 'Landed', 'subtype_name': '4-Room'}]},
                   {'housing_options': [{'property_type': 'Unknown'}]}, {'housing_options': [{'sql': 'drop'}]},
                   {'keywords': 'Bishan'}, {'keywords': [None]}, {'keywords': [1]},
                   {'keywords': ['Bishan'] * 9}, {'keyword_mode': 'all'},
                   {'keywords': ['Bishan'], 'keyword_mode': True},
                   {'keyword': 'Bishan', 'keywords': ['Lentor']}]
        for filters in invalid:
            self.app.extensions['chatbot_state'] = ChatbotState()
            with self.subTest(filters=filters):self.assertEqual(self.ask(filters).status_code, 422)

    def test_content_alternatives_escape_sql_wildcards_and_do_not_inject(self):
        data = self.ask({'keywords': ["' OR 1=1 --", '%', '_'], 'keyword_mode': 'any'}).get_json()
        self.assertEqual(data['total'], 0)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM idp').fetchone()[0], 3)

    def test_search_page_rejects_malformed_housing_and_preserves_english_case_matching(self):
        for query in ('housing=broken', 'housing=[]', 'housing=%7B%22sql%22%3A%22drop%22%7D', 'keyword_mode=all'):
            self.assertEqual(self.client.get('/chat/projects?' + query).status_code, 400)
        page = self.client.get('/chat/projects?keyword=bIsHaN&keyword=lEnToR&keyword_mode=any')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Harbour Home', page.data)

    def test_plain_style_list_overrides_erroneous_model_all(self):
        data = self.ask({'categories': ['Japandi', 'Modern'], 'category_mode': 'all'}, 'japandi and modern').get_json()
        self.assertEqual(data['filters']['category_mode'], 'any')
        self.assertEqual(data['total'], 3)
        self.assertIn('Japandi OR Modern', data['reply'])

    def test_all_projects_does_not_mean_all_style_tags(self):
        data = self.ask({'categories': ['Modern', 'Japandi'], 'category_mode': 'all'}, 'Show all Modern and Japandi projects').get_json()
        self.assertEqual(data['filters']['category_mode'], 'any')
        self.assertEqual(data['total'], 3)

    def test_fresh_housing_query_cannot_inherit_previous_both_styles(self):
        self.ask({'categories': ['Modern', 'Japandi'], 'category_mode': 'all'}, 'Projects with both Modern and Japandi')
        output = {'intent': 'search_projects', 'filters': {'housing_options': [{'subtype_name': '4-Room'}, {'property_type': 'Landed'}]}, 'inherit_filters': True}
        with patch.object(GeminiChat, 'interpret', return_value=output) as ai:
            response = self.client.post('/chat/message', data={'message': '4-room and Landed projects', 'form_token': self.csrf})
        data = response.get_json()
        self.assertEqual(data['total'], 2)
        self.assertNotIn('categories', data['filters'])
        self.assertEqual(ai.call_args.args[1]['previous_filters'], {})
        self.assertEqual(ai.call_args.args[1]['recent_messages'], [])
        self.assertEqual(ai.call_args.args[1]['request_scope'], 'new_search')

    def test_plain_places_use_any_despite_erroneous_model_all_and_clear_old_budget(self):
        self.ask({'max_price': 100})
        get_db().execute('UPDATE idp SET title=? WHERE id=3', ('Lentor Retreat',));get_db().commit()
        data = self.ask({'keywords': ['Bishan', 'Lentor'], 'keyword_mode': 'all'}, 'Bishan and Lentor', inherit=True).get_json()
        self.assertEqual(data['filters']['keyword_mode'], 'any')
        self.assertNotIn('max_price', data['filters'])
        self.assertEqual(data['total'], 3)

    def test_explicit_all_in_one_group_does_not_force_other_group_to_all(self):
        data = self.ask({'categories': ['Modern', 'Japandi'], 'category_mode': 'all', 'keywords': ['Bishan', 'Lentor'], 'keyword_mode': 'all'}, 'Both Modern and Japandi in Bishan or Lentor').get_json()
        self.assertEqual(data['filters']['category_mode'], 'all')
        self.assertEqual(data['filters']['keyword_mode'], 'any')
        self.assertEqual(data['total'], 1)

    def test_budget_follow_up_keeps_explicit_previous_both_style_mode(self):
        self.ask({'categories': ['Modern', 'Japandi'], 'category_mode': 'all'}, 'Projects with both styles')
        data = self.ask({'max_price': 50000}, 'only below 50k', inherit=True).get_json()
        self.assertEqual(data['filters']['category_mode'], 'all')
        self.assertEqual(data['total'], 1)

    def test_either_styles_follow_up_releases_previous_all_mode(self):
        self.ask({'categories': ['Modern', 'Japandi'], 'category_mode': 'all'}, 'Projects with both styles')
        data = self.ask({'category_mode': 'all'}, 'either styles instead', inherit=True).get_json()
        self.assertEqual(data['filters']['category_mode'], 'any')
        self.assertEqual(data['total'], 3)

    def test_explicit_filter_removal_does_not_reinject_old_group_modes(self):
        self.ask({'categories': ['Modern', 'Japandi'], 'category_mode': 'all', 'keyword': 'Bishan'})
        output = {'intent': 'search_projects', 'filters': {}, 'inherit_filters': False}
        with patch.object(GeminiChat, 'interpret', return_value=output):
            response = self.client.post('/chat/message', data={'message': 'remove all filters', 'form_token': self.csrf})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['filters'], {})
        self.assertEqual(response.get_json()['total'], 3)

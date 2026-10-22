# C08: tests for the Customer branch only.
from story_fixture import StoryFixture
from idfinder.db import get_db
from idfinder.entities.favourites import Favourites
from urllib.parse import urlsplit, parse_qs


class C08Tests(StoryFixture):
    def test_c08_save_card_and_persistent_state(self):
        self.login(3)
        self.assertIn(b'action="/favourites/projects/1"',self.client.get('/').data)
        self.assertEqual(self.save().status_code,302)
        response=self.client.get('/')
        self.assertIn(b'Saved to favourites',response.data)
        self.assertNotIn(b'action="/favourites/projects/1"',response.data)
        self.assertEqual(Favourites.find_project_ids(3),{1})

    def test_c08_duplicate_save_is_idempotent(self):
        self.login(3);self.save();self.save()
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM favourite_idp').fetchone()[0],1)

    def test_c08_identity_cannot_be_forged(self):
        self.login(5);self.save(customer_id='3')
        self.assertEqual(Favourites.find_project_ids(5),{1})
        self.assertEqual(Favourites.find_project_ids(3),set())

    def test_c08_roles_and_public_browsing(self):
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertNotIn(b'>Save to favourites</button>',self.client.get('/').data)
        self.assertEqual(self.client.post('/favourites/projects/1').status_code,302)
        for user_id in [1,4]:
            self.login(user_id)
            self.assertEqual(self.client.post('/favourites/projects/1').status_code,403)
            self.assertNotIn(b'>Save to favourites</button>',self.client.get('/').data)

    def test_c08_form_token_and_post_only(self):
        self.login(3)
        self.assertEqual(self.client.post('/favourites/projects/1').status_code,400)
        self.assertEqual(self.client.post('/favourites/projects/1',data={'form_token':'wrong'}).status_code,400)
        self.assertEqual(self.client.get('/favourites/projects/1').status_code,405)
        self.assertEqual(Favourites.find_project_ids(3),set())

    def test_c08_missing_project_and_customer_profile(self):
        self.login(3);self.assertEqual(self.save(999).status_code,404)
        self.login(6);self.assertEqual(self.save().status_code,403)

    def test_c08_detail_save_and_fixed_redirect(self):
        self.login(3)
        self.assertIn(b'>Save to favourites</button>',self.client.get('/projects/1').data)
        response=self.save(return_to='detail',next='https://example.com')
        self.assertEqual(response.headers['Location'],'/projects/1')
        self.assertIn(b'Saved to favourites',self.client.get('/projects/1').data)

    def test_c08_preserves_housing_filters(self):
        self.login(3)
        subtype=get_db().execute('SELECT property_subtype_id FROM idp WHERE id=1').fetchone()[0]
        response=self.save(property_type='HDB',property_subtype_id=str(subtype),next='https://example.com')
        dest=urlsplit(response.headers['Location'])
        self.assertEqual(dest.netloc,'')
        self.assertEqual(parse_qs(dest.query),{'property_type':['HDB'],'property_subtype_id':[str(subtype)]})
        self.assertEqual(self.client.get(response.headers['Location']).status_code,200)

    def test_c08_invalid_project_id(self):
        self.login(3);self.assertEqual(self.save(0).status_code,400)

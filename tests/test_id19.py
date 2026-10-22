# ID19: tests for the ID-user branch only.
import sqlite3
from story_fixture import StoryFixture
from idfinder.db import get_db
from idfinder.controller.errors import ValidationError, PermissionDenied, NotFoundError


class ID19Tests(StoryFixture):
    def test_id19_bulk_replace_deduplicates_and_preserves_fields(self):
        before=tuple(get_db().execute('SELECT title,propertyType,price,status,property_subtype_id FROM idp WHERE id=1').fetchone())
        self.assertEqual(self.ctrl.update_selected_categories(1,['1','2','1'],['2','1','2']),2)
        self.assertEqual(self.categories(1),[1,2]);self.assertEqual(self.categories(2),[1,2])
        self.assertEqual(self.categories(3),[2])
        after=tuple(get_db().execute('SELECT title,propertyType,price,status,property_subtype_id FROM idp WHERE id=1').fetchone())
        self.assertEqual(before,after)
        self.ctrl.update_selected_categories(1,['1'],['2'])
        self.assertEqual(self.categories(1),[2])

    def test_id19_foreign_project_rejects_entire_selection(self):
        with self.assertRaises(PermissionDenied):self.ctrl.update_selected_categories(1,['1','3'],['2'])
        self.assertEqual(self.categories(1),[1])

    def test_id19_missing_project_rejects_entire_selection(self):
        with self.assertRaises(NotFoundError):self.ctrl.update_selected_categories(1,['1','999'],['2'])
        self.assertEqual(self.categories(1),[1])

    def test_id19_invalid_selections(self):
        for projects,categories in [([],['1']),(['1'],[]),(['bad'],['1']),(['-1'],['1']),(['1'],['3']),(['1'],['999']),(['1'],['bad'])]:
            with self.subTest(projects=projects,categories=categories):
                with self.assertRaises(ValidationError):self.ctrl.update_selected_categories(1,projects,categories)
                self.assertEqual(self.categories(1),[1])

    def test_id19_database_failure_rolls_back_all_writes(self):
        get_db().executescript("CREATE TRIGGER fail_second BEFORE INSERT ON idp_category WHEN NEW.idp_id=2 AND NEW.category_id=2 BEGIN SELECT RAISE(ABORT,'test failure'); END;")
        with self.assertRaises(sqlite3.IntegrityError):self.ctrl.update_selected_categories(1,['1','2'],['2'])
        self.assertEqual(self.categories(1),[1]);self.assertEqual(self.categories(2),[1])

    def test_id19_route_access_form_token_and_success(self):
        self.assertEqual(self.client.get('/portfolio/categories').status_code,302)
        self.login(3);self.assertEqual(self.client.get('/portfolio/categories').status_code,403)
        self.login(1);token=self.token('/portfolio/categories')
        self.assertEqual(self.client.post('/portfolio/categories',data={'idp_ids':['1'],'category_ids':['2']}).status_code,400)
        response=self.client.post('/portfolio/categories',data={'form_token':token,'idp_ids':['1','2'],'category_ids':['1','2']},follow_redirects=True)
        self.assertEqual(response.status_code,200);self.assertIn(b'Categories updated for 2 project(s).',response.data)
        self.assertEqual(self.categories(1),[1,2])

    def test_id19_form_validation_preserves_selection(self):
        self.login(1);token=self.token('/portfolio/categories')
        response=self.client.post('/portfolio/categories',data={'form_token':token,'idp_ids':'1'})
        self.assertIn(b'Select at least one active category.',response.data)
        self.assertIn(b'value="1" checked',response.data)
        self.assertEqual(self.categories(1),[1])

    def test_id19_form_shows_only_owned_projects(self):
        self.login(1);response=self.client.get('/portfolio/categories')
        self.assertIn(b'First',response.data);self.assertNotIn(b'Other designer',response.data)

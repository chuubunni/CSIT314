"""Merge checks: AI endpoint, current comparison and current portfolio sorting coexist."""
from story_fixture import StoryFixture
from idfinder.db import get_db
from idfinder.entities.favourites import Favourites


class CurrentPullMergeTests(StoryFixture):
    def test_only_one_image_analysis_endpoint_is_registered(self):
        rules = [r for r in self.app.url_map.iter_rules() if r.rule == '/api/analyze-image']
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].endpoint, 'image_analysis.analyze_image')
        self.assertNotIn('designer.analyze_image', self.app.view_functions)

    def test_current_customer_comparison_remains_available(self):
        Favourites.add(3, 1);Favourites.add(3, 2)
        self.login(3)
        page = self.client.get('/favourites/')
        self.assertIn(b'Compare your favourite projects', page.data)
        result = self.client.get('/favourites/compare?project_ids=1&project_ids=2')
        self.assertEqual(result.status_code, 200)
        self.assertIn(b'Comparison of your two saved projects', result.data)
        self.assertIn(b'First', result.data)
        self.assertIn(b'Second', result.data)
        self.login(5)
        self.assertEqual(self.client.get('/favourites/compare?project_ids=1&project_ids=2').status_code, 302)

    def test_portfolio_sorting_remains_functional(self):
        db = get_db()
        db.execute("UPDATE idp SET created='2026-10-01 09:00:00' WHERE id=1")
        db.execute("UPDATE idp SET created='2026-10-02 09:00:00' WHERE id=2")
        db.executemany('INSERT INTO idp_view(idp_id) VALUES (?)', [(1,), (1,), (1,), (2,)])
        db.commit()
        Favourites.add(3,1);Favourites.add(3,2);Favourites.add(5,2)
        self.assertEqual([r['id'] for r in self.ctrl.list_portfolio(1, sort_by='newest')], [2,1])
        self.assertEqual([r['id'] for r in self.ctrl.list_portfolio(1, sort_by='views')], [1,2])
        self.assertEqual([r['id'] for r in self.ctrl.list_portfolio(1, sort_by='favourites')], [2,1])
        self.login(1)
        html = self.client.get('/portfolio?sort_by=views').get_data(as_text=True)
        self.assertIn('Most viewed', html)
        self.assertIn('Most favourited', html)
        self.assertIn('AI Auto-Fill Assistant', self.client.get('/portfolio/new').get_data(as_text=True))

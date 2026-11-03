"""
Image duplication review feature tests.

Uses temporary databases and image files.

Run:
python -m unittest discover -s tests -p "test_image_review.py" -v
"""

import io
import sqlite3
import tempfile
import unittest

from contextlib import closing
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance
from werkzeug.datastructures import FileStorage

from idfinder import create_app
from idfinder.db import get_db, init_db
from idfinder.entities.image_review_schema import ImageReviewSchema
from idfinder.entities.image_review import ImageReview
from idfinder.entities.idp import IDP
from idfinder.entities.search import DesignerSearch
from idfinder.controller.image_review_controller import ImageReviewController
from idfinder.controller.portfolio_controller import PortfolioController
from idfinder.controller.errors import ValidationError, PermissionDenied
from idfinder.services.image_similarity import ImageSimilarity


class Fixtures:

    @staticmethod
    def scene(other=False):
        im = Image.new(
            'RGB',
            (600, 400),
            '#ddddca' if not other else '#7183a2'
        )

        d = ImageDraw.Draw(im)

        if not other:
            d.rectangle(
                (0, 290, 600, 400),
                fill='#a38565'
            )

            d.rectangle(
                (25, 35, 200, 220),
                fill='#7599aa'
            )

            d.line(
                (110, 35, 110, 220),
                fill='white',
                width=8
            )

            d.rectangle(
                (225, 170, 530, 310),
                fill='#425a55'
            )

            d.rectangle(
                (210, 230, 550, 320),
                fill='#586e64'
            )

            d.ellipse(
                (300, 300, 500, 350),
                fill='#8b502e'
            )

            d.line(
                (480, 40, 480, 160),
                fill='#333333',
                width=8
            )

            d.polygon(
                [(440, 65), (520, 65), (500, 30), (460, 30)],
                fill='#d2af38'
            )

        else:
            d.polygon(
                [(20, 20), (300, 250), (450, 25)],
                fill='#14224b'
            )

            d.ellipse(
                (40, 220, 370, 390),
                fill='#bb4137'
            )

            d.rectangle(
                (450, 200, 590, 390),
                fill='#edccee'
            )

            for i in range(10):
                d.line(
                    (i * 50, 0, 590 - i * 30, 400),
                    fill='#242b42',
                    width=5
                )

        return im

    @staticmethod
    def upload(image=None, name='room.png', format='PNG'):
        b = io.BytesIO()

        (image or Fixtures.scene()).save(
            b,
            format=format
        )

        b.seek(0)

        return FileStorage(
            stream=b,
            filename=name
        )


class ReviewTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        self.app = create_app({
            'TESTING': True,
            'DEMO_DATA': False,
            'SECRET_KEY': 'test',
            'DATABASE': str(self.root / 'test.sqlite'),
            'UPLOAD_FOLDER': str(self.root / 'uploads'),
            'REVIEW_EVIDENCE_FOLDER': str(self.root / 'evidence')
        })

        self.ctx = self.app.app_context()
        self.ctx.push()

        init_db()
        self.db = get_db()

        self.db.execute('PRAGMA foreign_keys=ON')

        for uid, role in [
            (1, 'designer'),
            (2, 'designer'),
            (3, 'manager'),
            (4, 'customer')
        ]:
            self.db.execute(
                'INSERT INTO user(id,name,password,email,phone,Usertype) '
                'VALUES(?,?,?,?,?,?)',
                (
                    uid,
                    'User ' + str(uid),
                    'hash',
                    str(uid) + '@example.com',
                    '123',
                    role
                )
            )

        self.db.execute(
            "INSERT INTO company(companyID,companyName,companyLine) "
            "VALUES(1,'Studio','555')"
        )

        self.db.execute(
            'INSERT INTO designer(userID,companyID) '
            'VALUES(1,1),(2,1)'
        )

        self.db.execute(
            'INSERT INTO platform(managerID) VALUES(3)'
        )

        self.db.execute(
            "INSERT INTO customer(cust_id,current_property_type) "
            "VALUES(4,'HDB')"
        )

        self.db.execute(
            "INSERT INTO category(id,name) "
            "VALUES(1,'Minimalist')"
        )

        self.db.commit()

        self.port = PortfolioController(
            str(self.root / 'uploads'),
            str(self.root / 'evidence')
        )

        self.review = ImageReviewController(
            str(self.root / 'uploads'),
            str(self.root / 'evidence')
        )

        self.a = self.project(1, 'Original')
        self.b = self.project(2, 'New project')

        self.client = self.app.test_client()

    def tearDown(self):
        # Flask closes its database connection when the
        # application context is popped.
        try:
            self.ctx.pop()
        finally:
            self.temp.cleanup()

    def project(self, owner, title):
        return self.port.create_idp(
            owner,
            title,
            'Description',
            'HDB',
            50000,
            'completed',
            [1],
            3
        )

    def login(self, uid):
        with self.client.session_transaction() as s:
            s.clear()

            if uid:
                s['user_id'] = uid

    def flagged(self):
        self.review.add_image(
            self.a,
            1,
            Fixtures.upload()
        )

        media, status = self.review.add_image(
            self.b,
            2,
            Fixtures.upload()
        )

        self.assertEqual(status, 'pending')

        return media

    def token(self):
        self.client.get('/portfolio/' + str(self.b))

        with self.client.session_transaction() as s:
            return s['story_form_token']

    def test_draft_private_then_clean_published(self):
        self.assertEqual(
            IDP.find(self.a)['approval_status'],
            'draft'
        )

        self.assertEqual(IDP.find_all(), [])

        _, status = self.review.add_image(
            self.a,
            1,
            Fixtures.upload()
        )

        self.assertEqual(status, 'approved')
        self.assertEqual(len(IDP.find_all()), 1)

    def test_duplicate_pending_owner_grey_manager_alert(self):
        self.flagged()

        p = IDP.find(self.b)

        self.assertEqual(p['status'], 'completed')
        self.assertEqual(p['approval_status'], 'pending')

        self.login(2)

        r = self.client.get('/portfolio')

        self.assertEqual(r.status_code, 200)
        self.assertIn(b'review-private', r.data)
        self.assertIn(b'Pending approval', r.data)

        self.login(3)

        r = self.client.get('/platform/dashboard')

        self.assertEqual(r.status_code, 200)
        self.assertIn(b'1 pending project', r.data)

    def test_public_queries_details_images_hidden(self):
        media = self.flagged()

        link = self.db.execute(
            'SELECT link FROM idp_media WHERE mediaID=?',
            (media,)
        ).fetchone()[0]

        self.assertEqual(
            [r['id'] for r in IDP.find_all()],
            [self.a]
        )

        self.assertEqual(
            DesignerSearch.find_by_name('User 2')[0]['project_count'],
            0
        )

        for uid in (None, 1, 4):
            self.login(uid)

            self.assertEqual(
                self.client.get(
                    '/projects/' + str(self.b)
                ).status_code,
                404
            )

            self.assertEqual(
                self.client.get(
                    '/static/uploads/' + link
                ).status_code,
                404
            )

        for uid in (2, 3):
            self.login(uid)

            with self.client.get(
                '/static/uploads/' + link
            ) as response:
                self.assertEqual(response.status_code, 200)

    def test_manager_comparison_and_access(self):
        self.flagged()

        case = ImageReview.cases(
            self.b,
            IDP.find(self.b)['image_revision']
        )[0]

        for uid in (None, 1, 2, 4):
            self.login(uid)

            self.assertIn(
                self.client.get(
                    '/platform/image-reviews'
                ).status_code,
                (302, 403)
            )

            self.assertIn(
                self.client.get(
                    '/platform/image-reviews/evidence/'
                    + str(case['id'])
                    + '/matched'
                ).status_code,
                (302, 403)
            )

        self.login(3)

        r = self.client.get(
            '/platform/image-reviews/projects/' + str(self.b)
        )

        self.assertEqual(r.status_code, 200)
        self.assertIn(b'100.0%', r.data)
        self.assertIn(b'Original', r.data)

        with self.client.get(
            '/platform/image-reviews/evidence/'
            + str(case['id'])
            + '/matched'
        ) as response:
            self.assertEqual(response.status_code, 200)

    def test_approve_publishes_and_records_reason(self):
        self.flagged()

        self.review.decide(
            self.b,
            IDP.find(self.b)['image_revision'],
            3,
            'approved',
            'Permission verified'
        )

        self.assertEqual(
            IDP.find(self.b)['approval_status'],
            'approved'
        )

        self.assertEqual(len(IDP.find_all()), 2)

        self.assertEqual(
            ImageReview.history(self.b)[0]['reason'],
            'Permission verified'
        )

        self.assertEqual(
            self.client.get(
                '/projects/' + str(self.b)
            ).status_code,
            200
        )

    def test_reject_private_reason_and_resubmit(self):
        self.flagged()

        self.review.decide(
            self.b,
            IDP.find(self.b)['image_revision'],
            3,
            'rejected',
            'Provide your own photo'
        )

        self.assertEqual(
            IDP.find(self.b)['approval_status'],
            'rejected'
        )

        self.login(2)

        r = self.client.get('/portfolio/' + str(self.b))

        self.assertIn(
            b'Provide your own photo',
            r.data
        )

        self.assertEqual(
            self.review.resubmit(self.b, 2),
            'pending'
        )

        self.assertEqual(
            len(ImageReview.history(self.b)),
            1
        )

    def test_stale_review_and_duplicate_decision(self):
        self.flagged()

        old = IDP.find(self.b)['image_revision']

        self.review.add_image(
            self.b,
            2,
            Fixtures.upload(Fixtures.scene(True))
        )

        with self.assertRaises(ValidationError):
            self.review.decide(
                self.b,
                old,
                3,
                'approved',
                'Old page'
            )

        current = IDP.find(self.b)['image_revision']

        self.review.decide(
            self.b,
            current,
            3,
            'approved',
            'Allowed'
        )

        with self.assertRaises(ValidationError):
            self.review.decide(
                self.b,
                current,
                3,
                'rejected',
                'Another page'
            )

    def test_rejected_remove_resubmit_clean(self):
        media = self.flagged()

        self.review.decide(
            self.b,
            IDP.find(self.b)['image_revision'],
            3,
            'rejected',
            'Replace image'
        )

        self.review.remove_image(media, 2)

        self.assertEqual(
            IDP.find(self.b)['approval_status'],
            'rejected'
        )

        with self.assertRaises(ValidationError):
            self.review.resubmit(self.b, 2)

        self.review.add_image(
            self.b,
            2,
            Fixtures.upload(Fixtures.scene(True))
        )

        self.assertEqual(
            IDP.find(self.b)['approval_status'],
            'approved'
        )

    def test_new_upload_rechecks_approved_project(self):
        self.flagged()

        self.review.decide(
            self.b,
            IDP.find(self.b)['image_revision'],
            3,
            'approved',
            'Authorised'
        )

        self.review.add_image(
            self.b,
            2,
            Fixtures.upload(Fixtures.scene(True))
        )

        self.assertEqual(
            IDP.find(self.b)['approval_status'],
            'pending'
        )

    def test_ownership_and_reason_validation(self):
        with self.assertRaises(PermissionDenied):
            self.review.add_image(
                self.a,
                2,
                Fixtures.upload()
            )

        self.flagged()

        with self.assertRaises(PermissionDenied):
            self.review.decide(
                self.b,
                1,
                2,
                'approved',
                'Not a manager'
            )

        for reason in ('', 'x' * 2001):
            with self.assertRaises(ValidationError):
                self.review.decide(
                    self.b,
                    1,
                    3,
                    'approved',
                    reason
                )

    def test_corrupt_file_no_media_or_publication(self):
        before = list(
            (self.root / 'uploads').glob('*')
        )

        with self.assertRaises(ValidationError):
            self.review.add_image(
                self.a,
                1,
                FileStorage(
                    stream=io.BytesIO(b'not a picture'),
                    filename='fake.jpg'
                )
            )

        self.assertEqual(
            ImageReview.media(self.a),
            []
        )

        self.assertEqual(
            list((self.root / 'uploads').glob('*')),
            before
        )

        self.assertEqual(
            IDP.find(self.a)['approval_status'],
            'draft'
        )

    def test_same_project_images_not_self_flagged(self):
        self.review.add_image(
            self.a,
            1,
            Fixtures.upload()
        )

        self.review.add_image(
            self.a,
            1,
            Fixtures.upload()
        )

        self.assertEqual(
            IDP.find(self.a)['approval_status'],
            'approved'
        )

    def test_remove_all_goes_private_draft(self):
        media, _ = self.review.add_image(
            self.a,
            1,
            Fixtures.upload()
        )

        self.review.remove_image(media, 1)

        self.assertEqual(
            IDP.find(self.a)['approval_status'],
            'draft'
        )

        self.assertEqual(IDP.find_all(), [])

    def test_snapshots_survive_original_removal(self):
        self.flagged()

        case = ImageReview.cases(self.b, 1)[0]

        before = (
            self.root / 'evidence' / case['matched_snapshot']
        ).read_bytes()

        m = ImageReview.media(self.a)[0]

        self.review.remove_image(
            m['mediaID'],
            1
        )

        self.assertEqual(
            (
                self.root / 'evidence' / case['matched_snapshot']
            ).read_bytes(),
            before
        )

    def test_favourites_hidden_when_project_becomes_pending(self):
        from idfinder.entities.favourites import Favourites

        self.review.add_image(
            self.a,
            1,
            Fixtures.upload()
        )

        self.review.add_image(
            self.b,
            2,
            Fixtures.upload(Fixtures.scene(True))
        )

        Favourites.add(4, self.b)

        self.assertEqual(
            len(Favourites.find_projects(4)),
            1
        )

        self.review.add_image(
            self.b,
            2,
            Fixtures.upload()
        )

        self.assertEqual(
            Favourites.find_projects(4),
            []
        )

        with self.assertRaises(Exception):
            Favourites.add(4, self.b)

    def test_upload_route_and_manager_post_tokens(self):
        self.review.add_image(
            self.a,
            1,
            Fixtures.upload()
        )

        self.login(2)

        token = self.token()

        data = {
            'file': (
                Fixtures.upload().stream,
                'room.png'
            ),
            'form_token': token
        }

        r = self.client.post(
            '/portfolio/' + str(self.b) + '/images',
            data=data,
            follow_redirects=True
        )

        self.assertEqual(r.status_code, 200)

        self.assertIn(
            b'potential image reuse',
            r.data.lower()
        )

        self.login(3)

        self.client.get(
            '/platform/image-reviews/projects/' + str(self.b)
        )

        with self.client.session_transaction() as s:
            token = s['story_form_token']

        endpoint = (
            '/platform/image-reviews/projects/' + str(self.b)
        )

        self.assertEqual(
            self.client.post(
                endpoint,
                data={
                    'decision': 'approved',
                    'reason': 'ok',
                    'revision': 1
                }
            ).status_code,
            400
        )

        r = self.client.post(
            endpoint,
            data={
                'form_token': token,
                'decision': 'approved',
                'reason': 'Ownership checked',
                'revision': IDP.find(self.b)['image_revision']
            }
        )

        self.assertEqual(r.status_code, 303)

        self.assertEqual(
            IDP.find(self.b)['approval_status'],
            'approved'
        )

    def test_schema_repeat_and_migration_backup(self):
        ImageReviewSchema.apply(self.db)

        self.assertEqual(
            IDP.find(self.a)['approval_status'],
            'draft'
        )

        result = self.app.test_cli_runner().invoke(
            args=['migrate-image-review']
        )

        self.assertEqual(
            result.exit_code,
            0,
            result.output
        )

        self.assertEqual(
            len(list(self.root.glob('*.bak'))),
            1
        )

    def test_upload_failure_rolls_back_file_media_state_and_evidence(self):
        from unittest.mock import patch

        self.review.add_image(
            self.a,
            1,
            Fixtures.upload()
        )

        original_state = dict(
            ImageReview.project(self.b)
        )

        before_files = set(
            (self.root / 'uploads').glob('*')
        )

        with patch.object(
            ImageReview,
            'add_case',
            side_effect=RuntimeError('simulated database failure')
        ):
            with self.assertRaises(RuntimeError):
                self.review.add_image(
                    self.b,
                    2,
                    Fixtures.upload()
                )

        self.assertEqual(
            ImageReview.media(self.b),
            []
        )

        self.assertEqual(
            dict(ImageReview.project(self.b)),
            original_state
        )

        self.assertEqual(
            set((self.root / 'uploads').glob('*')),
            before_files
        )

        self.assertEqual(
            list((self.root / 'evidence').glob('*')),
            []
        )

    def test_missing_legacy_file_is_reported(self):
        self.db.execute(
            'INSERT INTO idp_media(idp_id,link) VALUES(?,?)',
            (self.a, 'missing.png')
        )

        self.db.commit()

        count, unreadable = self.review.index_existing()

        self.assertEqual(count, 0)
        self.assertEqual(len(unreadable), 1)

    def test_housing_category_filters_keep_private_hidden(self):
        from idfinder.controller.search_controller import SearchController

        self.flagged()

        rows = SearchController.search(
            'HDB',
            '3',
            '1'
        )

        self.assertEqual(
            [r['id'] for r in rows],
            [self.a]
        )

    def test_delete_project_and_media_cleanup(self):
        self.flagged()

        self.port.delete_idp(
            self.b,
            2
        )

        self.assertIsNone(IDP.find(self.b))

        self.assertEqual(
            len(ImageReview.queue()),
            0
        )


class SimilarityTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def fp(self, im, name='a.png', **kwargs):
        p = self.root / name

        im.save(p, **kwargs)

        return ImageSimilarity.fingerprint(p)

    def test_resized_recompressed_and_brightness(self):
        original = self.fp(Fixtures.scene())

        for im, name in [
            (
                Fixtures.scene().resize((300, 200)),
                'small.jpg'
            ),
            (
                ImageEnhance.Brightness(
                    Fixtures.scene()
                ).enhance(1.12),
                'bright.jpg'
            )
        ]:
            self.assertIsNotNone(
                ImageSimilarity.compare(
                    original,
                    self.fp(im, name, quality=78)
                )
            )

    def test_unrelated_and_plain_colours(self):
        a = self.fp(Fixtures.scene())

        b = self.fp(
            Fixtures.scene(True),
            'b.png'
        )

        self.assertIsNone(
            ImageSimilarity.compare(a, b)
        )

        red = self.fp(
            Image.new('RGB', (100, 100), 'red'),
            'red.png'
        )

        blue = self.fp(
            Image.new('RGB', (100, 100), 'blue'),
            'blue.png'
        )

        self.assertIsNone(
            ImageSimilarity.compare(red, blue)
        )

        self.assertEqual(
            ImageSimilarity.compare(red, red)['score'],
            100
        )

    def test_animated_gif_rejected(self):
        path = self.root / 'animated.gif'

        Fixtures.scene().save(
            path,
            save_all=True,
            append_images=[Fixtures.scene(True)],
            duration=100,
            loop=0
        )

        with self.assertRaises(ValidationError):
            ImageSimilarity.fingerprint(path)


class LegacyMigrationTests(unittest.TestCase):

    def test_legacy_records_preserved_and_default_approved(self):
        # FIX 2:
        # Ensure the temporary SQLite database connection closes
        # before Windows deletes the TemporaryDirectory.

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'legacy.sqlite'

            with closing(sqlite3.connect(path)) as db:
                db.execute(
                    'CREATE TABLE idp('
                    'id INTEGER PRIMARY KEY, '
                    'title TEXT)'
                )

                db.execute(
                    "INSERT INTO idp(id,title) "
                    "VALUES(1,'Existing project')"
                )

                db.commit()

                ImageReviewSchema.apply(db)
                ImageReviewSchema.apply(db)

                row = db.execute(
                    'SELECT title,approval_status,image_revision '
                    'FROM idp'
                ).fetchone()

                self.assertEqual(
                    row,
                    ('Existing project', 'approved', 0)
                )


if __name__ == '__main__':
    unittest.main(verbosity=2)
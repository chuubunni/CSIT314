"""
Regression tests for ID07 portfolio + image review.

Run from the CSIT314 root:

python -m unittest discover -s tests -p "test_id07.py" -v

Positive upload tests use real JPEG data.
"""

import io
import tempfile
import unittest

from pathlib import Path

from PIL import Image, ImageDraw
from werkzeug.datastructures import FileStorage

from idfinder import create_app
from idfinder.db import get_db, init_db

from idfinder.controller.errors import (
    PermissionDenied,
    ValidationError
)

from idfinder.controller.portfolio_controller import (
    PortfolioController
)

from idfinder.entities.idp import IDP
from idfinder.entities.idp_media import IDPMedia


class ID07Tests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        self.app = create_app({
            'TESTING': True,
            'DEMO_DATA': False,
            'SECRET_KEY': 'id07-tests',
            'DATABASE': str(self.root / 'tests.sqlite'),
            'UPLOAD_FOLDER': str(self.root / 'uploads'),
            'REVIEW_EVIDENCE_FOLDER': str(
                self.root / 'evidence'
            ),
        })

        self.context = self.app.app_context()
        self.context.push()

        init_db()
        self.db = get_db()

        self.db.execute('PRAGMA foreign_keys=ON')

        for user_id, role in [
            (1, 'designer'),
            (2, 'designer'),
            (3, 'manager')
        ]:
            self.db.execute(
                'INSERT INTO user'
                '(id,name,password,email,phone,Usertype) '
                'VALUES(?,?,?,?,?,?)',
                (
                    user_id,
                    f'User {user_id}',
                    'hash',
                    f'{user_id}@test.com',
                    '123',
                    role
                )
            )

        self.db.execute(
            "INSERT INTO company"
            "(companyID,companyName,companyLine) "
            "VALUES(1,'Firm','555')"
        )

        self.db.execute(
            'INSERT INTO designer(userID,companyID) '
            'VALUES(1,1),(2,1)'
        )

        self.db.execute(
            'INSERT INTO platform(managerID) VALUES(3)'
        )

        self.db.execute(
            "INSERT INTO category(id,name) "
            "VALUES(1,'Minimalist')"
        )

        self.db.commit()

        self.ctrl = PortfolioController(
            str(self.root / 'uploads'),
            str(self.root / 'evidence')
        )

        self.client = self.app.test_client()

    def tearDown(self):
        try:
            self.context.pop()
        finally:
            self.temp.cleanup()

    @staticmethod
    def file(name='room.jpg', seed=1):
        """Return a real JPEG image for positive upload tests."""

        image = Image.new(
            'RGB',
            (220, 160),
            (210, 195, 160)
        )

        drawing = ImageDraw.Draw(image)

        drawing.rectangle(
            (20, 30, 190, 120),
            fill=(30 + seed * 12, 105, 130)
        )

        drawing.ellipse(
            (30 + seed, 40, 90 + seed, 95),
            fill=(160, 70, 50)
        )

        stream = io.BytesIO()

        image.save(
            stream,
            format='JPEG'
        )

        stream.seek(0)

        return FileStorage(
            stream=stream,
            filename=name
        )

    @staticmethod
    def fields():
        return dict(
            title='Demo living room',
            description='Original interior design work',
            property_type='HDB',
            property_subtype_id=3,
            price='50000',
            status='completed',
            category_ids=[1],
        )

    def create(self, owner=1, images=()):
        return self.ctrl.create_idp(
            owner,
            **self.fields(),
            images=images
        )

    def login(self, user_id=1):
        with self.client.session_transaction() as session:
            session.clear()
            session['user_id'] = user_id

    def test_designer_header_links_line_up(self):
        self.login()

        response = self.client.get('/portfolio')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'New project', response.data)

    def test_id07_bad_image_saves_nothing(self):
        self.login()

        before = self.db.execute(
            'SELECT COUNT(*) FROM idp'
        ).fetchone()[0]

        response = self.client.post(
            '/portfolio/new',
            data={
                **self.fields(),
                'images': (
                    io.BytesIO(b'not an image'),
                    'invalid.jpg'
                ),
            },
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, 200)

        after = self.db.execute(
            'SELECT COUNT(*) FROM idp'
        ).fetchone()[0]

        self.assertEqual(before, after)

    def test_id07_create_project_with_several_images(self):
        project_id = self.create(
            images=[
                self.file('one.jpg', 1),
                self.file('two.jpg', 2)
            ]
        )

        self.assertEqual(
            len(IDPMedia.find_by_idp(project_id)),
            2
        )

        self.assertEqual(
            IDP.find(project_id)['approval_status'],
            'approved'
        )

    def test_id07_create_project_without_images(self):
        project_id = self.create()

        self.assertEqual(
            len(IDPMedia.find_by_idp(project_id)),
            0
        )

        self.assertEqual(
            IDP.find(project_id)['approval_status'],
            'draft'
        )

    def test_id07_edit_adds_images_and_keeps_existing(self):
        project_id = self.create(
            images=[self.file('old.jpg', 1)]
        )

        original_media_id = (
            IDPMedia.find_by_idp(project_id)[0]['mediaID']
        )

        self.ctrl.update_idp(
            project_id,
            1,
            **self.fields(),
            images=[self.file('added.jpg', 3)]
        )

        images = IDPMedia.find_by_idp(project_id)

        self.assertEqual(len(images), 2)

        self.assertIn(
            original_media_id,
            [image['mediaID'] for image in images]
        )

    def test_id07_edit_removes_ticked_images(self):
        project_id = self.create(
            images=[
                self.file('keep.jpg', 1),
                self.file('remove.jpg', 2)
            ]
        )

        original = IDPMedia.find_by_idp(project_id)

        keep_id = original[0]['mediaID']
        remove_id = original[1]['mediaID']

        removed_file = (
            self.root / 'uploads' / original[1]['link']
        )

        self.ctrl.update_idp(
            project_id,
            1,
            **self.fields(),
            remove_media_ids=[str(remove_id)]
        )

        self.assertEqual(
            [
                m['mediaID']
                for m in IDPMedia.find_by_idp(project_id)
            ],
            [keep_id]
        )

        self.assertFalse(removed_file.exists())

    def test_id07_cannot_remove_another_projects_image(self):
        my_project = self.create(owner=1)

        their_project = self.create(
            owner=2,
            images=[self.file('theirs.jpg', 4)]
        )

        other_id = (
            IDPMedia.find_by_idp(their_project)[0]['mediaID']
        )

        with self.assertRaises(PermissionDenied):
            self.ctrl.remove_media(other_id, 1)

        with self.assertRaises(ValidationError):
            self.ctrl.update_idp(
                my_project,
                1,
                **self.fields(),
                remove_media_ids=[str(other_id)]
            )

        self.assertIsNotNone(IDPMedia.find(other_id))

    def test_id07_form_and_detail_pages(self):
        self.login()

        form = self.client.get('/portfolio/new')

        self.assertEqual(form.status_code, 200)

        self.assertIn(
            b'name="images"',
            form.data
        )

        self.assertIn(b'multiple', form.data)

        project_id = self.create(
            images=[self.file('shown.jpg')]
        )

        detail = self.client.get(
            f'/portfolio/{project_id}'
        )

        self.assertEqual(detail.status_code, 200)
        self.assertIn(b'Images', detail.data)

        edit = self.client.get(
            f'/portfolio/{project_id}/edit'
        )

        self.assertEqual(edit.status_code, 200)

        self.assertIn(
            b'name="remove_media_ids"',
            edit.data
        )

        self.assertIn(
            b'name="images"',
            edit.data
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
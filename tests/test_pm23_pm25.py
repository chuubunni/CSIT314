"""
Regression tests for PM23 (update platform manager profile)
and PM25 (view platform manager profile).

Run from the CSIT314 root:

python -m unittest discover -s tests -p "test_pm23_pm25.py" -v
"""

import gc
import tempfile
import unittest

from pathlib import Path

from idfinder import create_app
from idfinder.db import get_db, init_db

from idfinder.controller.errors import (
    NotFoundError,
    ValidationError
)

from idfinder.controller.platform_controller import (
    PlatformController
)

from idfinder.entities.user import managers


class PM23PM25Tests(unittest.TestCase):

    def setUp(self):
        # ignore_cleanup_errors: on Windows a still-open SQLite file cannot be deleted
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp.name)

        self.app = create_app({
            'TESTING': True,
            'DEMO_DATA': False,
            'SECRET_KEY': 'pm23-pm25-tests',
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

        # 1 = manager under test, 2 = second manager (owns a taken email),
        # 3 = designer, 4 = customer, 5 = manager account with no platform record
        for user_id, role in [
            (1, 'manager'),
            (2, 'manager'),
            (3, 'designer'),
            (4, 'customer'),
            (5, 'manager')
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
            'INSERT INTO platform(managerID) VALUES(1),(2)'
        )

        self.db.execute(
            "INSERT INTO company"
            "(companyID,companyName,companyLine) "
            "VALUES(1,'Firm','555')"
        )

        self.db.execute(
            'INSERT INTO designer(userID,companyID) VALUES(3,1)'
        )

        self.db.execute(
            "INSERT INTO customer(cust_id,current_property_type) "
            "VALUES(4,'HDB')"
        )

        self.db.commit()

        self.ctrl = PlatformController()

        self.client = self.app.test_client()

    def tearDown(self):
        try:
            self.context.pop()
        finally:
            gc.collect()        # close connections the app left open before deleting the folder
            self.temp.cleanup()

    @staticmethod
    def fields(**changes):
        values = dict(
            name='Manager One',
            email='manager.one@test.com',
            phone='91234567'
        )
        values.update(changes)
        return values

    def login(self, user_id=1):
        with self.client.session_transaction() as session:
            session.clear()
            session['user_id'] = user_id

    def logout(self):
        with self.client.session_transaction() as session:
            session.clear()

    def stored(self, user_id=1):
        return self.db.execute(
            'SELECT name, email, phone FROM user WHERE id = ?',
            (user_id,)
        ).fetchone()

    # ----- PM25: view platform manager profile -----

    def test_pm25_profile_page_shows_manager_details(self):
        self.login()

        response = self.client.get('/platform/profile')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'My Profile', response.data)
        self.assertIn(b'User 1', response.data)
        self.assertIn(b'1@test.com', response.data)
        self.assertIn(b'Edit Profile', response.data)

    def test_pm25_controller_returns_own_profile(self):
        profile = self.ctrl.get_profile(1)

        self.assertEqual(profile['name'], 'User 1')
        self.assertEqual(profile['email'], '1@test.com')
        self.assertEqual(profile['phone'], '123')

    def test_pm25_not_logged_in_redirects_to_login(self):
        self.logout()

        response = self.client.get('/platform/profile')

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.headers['Location'])

    def test_pm25_other_user_types_get_403(self):
        for user_id in (3, 4):
            with self.subTest(user_id=user_id):
                self.login(user_id)

                response = self.client.get('/platform/profile')

                self.assertEqual(response.status_code, 403)

    def test_pm25_missing_manager_record_gives_404(self):
        with self.assertRaises(NotFoundError):
            self.ctrl.get_profile(5)

        self.login(5)

        response = self.client.get('/platform/profile')

        self.assertEqual(response.status_code, 404)

    # ----- PM23: update platform manager profile -----

    def test_pm23_edit_form_is_filled_with_current_details(self):
        self.login()

        response = self.client.get('/platform/profile/edit')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Save changes', response.data)
        self.assertIn(b'value="User 1"', response.data)
        self.assertIn(b'value="1@test.com"', response.data)

    def test_pm23_valid_update_is_saved(self):
        self.login()

        response = self.client.post(
            '/platform/profile/edit',
            data=self.fields()
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.headers['Location'].endswith('/platform/profile')
        )

        row = self.stored()

        self.assertEqual(row['name'], 'Manager One')
        self.assertEqual(row['email'], 'manager.one@test.com')
        self.assertEqual(row['phone'], '91234567')

        page = self.client.get('/platform/profile')

        self.assertIn(b'Profile updated.', page.data)
        self.assertIn(b'Manager One', page.data)

    def test_pm23_values_are_trimmed(self):
        self.ctrl.edit_profile(
            1,
            '  Manager One  ',
            ' manager.one@test.com ',
            ' 91234567 '
        )

        row = self.stored()

        self.assertEqual(row['name'], 'Manager One')
        self.assertEqual(row['email'], 'manager.one@test.com')
        self.assertEqual(row['phone'], '91234567')

    def test_pm23_blank_or_invalid_values_are_rejected(self):
        cases = [
            ('name', '', 'Name is required.'),
            ('name', '   ', 'Name is required.'),
            ('email', '', 'Please enter a valid email address.'),
            ('email', 'managermail.com', 'Please enter a valid email address.'),
            ('phone', '', 'Phone number is required.'),
        ]

        for field, value, message in cases:
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValidationError) as caught:
                    self.ctrl.edit_profile(
                        1,
                        **self.fields(**{field: value})
                    )

                self.assertEqual(str(caught.exception), message)

        row = self.stored()

        self.assertEqual(row['name'], 'User 1')
        self.assertEqual(row['email'], '1@test.com')

    def test_pm23_invalid_form_is_shown_again_with_message(self):
        self.login()

        response = self.client.post(
            '/platform/profile/edit',
            data=self.fields(name='')
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Name is required.', response.data)
        self.assertIn(b'value="manager.one@test.com"', response.data)
        self.assertEqual(self.stored()['name'], 'User 1')

    def test_pm23_email_used_by_another_account_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            self.ctrl.edit_profile(
                1,
                **self.fields(email='2@test.com')
            )

        self.assertEqual(
            str(caught.exception),
            'This email is already used by another account.'
        )

        self.assertEqual(self.stored()['email'], '1@test.com')

    def test_pm23_other_user_types_cannot_edit(self):
        for user_id in (3, 4):
            with self.subTest(user_id=user_id):
                self.login(user_id)

                response = self.client.post(
                    '/platform/profile/edit',
                    data=self.fields()
                )

                self.assertEqual(response.status_code, 403)

        self.assertEqual(self.stored()['name'], 'User 1')

    def test_pm23_entity_updates_only_that_manager(self):
        managers.update_profile(
            1,
            'Manager One',
            'manager.one@test.com',
            '91234567'
        )

        self.assertEqual(self.stored(1)['name'], 'Manager One')
        self.assertEqual(self.stored(2)['name'], 'User 2')


if __name__ == '__main__':
    unittest.main(verbosity=2)

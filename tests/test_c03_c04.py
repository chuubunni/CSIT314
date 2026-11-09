"""
Regression tests for C03 (view customer profile)
and C04 (update customer profile).

Run from the CSIT314 root:

python -m unittest discover -s tests -p "test_c03_c04.py" -v
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

from idfinder.controller.customer_controller import (
    CustomerController
)

from idfinder.entities.user import customers


class C03C04Tests(unittest.TestCase):

    def setUp(self):
        # ignore_cleanup_errors: on Windows a still-open SQLite file cannot be deleted
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp.name)

        self.app = create_app({
            'TESTING': True,
            'DEMO_DATA': False,
            'SECRET_KEY': 'c03-c04-tests',
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

        # 1 = customer under test, 2 = second customer (owns a taken email),
        # 3 = designer, 4 = manager, 5 = customer account with no customer record
        for user_id, role in [
            (1, 'customer'),
            (2, 'customer'),
            (3, 'designer'),
            (4, 'manager'),
            (5, 'customer')
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
            "INSERT INTO customer"
            "(cust_id,current_property_type,received_keys) "
            "VALUES(1,'HDB',0),(2,'Condo',NULL)"
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
            'INSERT INTO platform(managerID) VALUES(4)'
        )

        self.db.commit()

        self.ctrl = CustomerController()

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
            name='Customer One',
            email='customer.one@test.com',
            phone='91234567',
            current_property_type='Landed',
            received_keys='1'
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
            'SELECT u.name, u.email, u.phone, '
            'c.current_property_type, c.received_keys '
            'FROM user u JOIN customer c ON c.cust_id = u.id '
            'WHERE u.id = ?',
            (user_id,)
        ).fetchone()

    # ----- C03: view customer profile -----

    def test_c03_profile_page_shows_customer_details(self):
        self.login()

        response = self.client.get('/customer/profile')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'My Profile', response.data)
        self.assertIn(b'User 1', response.data)
        self.assertIn(b'1@test.com', response.data)
        self.assertIn(b'House type', response.data)
        self.assertIn(b'Edit Profile', response.data)

    def test_c03_controller_returns_own_profile(self):
        profile = self.ctrl.get_profile(1)

        self.assertEqual(profile['name'], 'User 1')
        self.assertEqual(profile['email'], '1@test.com')
        self.assertEqual(profile['current_property_type'], 'HDB')
        self.assertEqual(profile['received_keys'], 0)

    def test_c03_not_logged_in_redirects_to_login(self):
        self.logout()

        response = self.client.get('/customer/profile')

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.headers['Location'])

    def test_c03_other_user_types_get_403(self):
        for user_id in (3, 4):
            with self.subTest(user_id=user_id):
                self.login(user_id)

                response = self.client.get('/customer/profile')

                self.assertEqual(response.status_code, 403)

    def test_c03_missing_customer_record_gives_404(self):
        with self.assertRaises(NotFoundError):
            self.ctrl.get_profile(5)

        self.login(5)

        response = self.client.get('/customer/profile')

        self.assertEqual(response.status_code, 404)

    # ----- C04: update customer profile -----

    def test_c04_edit_form_is_filled_with_current_details(self):
        self.login()

        response = self.client.get('/customer/profile/edit')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Save changes', response.data)
        self.assertIn(b'value="User 1"', response.data)
        self.assertIn(b'value="1@test.com"', response.data)
        self.assertIn(b'name="current_property_type"', response.data)
        self.assertIn(b'name="received_keys"', response.data)

    def test_c04_valid_update_is_saved(self):
        self.login()

        response = self.client.post(
            '/customer/profile/edit',
            data=self.fields()
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.headers['Location'].endswith('/customer/profile')
        )

        row = self.stored()

        self.assertEqual(row['name'], 'Customer One')
        self.assertEqual(row['email'], 'customer.one@test.com')
        self.assertEqual(row['phone'], '91234567')
        self.assertEqual(row['current_property_type'], 'Landed')
        self.assertEqual(row['received_keys'], 1)

        page = self.client.get('/customer/profile')

        self.assertIn(b'Profile updated.', page.data)
        self.assertIn(b'Customer One', page.data)

    def test_c04_property_type_ignores_case(self):
        self.ctrl.update_profile(
            1,
            **self.fields(current_property_type='condo')
        )

        self.assertEqual(self.stored()['current_property_type'], 'Condo')

    def test_c04_received_keys_values(self):
        for raw, expected in [('1', 1), ('0', 0), ('', None)]:
            with self.subTest(received_keys=raw):
                self.ctrl.update_profile(
                    1,
                    **self.fields(received_keys=raw)
                )

                self.assertEqual(self.stored()['received_keys'], expected)

    def test_c04_blank_or_invalid_values_are_rejected(self):
        cases = [
            ('name', '', 'Name is required.'),
            ('name', '   ', 'Name is required.'),
            ('email', '', 'Please enter a valid email address.'),
            ('email', 'customermail.com', 'Please enter a valid email address.'),
            ('phone', '', 'Phone number is required.'),
            ('current_property_type', 'Mansion',
             'Please choose your current property type.'),
            ('received_keys', 'maybe',
             'Please choose Yes, No, or leave it unspecified.'),
        ]

        for field, value, message in cases:
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValidationError) as caught:
                    self.ctrl.update_profile(
                        1,
                        **self.fields(**{field: value})
                    )

                self.assertEqual(str(caught.exception), message)

        row = self.stored()

        self.assertEqual(row['name'], 'User 1')
        self.assertEqual(row['current_property_type'], 'HDB')
        self.assertEqual(row['received_keys'], 0)

    def test_c04_invalid_form_is_shown_again_with_message(self):
        self.login()

        response = self.client.post(
            '/customer/profile/edit',
            data=self.fields(phone='')
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Phone number is required.', response.data)
        self.assertIn(b'value="customer.one@test.com"', response.data)
        self.assertEqual(self.stored()['phone'], '123')

    def test_c04_email_used_by_another_account_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            self.ctrl.update_profile(
                1,
                **self.fields(email='3@test.com')
            )

        self.assertEqual(
            str(caught.exception),
            'This email is already used by another account.'
        )

        row = self.stored()

        self.assertEqual(row['email'], '1@test.com')
        self.assertEqual(row['current_property_type'], 'HDB')

    def test_c04_other_user_types_cannot_edit(self):
        for user_id in (3, 4):
            with self.subTest(user_id=user_id):
                self.login(user_id)

                response = self.client.post(
                    '/customer/profile/edit',
                    data=self.fields()
                )

                self.assertEqual(response.status_code, 403)

        self.assertEqual(self.stored()['name'], 'User 1')

    def test_c04_entity_updates_only_that_customer(self):
        customers.update_profile(
            1,
            'Customer One',
            'customer.one@test.com',
            '91234567',
            'Landed',
            1
        )

        self.assertEqual(self.stored(1)['name'], 'Customer One')
        self.assertEqual(self.stored(2)['name'], 'User 2')
        self.assertEqual(self.stored(2)['current_property_type'], 'Condo')


if __name__ == '__main__':
    unittest.main(verbosity=2)

import sqlite3

from werkzeug.security import check_password_hash

from myfirstapp.controller.errors import ValidationError
from myfirstapp.entities.user import Users, customers, designers

# Platform managers are never created through the public register form.
SELF_REGISTER_TYPES = ("designer", "customer")


class auth_control:
    """Control: the rules for logging in and registering.

    No Flask objects in here (no request, session, flash, redirect) and no database
    connection: it takes plain values, talks to the entity classes, and raises
    ValidationError with a message the boundary can flash.
    """

    @staticmethod
    def get_user(user_id):
        return Users.get_info(user_id)

    @staticmethod
    def authenticate_user(email, password):
        """Returns the user row, or raises ValidationError."""
        user = Users.check_email((email or '').strip())
        if user is None:
            raise ValidationError('Incorrect email address')
        # check_password_hash hashes the submitted password and compares the two hashes
        if not check_password_hash(user['password'], password or ''):
            raise ValidationError('Incorrect password')
        return user

    @staticmethod
    def do_register(name, password, email, phoneNo, Usertype):
        """Step 1 of registration. Returns the new user's id, or raises ValidationError."""
        name = (name or '').strip()
        email = (email or '').strip()
        phoneNo = (phoneNo or '').strip()

        if not name:
            raise ValidationError('name is required')
        if not password:
            raise ValidationError('password is required')
        if not email:
            raise ValidationError('email is required')
        if not phoneNo:
            raise ValidationError('phone is required')
        if Usertype not in SELF_REGISTER_TYPES:
            raise ValidationError('Please choose designer or customer.')

        try:
            user_id = Users.create_user(name, password, email, phoneNo, Usertype)
        except sqlite3.IntegrityError:
            raise ValidationError(f"This email {email} has already registered.")

        if Usertype == 'customer':
            customers.create_customer(user_id)   # customers need no extra details
        return user_id

    @staticmethod
    def register_designer(user_id, companyName, companyLine, companyDescription, companyEmail):
        """Step 2 for designers: create the designer row. Raises ValidationError."""
        companyName = (companyName or '').strip()
        companyLine = (companyLine or '').strip()
        companyDescription = (companyDescription or '').strip()
        companyEmail = (companyEmail or '').strip()

        if not companyName:
            raise ValidationError('Company name is required.')
        if not companyLine:
            raise ValidationError('Company phone number is required.')

        user = Users.get_info(user_id)
        if user is None or user['Usertype'] != 'designer':
            raise ValidationError('Only designer accounts can register a company.')

        try:
            designers.create_designer(user_id, companyName, companyLine,
                                      companyDescription, companyEmail)
        except sqlite3.IntegrityError as error:
            if 'companyLine' in str(error):
                raise ValidationError(
                    'A designer profile with this company phone number already exists.')
            raise ValidationError('You have already registered as a designer.')
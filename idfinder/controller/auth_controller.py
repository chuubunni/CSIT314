import sqlite3

from werkzeug.security import check_password_hash

from idfinder.controller.errors import ValidationError
from idfinder.controller.portfolio_controller import PROPERTY_TYPES   # same list as the IDP form
from idfinder.entities.user import Users, customers, designers, managers

# Platform managers are never created through the public register form.
SELF_REGISTER_TYPES = ("designer", "customer")


def _clean_property_type(value):
    """Canonical spelling of a property type (matched ignoring case), or ValidationError."""
    by_lower = {property.lower(): property for property in PROPERTY_TYPES}
    property = by_lower.get((value or '').strip().lower())
    if property is None:
        raise ValidationError('Please choose your current property type.')
    return property


def _clean_received_keys(value):
    """'' -> None (not specified), '1' -> 1 (received), '0' -> 0 (not yet)."""
    value = (value or '').strip()
    if value == '':
        return None
    if value in ('0', '1'):
        return int(value)
    raise ValidationError('Please choose Yes, No, or leave it unspecified.')


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
    def do_register(name, password, email, phoneNo, Usertype, company=None, customer=None):
        """Register a customer or a designer in one step. Returns the new user's id.

        company  - dict with companyName, companyLine, companyEmail (designers only)
        customer - dict with current_property_type, received_keys      (customers only)
        The details for the other user type are ignored. Raises ValidationError.
        """
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

        # Check the type-specific details BEFORE creating the user,
        # so a bad form leaves nothing behind.  
        if Usertype == 'designer':
            company = company or {}
            companyName = (company.get('companyName') or '').strip()
            companyLine = (company.get('companyLine') or '').strip()
            companyEmail = (company.get('companyEmail') or '').strip()
            if not companyName:
                raise ValidationError('Company name is required.')
            if not companyLine:
                raise ValidationError('Company phone number is required.')
        if Usertype == 'customer':
            customer = customer or {}
            property_type = _clean_property_type(customer.get('current_property_type'))
            received_keys = _clean_received_keys(customer.get('received_keys'))

        try:
            user_id = Users.create_user(name, password, email, phoneNo, Usertype)
        except sqlite3.IntegrityError:
            raise ValidationError(f"This email {email} has already registered.")

        if Usertype == 'customer':
            try:
                customers.create_customer(user_id, property_type, received_keys)
            except sqlite3.IntegrityError:
                Users.delete_user(user_id)       # undo step 1 so the person can simply try again
                raise ValidationError('Could not create the customer profile.')
        elif Usertype == 'manager':
            try:
                managers.create_manager(user_id)
            except sqlite3.IntegrityError:
                Users.delete_user(user_id)
                raise ValidationError('Cannot create platform manager profile')
        else:
            try:
                designers.register_designer(user_id, companyName, companyLine, companyEmail)
            except sqlite3.IntegrityError as error:
                Users.delete_user(user_id)       # undo step 1 so the person can simply try again
                if 'companyLine' in str(error):
                    raise ValidationError(
                        'A designer profile with this company phone number already exists.')
                raise ValidationError('Could not create the designer profile.')
        return user_id

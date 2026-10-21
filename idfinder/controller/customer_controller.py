import sqlite3

from idfinder.controller.errors import NotFoundError, ValidationError
from idfinder.controller.portfolio_controller import HOUSE_TYPES   # same list as the IDP form
from idfinder.entities.user import customers


class CustomerController:
    """Control: rules for a customer viewing and editing their own profile.

    Every method takes the customer's id from the logged-in user, never from the URL
    or the form, so a customer can only ever read or change their own record.
    """

    def get_profile(self, customer_id):
        profile = customers.get_profile(customer_id)
        if profile is None:
            raise NotFoundError('Customer profile not found.')
        return profile

    def update_profile(self, customer_id, name, email, phone, current_house_type, received_keys):
        self.get_profile(customer_id)          # 404 if this account has no customer profile

        name = (name or '').strip()
        email = (email or '').strip()
        phone = (phone or '').strip()
        if not name:
            raise ValidationError('Name is required.')
        if not email or '@' not in email:
            raise ValidationError('Please enter a valid email address.')
        if not phone:
            raise ValidationError('Phone number is required.')

        by_lower = {house.lower(): house for house in HOUSE_TYPES}
        house = by_lower.get((current_house_type or '').strip().lower())
        if house is None:
            raise ValidationError('Please choose your current house type.')

        keys = self._clean_keys(received_keys)

        try:
            customers.update_profile(customer_id, name, email, phone, house, keys)
        except sqlite3.IntegrityError:
            raise ValidationError('This email is already used by another account.')

    @staticmethod
    def _clean_keys(value):
        """'' -> None (not specified), '1' -> 1 (received), '0' -> 0 (not yet)."""
        value = (value or '').strip()
        if value == '':
            return None
        if value in ('0', '1'):
            return int(value)
        raise ValidationError('Please choose Yes, No, or leave it unspecified.')
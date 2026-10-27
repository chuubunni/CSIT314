import sqlite3

from idfinder.entities.category import Category
from idfinder.entities.housing import Housing
from idfinder.entities.platform_report import PlatformReport
from idfinder.controller.errors import ValidationError, NotFoundError
from idfinder.entities.user import managers


class PlatformController:
    """Business rules for category maintenance and platform reports."""

    def categories(self, search=''):
        return Category.find_all((search or '').strip())

    def add_category(self, name):
        name = self._validate_name(name)
        try:
            Category.create(name)
        except sqlite3.IntegrityError:
            raise ValidationError('This category name already exists.')

    def edit_category(self, category_id, name, active):
        if Category.find(category_id) is None:
            raise NotFoundError('Category not found.')
        name = self._validate_name(name)
        try:
            Category.update(category_id, name, active)
        except sqlite3.IntegrityError:
            raise ValidationError('This category name already exists.')

    def remove_category(self, category_id):
        category = Category.find(category_id)
        if category is None:
            raise NotFoundError('Category not found.')
        # Do not destroy references to this category in existing IDPs.
        projects = next((c['project_count'] for c in Category.find_all() if c['id'] == category_id), 0)
        if projects:
            raise ValidationError('Category is assigned to projects. Deactivate it instead.')
        Category.delete(category_id)

    def property_types(self):
        return Housing.types_with_usage()

    def remove_property_type(self, type_id):
        """PM14: remove an obsolete property type (and its subtypes). Returns its name.

        Refused while any project or customer still uses the type, so no existing
        record is left pointing at a classification that no longer exists. The
        last remaining type can't be removed, otherwise no project could be created.
        """
        usage = next((t for t in Housing.types_with_usage() if t['id'] == type_id), None)
        if usage is None:
            raise NotFoundError('Property type not found.')
        if usage['project_count'] or usage['customer_count']:
            raise ValidationError(
                f"Cannot remove {usage['name']}: it is used by {usage['project_count']} project(s) "
                f"and {usage['customer_count']} customer(s). Move or delete those first.")
        if len(Housing.codes()) <= 1:
            raise ValidationError('At least one property type must remain on the platform.')
        Housing.delete_type(type_id)
        return usage['name']

    def report(self, period):
        if period not in ('daily', 'weekly', 'monthly'):
            raise ValidationError('Invalid report period.')
        return PlatformReport.overview(period)

    def interest(self):
        return PlatformReport.interest()

    @staticmethod
    def _validate_name(name):
        name = (name or '').strip()
        if not name or len(name) > 80:
            raise ValidationError('Category name must be 1–80 characters.')
        return name


    def get_profile(self, managerid):
        profile = managers.get_profile(managerid)
        if profile is None: 
            raise NotFoundError("No manager profile found")
        return profile 

    def edit_profile(self, managerid, name, email, phone):
        self.get_profile(managerid)          # 404 if this account has no customer profile

        name = (name or '').strip()
        email = (email or '').strip()
        phone = (phone or '').strip()
        if not name:
            raise ValidationError('Name is required.')
        if not email or '@' not in email:
            raise ValidationError('Please enter a valid email address.')
        if not phone:
            raise ValidationError('Phone number is required.')

        try:
            managers.update_profile(managerid, name, email, phone)
        except sqlite3.IntegrityError:
            raise ValidationError('This email is already used by another account.')

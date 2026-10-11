import sqlite3

from myfirstapp.entities.category import Category
from myfirstapp.entities.platform_report import PlatformReport
from myfirstapp.controller.errors import ValidationError, NotFoundError


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

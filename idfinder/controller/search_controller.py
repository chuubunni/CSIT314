from idfinder.controller.errors import ValidationError
from idfinder.entities.housing import Housing
from idfinder.entities.category import Category
from idfinder.entities.idp import IDP
from idfinder.entities.search import DesignerSearch


class SearchController:
    """Validate filter values and retrieve matching records."""

    MAX_NAME_LENGTH = 100

    @staticmethod
    def options():
        return Housing.types(), Housing.subtypes()

    @staticmethod
    def categories():
        """Return active categories managed by Platform Managers."""
        return Category.find_all_active()

    @staticmethod
    def search(
        property_type='',
        property_subtype_id='',
        category_id=''
    ):
        property_type = (property_type or '').strip()

        if property_type and Housing.find_type(property_type) is None:
            raise ValidationError(
                'Please choose a valid housing type.'
            )

        subtype_id = None

        if property_subtype_id:
            try:
                subtype_id = int(property_subtype_id)
            except (TypeError, ValueError):
                raise ValidationError(
                    'Please choose a valid housing subtype.'
                )

            subtype = Housing.find_subtype(subtype_id)

            if subtype is None:
                raise ValidationError(
                    'Please choose a valid housing subtype.'
                )

            if (
                not property_type
                or subtype['type_code'] != property_type
            ):
                raise ValidationError(
                    'The subtype must belong to the selected housing type.'
                )

        selected_category_id = None

        if category_id:
            try:
                selected_category_id = int(category_id)
            except (TypeError, ValueError):
                raise ValidationError(
                    'Please choose a valid design category.'
                )

            category = Category.find(selected_category_id)

            if category is None or not category['active']:
                raise ValidationError(
                    'Please choose an available design category.'
                )

        return IDP.find_all_with_images(
            property_type,
            subtype_id,
            selected_category_id
        )

    @staticmethod
    def search_designers_by_name(name=''):
        """C19: search designers by name."""
        name = ' '.join((name or '').split())

        if len(name) > SearchController.MAX_NAME_LENGTH:
            raise ValidationError(
                f'Designer name must be '
                f'{SearchController.MAX_NAME_LENGTH} characters or fewer.'
            )

        return name, DesignerSearch.find_by_name(name)
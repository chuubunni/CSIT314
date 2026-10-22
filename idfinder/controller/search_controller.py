from idfinder.controller.errors import ValidationError
from idfinder.entities.housing import Housing
from idfinder.entities.idp import IDP


class SearchController:
    """Validate filter values, then ask the project entity for matching records."""

    @staticmethod
    def options():
        return Housing.types(), Housing.subtypes()

    @staticmethod
    def search(property_type='', property_subtype_id=''):
        property_type = (property_type or '').strip()
        if property_type and Housing.find_type(property_type) is None:
            raise ValidationError('Please choose a valid housing type.')
        subtype_id = None
        if property_subtype_id:
            try:
                subtype_id = int(property_subtype_id)
            except (ValueError, TypeError):
                raise ValidationError('Please choose a valid housing subtype.')
            subtype = Housing.find_subtype(subtype_id)
            if subtype is None:
                raise ValidationError('Please choose a valid housing subtype.')
            if not property_type or subtype['type_code'] != property_type:
                raise ValidationError('The subtype must belong to the selected housing type.')
        return IDP.find_all_with_images(property_type, subtype_id)
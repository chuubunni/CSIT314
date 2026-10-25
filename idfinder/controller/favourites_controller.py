# C08: save rules use the repo's existing entities and error conventions.
from idfinder.entities.favourites import Favourites
from idfinder.controller.errors import ValidationError


class FavouritesController:
    def save_favourite(self, customer_id, idp_id):
        if idp_id <= 0:
            raise ValidationError('Choose a valid project.')
        return Favourites.add(customer_id, idp_id)

    def list_favourites(self, customer_id):
        # C09: the customer id always comes from the logged-in user, so only their own list is shown.
        return Favourites.find_projects(customer_id)

    def favourite_ids(self, customer_id):
        return Favourites.find_project_ids(customer_id)

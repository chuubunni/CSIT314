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

    def compare_projects(self, customer_id, selected_ids):
        if len(selected_ids) != 2:
            raise ValidationError('Select exactly two projects.')

        try:
            first_id, second_id = map(int, selected_ids)
        except (TypeError, ValueError):
            raise ValidationError('Choose valid projects.')

        if first_id <= 0 or second_id <= 0 or first_id == second_id:
            raise ValidationError('Choose two different projects.')

        rows = Favourites.find_comparison(
            customer_id, first_id, second_id
        )

        if len(rows) != 2:
            raise ValidationError(
                'Both projects must be available in your favourites.'
            )

        projects = {row['id']: dict(row) for row in rows}
        first = projects[first_id]
        second = projects[second_id]

        summary = []
        difference = abs(first['price'] - second['price'])

        if difference:
            cheaper = (
                first if first['price'] < second['price'] else second
            )
            summary.append(
                f"{cheaper['title']} costs S${difference:,.0f} less."
            )
        else:
            summary.append('Both projects have the same listed price.')

        if (
            first['property_type'] != second['property_type']
            or first['property_subtype_id']
            != second['property_subtype_id']
        ):
            summary.append(
                'The property categories differ, so prices may not '
                'represent comparable work.'
            )

        if first['favourite_count'] == second['favourite_count']:
            summary.append(
                'Both projects have the same number of favourites.'
            )
        else:
            popular = max(
                (first, second),
                key=lambda project: project['favourite_count']
            )
            summary.append(
                f"{popular['title']} has more customer favourites."
            )

        if first['designer_id'] == second['designer_id']:
            summary.append(
                'Both projects have the same designer, so their '
                'designer review statistics are identical.'
            )
        elif first['review_count'] and second['review_count']:
            if first['average_rating'] == second['average_rating']:
                summary.append(
                    'Both designers have the same average review rating.'
                )
            else:
                higher = max(
                    (first, second),
                    key=lambda project: project['average_rating']
                )
                summary.append(
                    f"{higher['designer_name']} has the higher average "
                    'visible review rating. Compare the review counts too.'
                )
        else:
            summary.append(
                'At least one designer has no visible reviews, so a '
                'rating comparison is incomplete.'
            )

        return [first, second], summary
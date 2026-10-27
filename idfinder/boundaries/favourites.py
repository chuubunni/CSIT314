from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for
)

from idfinder.boundaries.auth import auth_boundary
from idfinder.boundaries.customer import customer_boundary
from idfinder.boundaries.form_security import validate_form_token

from idfinder.controller.favourites_controller import FavouritesController

from idfinder.controller.errors import (
    NotFoundError,
    PermissionDenied,
    ValidationError
)


bp = Blueprint(
    'favourites',
    __name__,
    url_prefix='/favourites'
)


class favourites_boundary:

    @bp.route('/')
    @auth_boundary.login_required
    @customer_boundary.customer_required
    def list_favourites():
        """Display the customer's saved projects."""
        return render_template(
            'customer/favourites.html',
            projects=FavouritesController().list_favourites(
                g.user['id']
            )
        )

    @bp.route(
        '/projects/<int:idp_id>',
        methods=('POST',)
    )
    @auth_boundary.login_required
    @customer_boundary.customer_required
    def save_favourite(idp_id):
        validate_form_token()

        try:
            added = FavouritesController().save_favourite(
                g.user['id'],
                idp_id
            )

        except NotFoundError as error:
            abort(404, description=str(error))

        except PermissionDenied as error:
            abort(403, description=str(error))

        except ValidationError as error:
            abort(400, description=str(error))

        flash(
            'Project saved to favourites.'
            if added
            else 'This project is already in your favourites.'
        )

        if request.form.get('return_to') == 'detail':
            return redirect(
                url_for(
                    'home.project_detail',
                    idp_id=idp_id
                )
            )

        # Keep the selected filters after saving a project.
        filters = {
            key: request.form[key]
            for key in (
                'property_type',
                'property_subtype_id',
                'category_id'
            )
            if request.form.get(key)
        }

        return redirect(
            url_for('home.index', **filters)
        )
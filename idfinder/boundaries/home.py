from flask import Blueprint, render_template, g, request
from werkzeug.exceptions import abort

from idfinder.entities.idp import IDP
from idfinder.controller.search_controller import SearchController
from idfinder.controller.errors import ValidationError
from idfinder.entities.idp_media import IDPMedia
from idfinder.entities.idp_view import IDPView

# C08: add saved-state IDs and form tokens without changing housing filters.
from idfinder.controller.favourites_controller import FavouritesController
from idfinder.boundaries.form_security import form_token

bp = Blueprint('home', __name__)

class home_boundary():

    @bp.route('/')
    def index():
        """Homepage filters use GET so results can be bookmarked and shared."""
        selected_type = request.args.get('property_type', '').strip()
        selected_subtype = request.args.get('property_subtype_id', '').strip()
        property_types, property_subtypes = SearchController.options()
        error = None
        try:
            projects = SearchController.search(selected_type, selected_subtype)
        except ValidationError as exc:
            projects = []
            error = str(exc)
        # C08: public/designer browsing is unchanged; only customers get save forms.
        customer = g.user is not None and g.user['Usertype'] == 'customer'
        saved_ids = FavouritesController().favourite_ids(g.user['id']) if customer else set()
        return render_template(
            'home/index.html', idps=projects,
            property_types=property_types, property_subtypes=property_subtypes,
            selected_type=selected_type, selected_subtype=selected_subtype,
            filter_error=error,
            favourite_ids=saved_ids, story_form_token=form_token() if customer else None,
        ), 400 if error else 200


    @bp.route('/projects/<int:idp_id>')
    def project_detail(idp_id):
        """Public project detail page with view tracking."""

        # Retrieve the selected project
        project = IDP.find(idp_id)

        # Return 404 if the project does not exist
        if project is None:
            abort(404)

        # Retrieve all images belonging to this project
        images = IDPMedia.find_by_idp(idp_id)

        # Identify the viewer (None if not logged in)
        viewer_id = g.user['id'] if g.user is not None else None

        # Do not count the designer viewing their own project
        if viewer_id != project['designer_id']:
            IDPView.record(idp_id, viewer_id)

        # C08: allow saving from the existing detail page as well as project cards.
        customer = g.user is not None and g.user['Usertype'] == 'customer'
        saved_ids = FavouritesController().favourite_ids(g.user['id']) if customer else set()

        # Display the public project detail page
        return render_template(
            'home/project_detail.html',
            project=project,
            images=images,
            favourite_ids=saved_ids, story_form_token=form_token() if customer else None
        )

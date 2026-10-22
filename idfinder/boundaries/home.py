from flask import Blueprint, render_template, g, request
from werkzeug.exceptions import abort

from idfinder.entities.idp import IDP
from idfinder.controller.search_controller import SearchController
from idfinder.controller.errors import ValidationError
from idfinder.entities.idp_media import IDPMedia
from idfinder.entities.idp_view import IDPView

bp = Blueprint('home', __name__)

class home_boundary():

    @bp.route('/')
    def index():
        """Homepage filters use GET so results can be bookmarked and shared."""
        selected_type = request.args.get('property_type', '').strip()
        selected_subtype = request.args.get('property_subtype_id', '').strip()
        housing_types, housing_subtypes = SearchController.options()
        error = None
        try:
            projects = SearchController.search(selected_type, selected_subtype)
        except ValidationError as exc:
            projects = []
            error = str(exc)
        return render_template(
            'home/index.html', idps=projects,
            housing_types=housing_types, housing_subtypes=housing_subtypes,
            selected_type=selected_type, selected_subtype=selected_subtype,
            filter_error=error,
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

        # Display the public project detail page
        return render_template(
            'home/project_detail.html',
            project=project,
            images=images
        )
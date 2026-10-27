from flask import Blueprint, render_template, g, request
from werkzeug.exceptions import abort

from idfinder.entities.idp import IDP
from idfinder.entities.idp_media import IDPMedia
from idfinder.entities.idp_view import IDPView

from idfinder.controller.search_controller import SearchController
from idfinder.controller.errors import ValidationError
from idfinder.controller.favourites_controller import FavouritesController

from idfinder.boundaries.form_security import form_token


bp = Blueprint('home', __name__)


class home_boundary:

    @bp.route('/')
    def index():
        """Display projects with housing and design category filters."""
        selected_type = request.args.get(
            'property_type', ''
        ).strip()

        selected_subtype = request.args.get(
            'property_subtype_id', ''
        ).strip()

        selected_category = request.args.get(
            'category_id', ''
        ).strip()

        property_types, property_subtypes = (
            SearchController.options()
        )

        categories = SearchController.categories()

        error = None

        try:
            projects = SearchController.search(
                selected_type,
                selected_subtype,
                selected_category
            )
        except ValidationError as exc:
            projects = []
            error = str(exc)

        customer = (
            g.user is not None
            and g.user['Usertype'] == 'customer'
        )

        saved_ids = (
            FavouritesController().favourite_ids(g.user['id'])
            if customer
            else set()
        )

        return render_template(
            'home/index.html',
            idps=projects,
            property_types=property_types,
            property_subtypes=property_subtypes,
            categories=categories,
            selected_type=selected_type,
            selected_subtype=selected_subtype,
            selected_category=selected_category,
            filter_error=error,
            favourite_ids=saved_ids,
            story_form_token=form_token() if customer else None
        ), 400 if error else 200

    @bp.route('/projects/<int:idp_id>')
    def project_detail(idp_id):
        """Display project details and record views."""
        project = IDP.find(idp_id)

        if project is None:
            abort(404)

        images = IDPMedia.find_by_idp(idp_id)

        viewer_id = (
            g.user['id']
            if g.user is not None
            else None
        )

        # Do not count the designer viewing their own project.
        if viewer_id != project['designer_id']:
            IDPView.record(idp_id, viewer_id)

        customer = (
            g.user is not None
            and g.user['Usertype'] == 'customer'
        )

        saved_ids = (
            FavouritesController().favourite_ids(g.user['id'])
            if customer
            else set()
        )

        return render_template(
            'home/project_detail.html',
            project=project,
            images=images,
            favourite_ids=saved_ids,
            story_form_token=form_token() if customer else None
        )
from flask import Blueprint, render_template

from flask import Blueprint, render_template, g
from werkzeug.exceptions import abort

from idfinder.entities.idp import IDP
from idfinder.entities.idp_media import IDPMedia
from idfinder.entities.idp_view import IDPView

bp = Blueprint('home', __name__)

@bp.route('/')
def index():
    """Homepage: display all projects with their images."""
    return render_template(
        'home/index.html',
        idps=IDP.find_all_with_images()
    )


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

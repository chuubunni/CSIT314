import functools

from flask import (
    Blueprint, current_app, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from myfirstapp.boundaries.auth import login_required
from myfirstapp.controller.errors import NotFoundError, PermissionDenied, ValidationError
from myfirstapp.controller.portfolio_controller import PortfolioController

bp = Blueprint('designer', __name__)


def designer_required(view):
    """Use under @login_required: only Interior Designers may manage IDPs."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user['Usertype'] != 'designer':
            abort(403)
        return view(**kwargs)
    return wrapped_view


def controller():
    return PortfolioController(current_app.config['UPLOAD_FOLDER'])


@bp.errorhandler(NotFoundError)
def handle_not_found(error):
    return str(error), 404


@bp.errorhandler(PermissionDenied)
def handle_permission_denied(error):
    return str(error), 403


@bp.route('/portfolio')
@login_required
@designer_required
def portfolio():
    """The logged-in designer's IDPs."""
    return render_template('designer/portfolio.html',
                           idps=controller().list_portfolio(g.user['id']))


@bp.route('/portfolio/new', methods=('GET', 'POST'))
@login_required
@designer_required
def create_idp():
    ctrl = controller()
    if request.method == 'POST':
        try:
            idp_id = ctrl.create_idp(
                g.user['id'], request.form.get('title'), request.form.get('description'),
                request.form.get('category_id'), request.form.get('status'))
            return redirect(url_for('designer.view_idp', idp_id=idp_id))
        except ValidationError as error:
            flash(str(error))
    return render_template('designer/create_port.html', idp=None,
                           categories=ctrl.categories(), form=request.form)


@bp.route('/portfolio/<int:idp_id>')
@login_required
@designer_required
def view_idp(idp_id):
    idp, images = controller().get_idp_with_media(idp_id, g.user['id'])
    return render_template('designer/idp_detail.html', idp=idp, images=images)


@bp.route('/portfolio/<int:idp_id>/edit', methods=('GET', 'POST'))
@login_required
@designer_required
def edit_idp(idp_id):
    ctrl = controller()
    idp = ctrl.get_idp(idp_id, g.user['id'])
    if request.method == 'POST':
        try:
            ctrl.update_idp(
                idp_id, g.user['id'], request.form.get('title'),
                request.form.get('description'), request.form.get('category_id'),
                request.form.get('status'))
            return redirect(url_for('designer.view_idp', idp_id=idp_id))
        except ValidationError as error:
            flash(str(error))
    return render_template('designer/create_port.html', idp=idp,
                           categories=ctrl.categories(), form=request.form)


@bp.route('/portfolio/<int:idp_id>/delete', methods=('POST',))
@login_required
@designer_required
def delete_idp(idp_id):
    controller().delete_idp(idp_id, g.user['id'])
    return redirect(url_for('designer.portfolio'))


@bp.route('/portfolio/<int:idp_id>/images', methods=('POST',))
@login_required
@designer_required
def upload_image(idp_id):
    try:
        controller().add_image(idp_id, g.user['id'], request.files.get('file'),
                               request.form.get('caption', ''))
    except ValidationError as error:
        flash(str(error))
    return redirect(url_for('designer.view_idp', idp_id=idp_id))


@bp.route('/portfolio/media/<int:media_id>/remove', methods=('POST',))
@login_required
@designer_required
def remove_media(media_id):
    idp_id = controller().remove_media(media_id, g.user['id'])
    return redirect(url_for('designer.view_idp', idp_id=idp_id))
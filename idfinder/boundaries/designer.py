import functools

from flask import (
    Blueprint, current_app, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from idfinder.controller.errors import NotFoundError, PermissionDenied, ValidationError
from idfinder.controller.portfolio_controller import PortfolioController

bp = Blueprint('designer', __name__)

class designer_boundary():
    def login_required(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                return redirect(url_for('auth.login'))
            return view(**kwargs)
        return wrapped_view

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


    def _idp_form_fields():
        """The fields shared by the create and edit forms, by name (so the order can't get mixed up)."""
        return dict(
            title=request.form.get('title'),
            description=request.form.get('description'),
            property_type=request.form.get('property_type'),
            property_subtype_id=request.form.get('property_subtype_id'),
            price=request.form.get('price'),
            status=request.form.get('status'),
            category_ids=request.form.getlist('category_ids'),   # one value per ticked checkbox
        )


    @bp.route('/portfolio')
    @login_required
    @designer_required
    def portfolio():
        """The logged-in designer's IDPs."""
        return render_template('designer/portfolio.html',
                            idps=designer_boundary.controller().list_portfolio(g.user['id']))


    @bp.route('/portfolio/new', methods=('GET', 'POST'))
    @login_required
    @designer_required
    def create_idp():
        ctrl = designer_boundary.controller()
        if request.method == 'POST':
            try:
                idp_id = ctrl.create_idp(g.user['id'], **designer_boundary._idp_form_fields())
                return redirect(url_for('designer.view_idp', idp_id=idp_id))
            except ValidationError as error:
                flash(str(error))
        return render_template('designer/create_port.html', idp=None,
                            categories=ctrl.categories(), form=request.form,
                            selected_categories=[],
                            property_types=ctrl.property_options()[0],
                            property_subtypes=ctrl.property_options()[1])


    @bp.route('/portfolio/<int:idp_id>')
    @login_required
    @designer_required
    def view_idp(idp_id):
        idp, images = designer_boundary.controller().get_idp_with_media(idp_id, g.user['id'])
        return render_template('designer/idp_detail.html', idp=idp, images=images)


    @bp.route('/portfolio/<int:idp_id>/edit', methods=('GET', 'POST'))
    @login_required
    @designer_required
    def edit_idp(idp_id):
        ctrl = designer_boundary.controller()
        idp = ctrl.get_idp(idp_id, g.user['id'])          # 404 / 403 if not found or not yours
        if request.method == 'POST':
            try:
                ctrl.update_idp(idp_id, g.user['id'], **designer_boundary._idp_form_fields())
                return redirect(url_for('designer.view_idp', idp_id=idp_id))
            except ValidationError as error:
                flash(str(error))
        return render_template('designer/create_port.html', idp=idp,
                            categories=ctrl.categories(), form=request.form,
                            selected_categories=ctrl.get_category_ids(idp_id, g.user['id']),
                            property_types=ctrl.property_options()[0],
                            property_subtypes=ctrl.property_options()[1])


    @bp.route('/portfolio/<int:idp_id>/delete', methods=('POST',))
    @login_required
    @designer_required
    def delete_idp(idp_id):
        designer_boundary.controller().delete_idp(idp_id, g.user['id'])
        return redirect(url_for('designer.portfolio'))


    @bp.route('/portfolio/<int:idp_id>/images', methods=('POST',))
    @login_required
    @designer_required
    def upload_image(idp_id):
        try:
            designer_boundary.controller().add_image(idp_id, g.user['id'], request.files.get('file'))
        except ValidationError as error:
            flash(str(error))
        return redirect(url_for('designer.view_idp', idp_id=idp_id))


    @bp.route('/portfolio/media/<int:mediaID>/remove', methods=('POST',))
    @login_required
    @designer_required
    def remove_media(mediaID):
        idp_id = designer_boundary.controller().remove_media(mediaID, g.user['id'])
        return redirect(url_for('designer.view_idp', idp_id=idp_id))


    @bp.route('/profile')
    @login_required
    @designer_required
    def profile():
        return render_template('designer/profile.html', editing=False, form={},
                        profile=designer_boundary.controller().get_profile(g.user['id']))

    @bp.route('/profile/edit', methods=('GET', 'POST'))
    @login_required
    @designer_required
    def edit_profile():
        ctrl = designer_boundary.controller()
        if request.method == 'POST':
            try:
                ctrl.update_profile(
                    g.user['id'],
                    request.form.get('name'),
                    request.form.get('email'),
                    request.form.get('phone'),
                )
                flash('Profile updated.')
                return redirect(url_for('designer.profile'))
            except ValidationError as error:
                flash(str(error))
        return render_template('designer/profile.html', editing=True, form=request.form,
                               profile=ctrl.get_profile(g.user['id']))

    @bp.route('/profile/company/edit', methods=('GET', 'POST'))
    @login_required
    @designer_required
    def edit_company_profile():
        ctrl = designer_boundary.controller()

        if request.method == 'POST':
            try:
                ctrl.update_company_profile(
                    g.user['id'],
                    request.form.get('companyName'),
                    request.form.get('companyLine'),
                    request.form.get('companyEmail')
                )
            except ValidationError as error:
                flash(str(error))
            else:
                flash('Company profile updated.')
                return redirect(url_for('designer.profile'))

        return render_template(
            'designer/profile.html',
            editing=False,
            editing_company=True,
            form=request.form,
            profile=ctrl.get_profile(g.user['id'])
        )

    # ID19: add a bulk page to the existing designer_boundary class.
    @bp.route('/portfolio/categories', methods=('GET', 'POST'))
    @login_required
    @designer_required
    def update_selected_categories():
        from idfinder.boundaries.form_security import form_token, validate_form_token
        ctrl = designer_boundary.controller()
        if request.method == 'POST':
            validate_form_token()
            try:
                count = ctrl.update_selected_categories(
                    g.user['id'], request.form.getlist('idp_ids'), request.form.getlist('category_ids'))
            except ValidationError as error:
                flash(str(error))
            else:
                flash(f'Categories updated for {count} project(s).')
                return redirect(url_for('designer.update_selected_categories'))
        return render_template('designer/bulk_categories.html',
                               idps=ctrl.list_portfolio(g.user['id']), categories=ctrl.categories(),
                               form_token=form_token(), selected_projects=request.form.getlist('idp_ids'),
                               selected_categories=request.form.getlist('category_ids'))

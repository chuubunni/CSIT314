import functools

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from idfinder.boundaries.auth import auth_boundary
from idfinder.controller.errors import NotFoundError, ValidationError
from idfinder.controller.platform_controller import PlatformController

bp = Blueprint('platform', __name__, url_prefix='/platform')

class platform_boundary():
    def login_required(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                return redirect(url_for('auth.login'))
            return view(**kwargs)
        return wrapped_view

    def platform_required(view):
        @functools.wraps(view)
        def wrapper(**kwargs):
            if g.user['Usertype'] != 'manager':
                abort(403)
            return view(**kwargs)
        return wrapper


    def controller():
        return PlatformController()


    @bp.route('/')
    @login_required
    @platform_required
    def dashboard():
        period = request.args.get('period', 'daily')
        if period not in ('daily', 'weekly', 'monthly'):
            abort(400)
        ctrl = platform_boundary.controller()
        return render_template('platform/dashboard.html', categories=ctrl.categories(request.args.get('q', '')),
                            q=request.args.get('q', ''), period=period,
                            summary=ctrl.report(period), interest=ctrl.interest())


    @bp.route('/profile')
    @login_required 
    @platform_required 
    def profile():
        return render_template('platform/profile.html', editing=False, form={},
                profile=platform_boundary.controller().get_profile(g.user['id']))

    @bp.route('/profile/edit', methods=('GET', 'POST'))
    @login_required
    @platform_required
    def edit_profile():
        ctrl = platform_boundary.controller()
        if request.method == 'POST':
            try:
                ctrl.edit_profile(
                    g.user['id'],
                    request.form.get('name'),
                    request.form.get('email'),
                    request.form.get('phone'),
                )
                flash('Profile updated.')
                return redirect(url_for('platform.profile'))
            except ValidationError as error:
                flash(str(error))
        return render_template('platform/profile.html', editing=True, form=request.form,
                            profile=ctrl.get_profile(g.user['id']))



    @bp.route('/categories/add', methods=['POST'])
    @login_required
    @platform_required
    def add_category():
        try:
            platform_boundary.controller().add_category(request.form.get('name'))
            flash('Category added.')
        except ValidationError as error:
            flash(str(error))
        return redirect(url_for('platform.dashboard'))


    @bp.route('/categories/<int:category_id>/edit', methods=['POST'])
    @login_required
    @platform_required
    def edit_category(category_id):
        try:
            platform_boundary.controller().edit_category(category_id, request.form.get('name'),
                                    request.form.get('active') == '1')
            flash('Category updated.')
        except ValidationError as error:
            flash(str(error))
        except NotFoundError:
            abort(404)
        return redirect(url_for('platform.dashboard'))


    @bp.route('/categories/<int:category_id>/delete', methods=['POST'])
    @login_required
    @platform_required
    def delete_category(category_id):
        try:
            platform_boundary.controller().remove_category(category_id)
            flash('Category removed.')
        except ValidationError as error:
            flash(str(error))
        except NotFoundError:
            abort(404)
        return redirect(url_for('platform.dashboard'))
import functools

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from myfirstapp.boundaries.auth import login_required
from myfirstapp.controller.errors import NotFoundError, ValidationError
from myfirstapp.controller.platform_controller import PlatformController

bp = Blueprint('platform', __name__, url_prefix='/platform')


def platform_required(view):
    @functools.wraps(view)
    def wrapper(**kwargs):
        if g.user['Usertype'] != 'platform':
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
    ctrl = controller()
    return render_template('platform/dashboard.html', categories=ctrl.categories(request.args.get('q', '')),
                           q=request.args.get('q', ''), period=period,
                           summary=ctrl.report(period), interest=ctrl.interest())


@bp.route('/categories/add', methods=['POST'])
@login_required
@platform_required
def add_category():
    try:
        controller().add_category(request.form.get('name'))
        flash('Category added.')
    except ValidationError as error:
        flash(str(error))
    return redirect(url_for('platform.dashboard'))


@bp.route('/categories/<int:category_id>/edit', methods=['POST'])
@login_required
@platform_required
def edit_category(category_id):
    try:
        controller().edit_category(category_id, request.form.get('name'),
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
        controller().remove_category(category_id)
        flash('Category removed.')
    except ValidationError as error:
        flash(str(error))
    except NotFoundError:
        abort(404)
    return redirect(url_for('platform.dashboard'))
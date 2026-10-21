import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from idfinder.controller.customer_controller import CustomerController
from idfinder.controller.errors import NotFoundError, ValidationError

bp = Blueprint('customer', __name__, url_prefix='/customer')

class customer_boundary():
    def login_required(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                return redirect(url_for('auth.login'))
            return view(**kwargs)
        return wrapped_view

    
    def customer_required(view):
        """Use under @login_required: only customers have a customer profile."""
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if g.user['Usertype'] != 'customer':
                abort(403)
            return view(**kwargs)
        return wrapped_view


    def controller():
        return CustomerController()


    @bp.errorhandler(NotFoundError)
    def handle_not_found(error):
        return str(error), 404


    @bp.route('/profile')
    @login_required
    @customer_required
    def profile():
        """The logged-in customer's own profile (read-only)."""
        return render_template('customer/profile.html', editing=False, form={},
                            profile=customer_boundary.controller().get_profile(g.user['id']))


    @bp.route('/profile/edit', methods=('GET', 'POST'))
    @login_required
    @customer_required
    def edit_profile():
        ctrl = customer_boundary.controller()
        if request.method == 'POST':
            try:
                ctrl.update_profile(
                    g.user['id'],
                    request.form.get('name'),
                    request.form.get('email'),
                    request.form.get('phone'),
                    request.form.get('current_house_type'),
                    request.form.get('received_keys'),
                )
                flash('Profile updated.')
                return redirect(url_for('customer.profile'))
            except ValidationError as error:
                flash(str(error))
        return render_template('customer/profile.html', editing=True, form=request.form,
                            profile=ctrl.get_profile(g.user['id']))
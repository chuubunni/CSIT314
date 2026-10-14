import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)

from myfirstapp.controller.auth_controller import auth_control
from myfirstapp.controller.errors import ValidationError

bp = Blueprint('auth', __name__, url_prefix='/auth')
# Boundary: reads the request, calls auth_control, and turns the result into
# a flash message, a session change, a redirect or a template. No SQL, no rules.


@bp.before_app_request
# runs before every view, whatever URL is requested
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = auth_control.get_user(user_id)  # g.user lasts for the length of the request


@bp.route('/logout')
def log_out_user():
    session.clear()  # removes user_id from session
    return redirect(url_for('index'))


# to require user to be logged in for editing:
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view


@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        try:
            user = auth_control.authenticate_user(
                request.form.get('email'), request.form.get('password'))
        except ValidationError as error:
            flash(str(error))
        else:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('index'))
    return render_template('auth/login.html')  # also shown again after an error


@bp.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        Usertype = request.form.get('type')
        try:
            user_id = auth_control.do_register(
                request.form.get('name'), request.form.get('password'),
                request.form.get('email'), request.form.get('phone'), Usertype)
        except ValidationError as error:
            flash(str(error))
        else:
            if Usertype == 'designer':
                # remember who is mid-registration; the browser can't change a signed session
                session['pending_designer_id'] = user_id
                return redirect(url_for('auth.designer_register'))
            return redirect(url_for('auth.login'))
    return render_template('auth/register.html')


@bp.route('/designer_register', methods=('GET', 'POST'))
def designer_register():
    user_id = session.get('pending_designer_id')
    if user_id is None:                       # nobody is mid-registration
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        try:
            auth_control.register_designer(
                user_id,
                request.form.get('companyName'),
                request.form.get('companyLine'),
                request.form.get('companyDescription'),
                request.form.get('companyEmail'),
            )
        except ValidationError as error:
            flash(str(error))
        else:
            session.pop('pending_designer_id')
            return redirect(url_for('auth.login'))

    return render_template('auth/designer_register.html')
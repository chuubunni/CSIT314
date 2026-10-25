import functools

from flask import Blueprint, g, redirect, render_template, request, url_for
from werkzeug.exceptions import abort

from idfinder.controller.errors import ValidationError
from idfinder.controller.search_controller import SearchController

bp = Blueprint('search', __name__)


class search_boundary():
    def login_required(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                return redirect(url_for('auth.login'))
            return view(**kwargs)
        return wrapped_view

    def customer_required(view):
        """Use under @login_required: only customers search for designers."""
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if g.user['Usertype'] != 'customer':
                abort(403)
            return view(**kwargs)
        return wrapped_view

    @bp.route('/designers')
    @login_required
    @customer_required
    def designers():
        """C19: search interior designers by name (GET, so results can be bookmarked)."""
        query = request.args.get('name', '')
        error = None
        try:
            query, results = SearchController.search_designers_by_name(query)
        except ValidationError as exc:
            query, results, error = query.strip(), [], str(exc)
        return render_template('search/designers.html', designers=results,
                               query=query, error=error), 400 if error else 200

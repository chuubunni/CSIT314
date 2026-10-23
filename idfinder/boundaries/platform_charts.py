from flask import Blueprint, jsonify, render_template, request

from idfinder.boundaries.platform import platform_boundary
from idfinder.controller.errors import ValidationError
from idfinder.controller.platform_charts_controller import PlatformChartsController

# Boundary for the manager's graphs: one page (/platform/charts/) that loads its data
# from two JSON routes, so the manager can change the week without reloading the page.
bp = Blueprint('platform_charts', __name__, url_prefix='/platform/charts')


class platform_charts_boundary():

    @bp.route('/')
    @platform_boundary.login_required
    @platform_boundary.platform_required
    def page():
        return render_template('platform/charts.html')

    @bp.route('/weekly')
    @platform_boundary.login_required
    @platform_boundary.platform_required
    def weekly():
        """PM21: ?end=YYYY-MM-DD (optional) is the last day of the 7-day window."""
        try:
            data = PlatformChartsController().weekly_activity(request.args.get('end'))
        except ValidationError as error:
            return jsonify(error=str(error)), 400
        return jsonify(data)

    @bp.route('/categories')
    @platform_boundary.login_required
    @platform_boundary.platform_required
    def categories():
        """PM23: views and shortlists per design category."""
        return jsonify(PlatformChartsController().interest_by_category())

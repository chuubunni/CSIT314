from flask import Blueprint, jsonify, render_template, request

from idfinder.boundaries.platform import ManagerOnlyView
from idfinder.controller.errors import ValidationError
from idfinder.controller.platform_charts_controller import PlatformChartsController

# BOUNDARY for the manager's graphs (PM21, PM23): one page (/platform/charts/) that loads
# its data from two JSON routes, so the manager can change the week without reloading.
# ManagerOnlyView (from platform.py) means only platform managers can open any of them.
platform_charts_bp = Blueprint('platform_charts', __name__, url_prefix='/platform/charts')


class ChartsJsonView(ManagerOnlyView):
    """Same rules as ManagerOnlyView, but the JSON routes answer with a JSON error
    (401/403) instead of redirecting to the login page."""

    def deny(self, status):
        return jsonify(error='Please log in as a platform manager.' if status == 401
                       else 'Only platform managers can see this.'), status


# ======================================================================
# PM21 + PM23: the page that shows both graphs (/platform/charts/)
# ======================================================================
class ChartsPageView(ManagerOnlyView):
    def get(self):
        return render_template('platform/charts.html')


# ======================================================================
# PM21 START: weekly activity graph (boundary part)
# ======================================================================
class WeeklyActivityView(ChartsJsonView):
    def get(self):
        """?end=YYYY-MM-DD (optional) is the last day of the 7-day window."""
        try:
            data = PlatformChartsController().weekly_activity(request.args.get('end'))
        except ValidationError as error:
            return jsonify(error=str(error)), 400          # bad date -> 400 with a message
        return jsonify(data)

# ======================= PM21 END (boundary part) =====================


# ======================================================================
# PM23 START: project interest by design category (boundary part)
# ======================================================================
class CategoryInterestView(ChartsJsonView):
    def get(self):
        return jsonify(PlatformChartsController().interest_by_category())

# ======================= PM23 END (boundary part) =====================

# ======================================================================
# PM21 / PM23 (extra graphs): trend + forecast, heatmap, category trend, ratings
# ======================================================================
class TrendView(ChartsJsonView):
    def get(self):
        """?metric=views|projects|favourites|users&end=YYYY-MM-DD (both optional)."""
        try:
            data = PlatformChartsController().trend(request.args.get('metric', 'views'), request.args.get('end'))
        except ValidationError as error:
            return jsonify(error=str(error)), 400
        return jsonify(data)


class HeatmapView(ChartsJsonView):
    def get(self):
        """?end=YYYY-MM-DD&tz=480 (tz = minutes east of UTC, so hours match the manager's clock)."""
        try:
            data = PlatformChartsController().heatmap(request.args.get('end'), request.args.get('tz'))
        except ValidationError as error:
            return jsonify(error=str(error)), 400
        return jsonify(data)


class CategoryTrendView(ChartsJsonView):
    def get(self):
        try:
            data = PlatformChartsController().category_trend(request.args.get('end'))
        except ValidationError as error:
            return jsonify(error=str(error)), 400
        return jsonify(data)


class RatingsOverviewView(ChartsJsonView):
    def get(self):
        return jsonify(PlatformChartsController().ratings_overview())


# endpoints keep the names the templates use: platform_charts.page / .weekly / .categories
platform_charts_bp.add_url_rule('/', view_func=ChartsPageView.as_view('page'))
platform_charts_bp.add_url_rule('/weekly', view_func=WeeklyActivityView.as_view('weekly'))
platform_charts_bp.add_url_rule('/categories', view_func=CategoryInterestView.as_view('categories'))
platform_charts_bp.add_url_rule('/trend', view_func=TrendView.as_view('trend'))
platform_charts_bp.add_url_rule('/heatmap', view_func=HeatmapView.as_view('heatmap'))
platform_charts_bp.add_url_rule('/category-trend', view_func=CategoryTrendView.as_view('category_trend'))
platform_charts_bp.add_url_rule('/ratings', view_func=RatingsOverviewView.as_view('ratings'))

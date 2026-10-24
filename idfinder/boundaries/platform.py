from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from flask.views import MethodView

from idfinder.controller.errors import NotFoundError, ValidationError
from idfinder.controller.platform_charts_controller import PlatformChartsController
from idfinder.controller.platform_controller import PlatformController

bp = Blueprint('platform', __name__, url_prefix='/platform')

# Boundary: reads the request, calls a controller, turns the result into a
# flash message, redirect or template. No SQL, no business rules.


class ManagerOnlyView(MethodView):
    """Base class: not logged in -> login page (401 for JSON); not a manager -> 403."""

    def deny(self, status):
        if status == 401:
            return redirect(url_for('auth.login'))
        abort(403)

    def dispatch_request(self, **kwargs):
        if g.user is None:
            return self.deny(401)
        if g.user['Usertype'] != 'manager':
            return self.deny(403)
        return super().dispatch_request(**kwargs)


class DashboardView(ManagerOnlyView):
    """GET /platform/dashboard (also /platform/): summary widget + category tools."""

    def get(self):
        period = request.args.get('period', 'daily')
        if period not in ('daily', 'weekly', 'monthly'):
            abort(400)
        search = request.args.get('q', '')
        controller = PlatformController()
        summary = PlatformChartsController().get_dashboard_summary()
        return render_template(
            'platform/dashboard.html',
            categories=controller.categories(search),
            q=search,
            period=period,
            summary=controller.report(period),
            interest=controller.interest(),
            # PM21 / PM23 widget data (always present, never undefined)
            weekly_summary={'total_views': summary['weekly_views'],
                            'total_saves': summary['weekly_saves'],
                            'available': summary['available']},
            category_summary={'top_category': summary['top_category'],
                              'available': summary['available']},
        )


class ProfileView(ManagerOnlyView):
    def get(self):
        try:
            profile = PlatformController().get_profile(g.user['id'])
        except NotFoundError:
            abort(404)
        return render_template('platform/profile.html', editing=False, form={}, profile=profile)


class EditProfileView(ManagerOnlyView):
    def get(self):
        return self._render(request.form)

    def post(self):
        try:
            PlatformController().edit_profile(
                g.user['id'],
                request.form.get('name'),
                request.form.get('email'),
                request.form.get('phone'),
            )
            flash('Profile updated.')
            return redirect(url_for('platform.profile'))
        except ValidationError as error:
            flash(str(error))
        except NotFoundError:
            abort(404)
        return self._render(request.form)

    @staticmethod
    def _render(form):
        try:
            profile = PlatformController().get_profile(g.user['id'])
        except NotFoundError:
            abort(404)
        return render_template('platform/profile.html', editing=True, form=form, profile=profile)


class AddCategoryView(ManagerOnlyView):
    def post(self):
        try:
            PlatformController().add_category(request.form.get('name'))
            flash('Category added.')
        except ValidationError as error:
            flash(str(error))
        return redirect(url_for('platform.dashboard'))


class EditCategoryView(ManagerOnlyView):
    def post(self, category_id):
        try:
            PlatformController().edit_category(
                category_id, request.form.get('name'), request.form.get('active') == '1')
            flash('Category updated.')
        except ValidationError as error:
            flash(str(error))
        except NotFoundError:
            abort(404)
        return redirect(url_for('platform.dashboard'))


class DeleteCategoryView(ManagerOnlyView):
    def post(self, category_id):
        try:
            PlatformController().remove_category(category_id)
            flash('Category removed.')
        except ValidationError as error:
            flash(str(error))
        except NotFoundError:
            abort(404)
        return redirect(url_for('platform.dashboard'))


# '/dashboard' is listed first so url_for('platform.dashboard') builds /platform/dashboard.
_dashboard = DashboardView.as_view('dashboard')
bp.add_url_rule('/dashboard', view_func=_dashboard)
bp.add_url_rule('/', view_func=_dashboard)
bp.add_url_rule('/profile', view_func=ProfileView.as_view('profile'))
bp.add_url_rule('/profile/edit', view_func=EditProfileView.as_view('edit_profile'), methods=('GET', 'POST'))
bp.add_url_rule('/categories/add', view_func=AddCategoryView.as_view('add_category'), methods=('POST',))
bp.add_url_rule('/categories/<int:category_id>/edit', view_func=EditCategoryView.as_view('edit_category'), methods=('POST',))
bp.add_url_rule('/categories/<int:category_id>/delete', view_func=DeleteCategoryView.as_view('delete_category'), methods=('POST',))
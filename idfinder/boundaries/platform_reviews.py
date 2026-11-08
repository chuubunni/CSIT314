# PM24: manager review moderation (flagged/reported reviews and permitted actions).
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from idfinder.boundaries.form_security import form_token, validate_form_token
from idfinder.boundaries.platform import ManagerOnlyView
from idfinder.controller import review_text
from idfinder.controller.errors import NotFoundError, ValidationError
from idfinder.controller.review_controller import ReviewController

platform_reviews_bp = Blueprint('platform_reviews', __name__, url_prefix='/platform/reviews')

# BOUNDARY for review moderation (manager only): see every review with its integrity flags,
# hide a review with a reason, restore it, or dismiss a designer's report.


class ModerationQueueView(ManagerOnlyView):
    def get(self):
        show = request.args.get('show', 'attention')
        if show not in ('attention', 'all'):
            abort(400)
        reviews = ReviewController().moderation_queue()
        if show == 'attention':
            reviews = [r for r in reviews if r['flags'] or r['status'] == 'hidden']
        return render_template('platform/reviews.html', reviews=reviews, show=show,
                               engine=review_text.engine_name(), form_token=form_token())


class ModerationActionView(ManagerOnlyView):
    """POST /platform/reviews/<id>/<action>  (hide | restore | dismiss)"""

    def post(self, review_id, action):
        validate_form_token()
        controller = ReviewController()
        try:
            if action == 'hide':
                controller.hide(review_id, request.form.get('reason'))
                flash('Review hidden. It no longer counts towards the designer\'s rating.')
            elif action == 'restore':
                controller.restore(review_id)
                flash('Review restored.')
            else:
                controller.dismiss_report(review_id)
                flash('Report dismissed.')
        except ValidationError as error:
            flash(str(error))
        except NotFoundError:
            abort(404)
        return redirect(url_for('platform_reviews.queue', show=request.form.get('show', 'attention')))


platform_reviews_bp.add_url_rule('/', view_func=ModerationQueueView.as_view('queue'))
platform_reviews_bp.add_url_rule('/<int:review_id>/<any(hide,restore,dismiss):action>',
                                 view_func=ModerationActionView.as_view('action'), methods=('POST',))

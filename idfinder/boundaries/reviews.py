from flask import (
    Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for
)

from idfinder.boundaries.auth import auth_boundary
from idfinder.boundaries.customer import customer_boundary
from idfinder.boundaries.designer import designer_boundary
from idfinder.boundaries.form_security import form_token, validate_form_token
from idfinder.controller import review_text
from idfinder.controller.engagement_controller import EngagementController
from idfinder.controller.errors import NotFoundError, PermissionDenied, ValidationError
from idfinder.controller.leaderboard_controller import LeaderboardController
from idfinder.controller.review_controller import ReviewController
from idfinder.entities.category import Category
from idfinder.entities.housing import Housing

bp = Blueprint('reviews', __name__)

# BOUNDARY for designer ratings: public profile + leaderboard, the customer's jobs and reviews,
# the designer's requests and replies. Only reads the request, calls a controller and picks the
# response. No SQL and no business rules in this file.


@bp.errorhandler(NotFoundError)
def _not_found(error):
    return str(error), 404


@bp.errorhandler(PermissionDenied)
def _forbidden(error):
    return str(error), 403


def _back(default_endpoint, **values):
    """Redirect to the page the form came from (same site only), else to a default page."""
    target = request.form.get('next', '')
    if target.startswith('/') and not target.startswith('//'):
        return redirect(target)
    return redirect(url_for(default_endpoint, **values))


# ======================================================================
# PUBLIC: a designer's profile with reviews, and the leaderboard
# ======================================================================
@bp.route('/designers/<int:designer_id>')
def designer_profile(designer_id):
    data = LeaderboardController().profile(designer_id)

    my_jobs, reviewable = [], []
    if g.user is not None and g.user['Usertype'] == 'customer':
        my_jobs = [j for j in EngagementController().for_customer(g.user['id'])
                   if j['designer_id'] == designer_id]
        reviewable = [j for j in my_jobs if j['status'] == 'completed' and j['review_id'] is None]
    return render_template(
        'reviews/designer_profile.html', **data,
        is_owner=g.user is not None and g.user['id'] == designer_id,
        is_customer=g.user is not None and g.user['Usertype'] == 'customer',
        my_jobs=my_jobs, reviewable=reviewable, form_token=form_token())


@bp.route('/leaderboard')
def leaderboard():
    selected = {key: request.args.get(key, '').strip() for key in ('category_id', 'property_type', 'min_reviews')}
    error, board = None, None
    try:
        board = LeaderboardController().leaderboard(
            selected['category_id'], selected['property_type'], selected['min_reviews'],
            LeaderboardController.weights_from_args(request.args))
    except ValidationError as exc:
        error = str(exc)
        board = LeaderboardController().leaderboard()          # show everyone, with the message above
    return render_template('reviews/leaderboard.html', board=board, error=error, selected=selected,
                           categories=Category.find_all_active(), property_types=Housing.types(),
                           engine=review_text.engine_name()), 400 if error else 200


@bp.route('/leaderboard.json')
def leaderboard_json():
    try:
        board = LeaderboardController().leaderboard(
            request.args.get('category_id', ''), request.args.get('property_type', ''),
            request.args.get('min_reviews', ''), LeaderboardController.weights_from_args(request.args))
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(board)


# ======================================================================
# CUSTOMER: hire a designer, follow the job, write / edit / delete a review
# ======================================================================
@bp.route('/designers/<int:designer_id>/hire', methods=('POST',))
@auth_boundary.login_required
@customer_boundary.customer_required
def hire(designer_id):
    validate_form_token()
    try:
        EngagementController().request(g.user['id'], designer_id, request.form.get('title'),
                                       request.form.get('message'), request.form.get('idp_id'))
        flash('Request sent. The designer will accept or decline it.')
        return redirect(url_for('reviews.my_jobs'))
    except ValidationError as error:
        flash(str(error))
    return redirect(url_for('reviews.designer_profile', designer_id=designer_id))


@bp.route('/my-jobs')
@auth_boundary.login_required
@customer_boundary.customer_required
def my_jobs():
    return render_template('reviews/my_jobs.html', jobs=EngagementController().for_customer(g.user['id']),
                           form_token=form_token())


@bp.route('/jobs/<int:engagement_id>/cancel', methods=('POST',))
@auth_boundary.login_required
@customer_boundary.customer_required
def cancel_job(engagement_id):
    validate_form_token()
    try:
        EngagementController().cancel(g.user['id'], engagement_id)
        flash('Job cancelled.')
    except ValidationError as error:
        flash(str(error))
    return redirect(url_for('reviews.my_jobs'))


@bp.route('/jobs/<int:engagement_id>/review', methods=('GET', 'POST'))
@auth_boundary.login_required
@customer_boundary.customer_required
def review_job(engagement_id):
    controller = ReviewController()
    try:
        job, existing = controller.for_review_form(g.user['id'], engagement_id)
    except ValidationError as error:                       # not completed yet
        flash(str(error))
        return redirect(url_for('reviews.my_jobs'))
    if request.method == 'POST':
        validate_form_token()
        try:
            if existing is None:
                controller.submit(g.user['id'], engagement_id, request.form.get('rating'), request.form.get('comment'))
                flash('Thank you! Your review has been posted.')
            else:
                controller.edit(g.user['id'], existing['id'], request.form.get('rating'), request.form.get('comment'))
                flash('Your review has been updated.')
            return redirect(url_for('reviews.designer_profile', designer_id=job['designer_id']))
        except ValidationError as error:
            flash(str(error))
    return render_template('reviews/review_form.html', job=job, existing=existing, form=request.form,
                           form_token=form_token())


@bp.route('/reviews/<int:review_id>/delete', methods=('POST',))
@auth_boundary.login_required
@customer_boundary.customer_required
def delete_review(review_id):
    validate_form_token()
    ReviewController().delete(g.user['id'], review_id)
    flash('Your review was deleted.')
    return _back('reviews.my_jobs')


# ======================================================================
# DESIGNER: answer requests, reply to and report reviews
# ======================================================================
@bp.route('/client-requests')
@auth_boundary.login_required
@designer_boundary.designer_required
def client_requests():
    return render_template('reviews/client_requests.html',
                           jobs=EngagementController().for_designer(g.user['id']), form_token=form_token())


def _job_action(action, message):
    validate_form_token()
    try:
        getattr(EngagementController(), action)(g.user['id'], request.view_args['engagement_id'])
        flash(message)
    except ValidationError as error:
        flash(str(error))
    return redirect(url_for('reviews.client_requests'))


@bp.route('/jobs/<int:engagement_id>/accept', methods=('POST',))
@auth_boundary.login_required
@designer_boundary.designer_required
def accept_job(engagement_id):
    return _job_action('accept', 'Job accepted.')


@bp.route('/jobs/<int:engagement_id>/decline', methods=('POST',))
@auth_boundary.login_required
@designer_boundary.designer_required
def decline_job(engagement_id):
    return _job_action('decline', 'Job declined.')


@bp.route('/jobs/<int:engagement_id>/complete', methods=('POST',))
@auth_boundary.login_required
@designer_boundary.designer_required
def complete_job(engagement_id):
    return _job_action('complete', 'Job marked as completed. The customer can now review it.')


@bp.route('/reviews/<int:review_id>/reply', methods=('POST',))
@auth_boundary.login_required
@designer_boundary.designer_required
def reply_review(review_id):
    validate_form_token()
    try:
        ReviewController().reply(g.user['id'], review_id, request.form.get('reply'))
        flash('Reply saved.')
    except ValidationError as error:
        flash(str(error))
    return _back('reviews.designer_profile', designer_id=g.user['id'])


@bp.route('/reviews/<int:review_id>/report', methods=('POST',))
@auth_boundary.login_required
@designer_boundary.designer_required
def report_review(review_id):
    validate_form_token()
    try:
        ReviewController().report(g.user['id'], review_id, request.form.get('reason'))
        flash('Thanks. The platform manager will take a look at this review.')
    except ValidationError as error:
        flash(str(error))
    return _back('reviews.designer_profile', designer_id=g.user['id'])

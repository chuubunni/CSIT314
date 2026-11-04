import os

from flask import Flask


def _ensure_image_review_schema(app):
    import sqlite3
    try:
        connection = sqlite3.connect(app.config['DATABASE'], timeout=app.config.get('SQLITE_TIMEOUT', 1.0))
        try:
            columns = {row[1] for row in connection.execute('PRAGMA table_info(idp)')}
            if columns and 'approval_status' not in columns:
                from .entities.image_review_schema import ImageReviewSchema
                ImageReviewSchema.apply(connection)
                app.logger.info('Applied the image-review schema migration.')
        finally:
            connection.close()
    except Exception:
        app.logger.exception('Image-review schema check failed')


def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_relative_config=True
    )

    app.config.from_mapping(
        # C18: private credentials and the session secret stay on the server.
        SECRET_KEY=os.environ.get('IDFINDER_SECRET_KEY', 'dev'),
        GEMINI_API_KEY=os.environ.get('GEMINI_API_KEY', ''),
        GEMINI_MODEL=os.environ.get('GEMINI_MODEL', 'gemini-3.5-flash-lite'),
        GEMINI_IMAGE_MODEL=os.environ.get('GEMINI_IMAGE_MODEL', ''),
        DATABASE=os.path.join(
            app.instance_path,
            'idfinder.sqlite'
        ),
        UPLOAD_FOLDER=os.path.join(
            app.root_path,
            'static',
            'uploads'
        ),
        MAX_CONTENT_LENGTH=15 * 1024 * 1024,
        SQLITE_TIMEOUT=1.0,
        REVIEW_EVIDENCE_FOLDER=os.path.join(app.instance_path, 'review_evidence'),
        DEMO_DATA=(
            os.environ.get('IDFINDER_DEMO_DATA', '0') == '1'
        )
    )

    if test_config is None:
        app.config.from_pyfile(
            'config.py',
            silent=True
        )
    else:
        app.config.from_mapping(test_config)

    os.makedirs(
        app.instance_path,
        exist_ok=True
    )

    # The repo ships instance/idfinder.sqLite (capital L). Windows treats it as idfinder.sqlite,
    # Linux/macOS do not and would silently open a new empty database.
    configured = app.config['DATABASE']
    shipped = os.path.join(os.path.dirname(configured), 'idfinder.sqLite')
    if (os.path.basename(configured) == 'idfinder.sqlite' and not os.path.exists(configured)
            and os.path.exists(shipped)):
        app.config['DATABASE'] = shipped

    os.makedirs(
        app.config['UPLOAD_FOLDER'],
        exist_ok=True
    )

    from . import db
    db.init_app(app)

    from .entities import review_schema
    review_schema.init_app(app)

    os.makedirs(app.config['REVIEW_EVIDENCE_FOLDER'], exist_ok=True)

    # The leaderboard, charts and home page filter on idp.approval_status, which only exists after
    # the image-review migration. Apply it automatically (additive, keeps all data) instead of 500-ing.
    _ensure_image_review_schema(app)

    if app.config['DEMO_DATA']:
        from .demo_seed import DemoSeeder

        try:
            DemoSeeder(app.config['DATABASE']).seed()
        except Exception:
            app.logger.exception(
                'Demo data could not be created'
            )

    _register_safety_net(app)

    from .boundaries import auth
    app.register_blueprint(auth.bp)

    from .boundaries import home
    app.register_blueprint(home.bp)

    app.add_url_rule(
        '/',
        endpoint='index'
    )

    from .boundaries import designer
    app.register_blueprint(designer.bp)

    from .boundaries import platform
    app.register_blueprint(platform.bp)

    from idfinder.boundaries.platform_charts import (
        platform_charts_bp
    )
    app.register_blueprint(platform_charts_bp)

    from .boundaries import customer
    app.register_blueprint(customer.bp)

    from .boundaries import search
    app.register_blueprint(search.bp)

    from .boundaries import favourites
    app.register_blueprint(favourites.bp)

    # designer ratings: profile + leaderboard, jobs, reviews, and the manager's moderation page
    from .boundaries import reviews
    app.register_blueprint(reviews.bp)

    from .boundaries.platform_reviews import platform_reviews_bp
    app.register_blueprint(platform_reviews_bp)

    # C18: keep the latest review/analytics routes and add customer chat memory.
    from .boundaries import chatbot
    from .services.chatbot_state import ChatbotState
    app.extensions['chatbot_state'] = ChatbotState()
    app.register_blueprint(chatbot.bp)

    from .boundaries.image_review import bp as image_review_bp, ReviewBoundary
    app.register_blueprint(image_review_bp)
    app.before_request(ReviewBoundary.protect_uploads)
    app.after_request(ReviewBoundary.private_response)
    app.context_processor(ReviewBoundary.context)

    # Preserve AI analysis while retaining the merged review and request safeguards.
    from .boundaries.image_analysis import bp as image_analysis_bp, AnalysisRateLimit
    app.extensions['image_analysis_rate_limit'] = AnalysisRateLimit()
    app.register_blueprint(image_analysis_bp)

    return app


def _register_safety_net(app):
    """Request safeguards for invalid IDs, constraint conflicts and real SQLite contention."""
    import sqlite3
    from flask import g, jsonify, request
    from werkzeug.exceptions import InternalServerError, NotFound
    from werkzeug.routing import IntegerConverter, ValidationError as RoutingValidationError
    from .db import is_busy_error

    class SQLiteIntegerConverter(IntegerConverter):
        def to_python(self, value):
            digits = value.lstrip('0') or '0'
            # Validate before Python's integer parser and before binding an SQLite INTEGER.
            if len(digits) > 19 or int(digits) > 9223372036854775807:
                raise RoutingValidationError()
            return super().to_python(digits)

    app.url_map.converters['int'] = SQLiteIntegerConverter

    def rollback():
        connection = g.get('db')
        if connection is not None and connection.in_transaction:
            connection.rollback()

    def error_response(message, status):
        wants_json = (request.is_json or request.path.startswith('/platform/charts/')
                      or request.path.endswith('.json')
                      or request.accept_mimetypes.best == 'application/json')
        return app.make_response((jsonify(error=message) if wants_json else message, status))

    @app.errorhandler(OverflowError)
    def number_too_large(error):
        return NotFound('That value is out of range.')

    @app.errorhandler(sqlite3.OperationalError)
    def database_error(error):
        rollback()
        if not is_busy_error(error):
            app.logger.exception('Database operation failed')
            return InternalServerError()
        app.logger.warning('Database contention; request was not completed')
        response = error_response('The database is busy. Please wait a moment, reload and try again.', 503)
        response.headers['Retry-After'] = '1'
        return response

    @app.errorhandler(sqlite3.IntegrityError)
    def conflict(error):
        rollback()
        return error_response('That change conflicts with existing data. Reload the page before trying again.', 409)

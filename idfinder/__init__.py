import os

from flask import Flask


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

    os.makedirs(
        app.config['UPLOAD_FOLDER'],
        exist_ok=True
    )

    from . import db
    db.init_app(app)

    from .entities import review_schema
    review_schema.init_app(app)

    os.makedirs(app.config['REVIEW_EVIDENCE_FOLDER'], exist_ok=True)

    if app.config['DEMO_DATA']:
        from .demo_seed import DemoSeeder

        try:
            DemoSeeder(app.config['DATABASE']).seed()
        except Exception:
            app.logger.exception(
                'Demo data could not be created'
            )

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

    # AI image analysis only suggests form details; saving still runs duplicate review.
    from .boundaries.image_analysis import bp as image_analysis_bp, AnalysisRateLimit
    app.extensions['image_analysis_rate_limit'] = AnalysisRateLimit()
    app.register_blueprint(image_analysis_bp)

    return app
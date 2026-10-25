import os

from flask import Flask


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',  # change to a random value when deploying
        DATABASE=os.path.join(app.instance_path, 'idfinder.sqlite'),
        # folder INSIDE myfirstapp/static so Flask can serve the files
        UPLOAD_FOLDER=os.path.join(app.root_path, 'static', 'uploads'),
        MAX_CONTENT_LENGTH=15 * 1024 * 1024,  # reject uploads over 15 MB
        DEMO_DATA=os.environ.get('IDFINDER_DEMO_DATA', '0') == '1',
        #DO NOT REPEAT
    )

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    from . import db
    db.init_app(app)
    if app.config['DEMO_DATA']:
        from .demo_seed import DemoSeeder
        try:
            DemoSeeder(app.config['DATABASE']).seed()
        except Exception:
            # never stop the site from starting because of demo data
            app.logger.exception('Demo data could not be created')

    from .boundaries import auth
    app.register_blueprint(auth.bp)

    from .boundaries import home
    app.register_blueprint(home.bp)
    app.add_url_rule('/', endpoint='index')
    #means that when user goes to localhost:5000/ --> brings them to home/index.html 

    from .boundaries import designer
    app.register_blueprint(designer.bp)
    # the designer blueprint already serves /portfolio as endpoint 'designer.portfolio'

    from .boundaries import platform
    app.register_blueprint(platform.bp)

    from idfinder.boundaries.platform_charts import platform_charts_bp
    app.register_blueprint(platform_charts_bp)

    from .boundaries import customer
    app.register_blueprint(customer.bp)

    # C08: register saving on the Customer branch without adding ID19 routes.
    from .boundaries import favourites
    app.register_blueprint(favourites.bp)

    return app
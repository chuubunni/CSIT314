import os

from flask import Flask


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',  # change to a random value when deploying
        DATABASE=os.path.join(app.instance_path, 'myfirstapp.sqLite'),
        # folder INSIDE myfirstapp/static so Flask can serve the files
        UPLOAD_FOLDER=os.path.join(app.root_path, 'static', 'uploads'),
        FILES_FOLDER=os.path.join(app.root_path, 'static', 'files'),
        MAX_CONTENT_LENGTH=15 * 1024 * 1024,  # reject uploads over 15 MB
        #DO NOT REPEAT
    )

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    @app.route('/hello')
    def hello():
        return 'Hello, world!'

    from . import db
    db.init_app(app)

    from .boundaries import auth
    app.register_blueprint(auth.bp)

    from .boundaries import home
    app.register_blueprint(home.bp)
    app.add_url_rule('/', endpoint='index')
    #means that when user goes to localhost:5000/ --> brings them to home/index.html 

    from .boundaries import designer
    app.register_blueprint(designer.bp)
    # the designer blueprint already serves /portfolio as endpoint 'designer.portfolio'

    return app 
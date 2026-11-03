import sqlite3
from contextlib import closing
from datetime import datetime

import click
from flask.cli import with_appcontext
from flask import current_app, g


def get_db():
    # Return a database connection for the current application context.
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    # Close the connection when Flask finishes the application context.
    db = g.pop('db', None)

    if db is not None:
        db.close()


def init_db():
    db = get_db()

    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf-8'))

    # Clear image review tables when initializing a new database.
    # WARNING: init-db is destructive and should only be used
    # when intentionally resetting the database.
    for table in (
        'image_fingerprint',
        'image_review_case',
        'project_review_decision'
    ):
        db.execute(f'DROP TABLE IF EXISTS {table}')

    # Recreate rating and review tables.
    from idfinder.entities import review_schema
    review_schema.reset(db)

    # Create image duplication review tables.
    from idfinder.entities.image_review_schema import ImageReviewSchema
    ImageReviewSchema.apply(db)


@click.command('init-db')
def init_db_command():
    init_db()
    click.echo('Initialized the database')


sqlite3.register_converter(
    'timestamp',
    lambda v: datetime.fromisoformat(v.decode())
)


def init_app(app):
    app.teardown_appcontext(close_db)

    app.cli.add_command(init_db_command)
    app.cli.add_command(migrate_image_review_command)


@click.command('migrate-image-review')
@with_appcontext
def migrate_image_review_command():
    """
    Add image review tables and index existing images
    without deleting existing project records.
    """

    from pathlib import Path

    from idfinder.entities.image_review_schema import ImageReviewSchema
    from idfinder.controller.image_review_controller import ImageReviewController

    app = current_app._get_current_object()

    path = Path(app.config['DATABASE']).resolve()

    if not path.is_file():
        raise click.ClickException(
            'Configured database does not exist. '
            'Check DATABASE before migrating.'
        )

    database = get_db()

    # Create a timestamped backup before applying migrations.
    backup = path.with_name(
        path.name
        + '.review-'
        + datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        + '.bak'
    )

    # FIX 1:
    # Explicitly close the SQLite backup connection.
    #
    # The normal sqlite3.connect() context manager only
    # handles transactions. It does not close the connection.
    #
    # On Windows, this can cause WinError 32 when a
    # temporary backup database is deleted.

    try:
        with closing(sqlite3.connect(str(backup))) as destination:
            database.backup(destination)

        # Apply the image review database migration.
        ImageReviewSchema.apply(database)

        # Index existing project images.
        count, unreadable = ImageReviewController(
            app.config['UPLOAD_FOLDER'],
            app.config['REVIEW_EVIDENCE_FOLDER']
        ).index_existing()

    except (RuntimeError, sqlite3.Error) as error:
        raise click.ClickException(str(error))

    click.echo(f'Database: {path}')
    click.echo(f'Backup: {backup}')

    click.echo(
        f'Image review ready. Indexed {count} existing image(s). '
        'Existing projects remain published.'
    )

    if unreadable:
        click.echo(
            'Missing/unreadable legacy media IDs '
            f'(repair these files): {unreadable}'
        )
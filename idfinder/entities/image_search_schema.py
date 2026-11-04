"""Non-destructive schema creation and CLI indexing."""
import sqlite3
from pathlib import Path
import click


def ensure(db):
    sql = (Path(__file__).resolve().parents[1] / 'image_search_schema.sql').read_text(encoding='utf-8')
    db.executescript(sql)


def init_app(app):
    with sqlite3.connect(app.config['DATABASE']) as db:
        ensure(db)

    @app.cli.command('init-image-search')
    def init_images():
        with sqlite3.connect(app.config['DATABASE']) as db:
            ensure(db)
        click.echo('Image-search table ready.')

    @app.cli.command('index-images')
    @click.option('--force', is_flag=True, help='Rebuild all indexed images')
    def index_images(force):
        from idfinder.controller.image_search_controller import ImageSearchController
        count = ImageSearchController.rebuild(app.config['UPLOAD_FOLDER'], force)
        click.echo(f'Indexed {count} pictures.')

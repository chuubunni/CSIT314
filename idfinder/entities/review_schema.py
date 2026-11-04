"""Creates the engagement + review tables from review_schema.sql, without touching schema.sql.

  * create_app() calls init_app(), so the tables appear the first time the site starts
    (existing data is never touched: every statement is IF NOT EXISTS).
  * `flask --app idfinder init-reviews` does the same by hand.
  * db.init_db() calls reset(), so `flask --app idfinder init-db` also clears reviews and
    engagements together with the users they belong to (no orphan rows).
"""
import os
import sqlite3

import click

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'review_schema.sql')
TABLES = ('review', 'engagement')                     # children first


def _script():
    with open(SCHEMA_PATH, encoding='utf-8') as f:
        return f.read()


def ensure(db):
    """Create the tables if they are missing. Safe to call any number of times."""
    db.executescript(_script())


def reset(db):
    """Drop and recreate (used by init-db, which wipes everything else too)."""
    for table in TABLES:
        db.execute(f'drop table if exists {table}')
    ensure(db)


def init_app(app):
    @click.command('init-reviews')
    def init_reviews_command():
        """Create the review/engagement tables (keeps existing data)."""
        connection = sqlite3.connect(app.config['DATABASE'], timeout=app.config.get('SQLITE_TIMEOUT', 1.0))
        try:
            ensure(connection)
        finally:
            connection.close()
        click.echo('Review tables are ready.')

    app.cli.add_command(init_reviews_command)

    # Create the tables when the site starts. A failure must never stop the site from starting.
    try:
        connection = sqlite3.connect(app.config['DATABASE'], timeout=app.config.get('SQLITE_TIMEOUT', 1.0))
        try:
            ensure(connection)
        finally:
            connection.close()
    except Exception:
        app.logger.exception('Could not create the review tables')

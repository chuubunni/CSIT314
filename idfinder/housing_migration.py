"""Add housing options without deleting records or guessing room types."""
from datetime import datetime
from pathlib import Path
import sqlite3
import click
from flask import current_app
from flask.cli import with_appcontext
from idfinder.db import get_db

HOUSING_OPTIONS = {
    'HDB': ('HDB', ('2-Room', '3-Room', '4-Room', '5-Room', '3Gen',
                    'Maisonette', 'Jumbo', 'Studio Apartment')),
    'Condo': ('Condominium', ('Studio', '1-Bedroom', '2-Bedroom', '3-Bedroom',
                            '4-Bedroom', '5+ Bedrooms', 'Penthouse')),
    'Landed': ('Landed', ('Terrace House', 'Semi-Detached House',
                        'Bungalow / Detached House', 'Good Class Bungalow (GCB)', 'Townhouse')),
}


def migrate_housing(db):
    """Repeatable migration for the supplied ZIP. New tables are seeded once."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='idp'").fetchone():
        raise RuntimeError('Existing idp table not found. Check the database path.')
    for name, required in (
        ('property_type', {'id', 'code', 'name'}),
        ('property_subtype', {'id', 'property_type_id', 'name'}),
    ):
        columns = {r[1] for r in db.execute(f'PRAGMA table_info({name})')}
        if columns and not required.issubset(columns):
            raise RuntimeError(f'{name} has a different schema. Merge your teammate\'s change first.')
    # Explicit BEGIN includes SQLite DDL in the transaction too.
    db.execute('BEGIN')
    try:
        db.execute('CREATE TABLE IF NOT EXISTS property_type ('
                   'id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL UNIQUE)')
        db.execute('CREATE TABLE IF NOT EXISTS property_subtype ('
                   'id INTEGER PRIMARY KEY, property_type_id INTEGER NOT NULL '
                   'REFERENCES property_type(id), name TEXT NOT NULL, UNIQUE(property_type_id, name))')
        columns = {r[1] for r in db.execute('PRAGMA table_info(idp)')}
        if 'property_subtype_id' not in columns:
            db.execute('ALTER TABLE idp ADD COLUMN property_subtype_id INTEGER '
                       'REFERENCES property_subtype(id)')
        for code, (name, subtypes) in HOUSING_OPTIONS.items():
            db.execute('INSERT INTO property_type (code, name) VALUES (?, ?) '
                       'ON CONFLICT(code) DO NOTHING', (code, name))
            type_id = db.execute('SELECT id FROM property_type WHERE code = ?', (code,)).fetchone()[0]
            db.executemany('INSERT OR IGNORE INTO property_subtype (property_type_id, name) '
                           'VALUES (?, ?)', [(type_id, s) for s in subtypes])
        db.execute('CREATE INDEX IF NOT EXISTS ix_idp_property_type ON idp(propertyType)')
        db.execute('CREATE INDEX IF NOT EXISTS ix_idp_subtype ON idp(property_subtype_id)')
        for operation in ('INSERT', 'UPDATE'):
            db.execute(f'''CREATE TRIGGER IF NOT EXISTS validate_idp_housing_{operation.lower()}
                BEFORE {operation} ON idp
                WHEN NEW.property_subtype_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM property_subtype s JOIN property_type t
                    ON t.id = s.property_type_id
                    WHERE s.id = NEW.property_subtype_id AND t.code = NEW.propertyType
                ) BEGIN SELECT RAISE(ABORT, 'Housing subtype does not match property type'); END''')
        db.commit()
    except Exception:
        db.rollback()
        raise


@click.command('migrate-housing')
@with_appcontext
def migrate_housing_command():
    """Back up the configured SQLite database, then add types and subtypes."""
    source = Path(current_app.config['DATABASE']).resolve()
    if not source.is_file():
        raise click.ClickException(f'Database not found: {source}. Check your configuration.')
    db = get_db()
    backup = source.with_name(source.name + '.housing-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
    with sqlite3.connect(str(backup)) as destination:
        db.backup(destination)
    try:
        migrate_housing(db)
    except (RuntimeError, sqlite3.Error) as error:
        raise click.ClickException(str(error))
    click.echo(f'Database: {source}')
    click.echo(f'Backup: {backup}')
    click.echo('Housing ready: 3 types, 20 initial subtypes. Existing projects preserved.')
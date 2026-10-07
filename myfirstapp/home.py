import os
import uuid

from flask import (
    Blueprint, render_template
)

from myfirstapp.db import get_db

bp = Blueprint('home', __name__)


@bp.route('/')
def index():
    db = get_db()
    images = db.execute(
        'SELECT i.id, i.imagelink, i.caption, i.author_id, i.created, u.name'
        ' FROM images i JOIN user u ON i.author_id = u.id' #MUST PUT SPACING!!!!!!!!!
        ' ORDER BY created DESC'
    ).fetchall()
    files = show_files()
    return render_template('home/index.html', images=images, files=files)

def show_files():
    """All uploaded files (newest first) for the index page."""
    return get_db().execute(
        'SELECT f.id, f.filelink, f.filename, f.author_id, f.created, u.name'
        ' FROM files f JOIN user u ON f.author_id = u.id'
        ' ORDER BY f.created DESC'
    ).fetchall()

import os
import uuid

from flask import (
    Blueprint, current_app, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort
from werkzeug.utils import secure_filename

from myfirstapp.auth import login_required
from myfirstapp.db import get_db

bp = Blueprint('blog', __name__)

# Each upload type has its own whitelist so a PDF can't end up in the images table
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
FILE_EXTENSIONS = {"pdf"}


def allowed_file(filename, allowed):
    """True if the filename's LAST extension is in the `allowed` set."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


@bp.route('/')
def index():
    db = get_db()
    posts = db.execute(
        'SELECT p.id, title, body, created, author_id, name'
        ' FROM post p JOIN user u ON p.author_id = u.id'
        ' ORDER BY created DESC'
    ).fetchall()
    images = db.execute(
        'SELECT i.id, i.imagelink, i.caption, i.author_id, i.created, u.name'
        ' FROM images i JOIN user u ON i.author_id = u.id' #MUST PUT SPACING!!!!!!!!!
        ' ORDER BY created DESC'
    ).fetchall()
    files = Files.show_files()
    return render_template('blog/index.html', posts=posts, images=images, files=files)

class Posts():
    @bp.route("/create", methods=("GET", "POST"))
    @login_required
    def create():
        """Create a new post for the current user."""
        if request.method == "POST":
            title = request.form["title"]
            body = request.form["body"]
            error = None

            if not title:
                error = "Title is required."

            if error is not None:
                flash(error)
            else:
                db = get_db()
                db.execute(
                    "INSERT INTO post (title, body, author_id) VALUES (?, ?, ?)",
                    (title, body, g.user["id"]),
                )
                db.commit()
                return redirect(url_for("blog.index"))

        return render_template("blog/create.html")

    @bp.route("/upload", methods=("GET", "POST"))
    @login_required
    def upload():
        if request.method == "POST":
            fileobj = request.files.get("file")
            caption = request.form.get("caption", "").strip()
            error = None

            if fileobj is None or fileobj.filename == "":
                error = "No file selected."
            elif not allowed_file(fileobj.filename, IMAGE_EXTENSIONS):
                error = "Wrong file extension! Allowed: jpg, jpeg, png, gif."

            if error is not None:
                flash(error)
            else:
                ext = fileobj.filename.rsplit(".", 1)[1].lower()
                # random name: avoids overwriting other uploads and unsafe filenames
                saved_name = f"{uuid.uuid4().hex}.{ext}"
                fileobj.save(os.path.join(current_app.config['UPLOAD_FOLDER'], saved_name))

                db = get_db()
                db.execute(
                    "INSERT INTO images (imagelink, caption, author_id) VALUES (?, ?, ?)",
                    (saved_name, caption, g.user["id"]),
                )
                db.commit()
                return redirect(url_for("blog.index"))

        return render_template("blog/upload.html")

    def get_post(id, check_author=True):
        post = get_db().execute(
            'SELECT p.id, title, body, created, author_id, name'
            ' FROM post p JOIN user u ON p.author_id = u.id'
            ' WHERE p.id = ?',
            (id,)
        ).fetchone()

        if post is None:
            abort(404, f"Post id {id} doesn't exist.")

        if check_author and post['author_id'] != g.user['id']:
            abort(403)

        return post

    @bp.route('/<int:id>/update', methods=('GET', 'POST'))
    @login_required
    def update(id):
        post = Posts.get_post(id)

        if request.method == 'POST':
            title = request.form['title']
            body = request.form['body']
            error = None

            if not title:
                error = 'Title is required.'

            if error is not None:
                flash(error)
            else:
                db = get_db()
                db.execute(
                    'UPDATE post SET title = ?, body = ?'
                    ' WHERE id = ?',
                    (title, body, id)
                )
                db.commit()
                return redirect(url_for('blog.index'))

        return render_template('blog/update.html', post=post)

    @bp.route('/<int:id>/delete', methods=('POST',))
    @login_required
    def delete(id):
        Posts.get_post(id)
        db = get_db()
        db.execute('DELETE FROM post WHERE id = ?', (id,))
        db.commit()
        return redirect(url_for('blog.index'))


@bp.route('/profile',methods=("GET","POST"))
@login_required
def profile(id):
    return render_template('blog/profile.html')

class Image():
    def get_image(id, check_author=True):
        image = get_db().execute(
            'SELECT id, imagelink, author_id FROM images WHERE id = ?', (id,)
        ).fetchone()

        if image is None:
            abort(404, f"Image id {id} doesn't exist.")

        if check_author and image['author_id'] != g.user['id']:
            abort(403)

        return image

    @bp.route('/<int:id>/remove', methods=("POST",))  # POST only: deletes must not be triggered by a link/GET
    @login_required
    def remove_img(id):
        image = Image.get_image(id)  # 404 if missing, 403 if it isn't the current user's image

        db = get_db()
        db.execute('DELETE FROM images WHERE id = ?', (id,))
        db.commit()

        # remove the file from disk too (basename guards against path tricks)
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], os.path.basename(image['imagelink']))
        try:
            os.remove(path)
        except FileNotFoundError:
            pass  # row is already gone; nothing left to clean up

        return redirect(url_for('blog.index'))

class Files():
    def show_files():
        """All uploaded files (newest first) for the index page."""
        return get_db().execute(
            'SELECT f.id, f.filelink, f.filename, f.author_id, f.created, u.name'
            ' FROM files f JOIN user u ON f.author_id = u.id'
            ' ORDER BY f.created DESC'
        ).fetchall()

    @bp.route("/upload_file", methods=("GET", "POST"))
    @login_required
    def upload_file():
        """Upload a PDF and record it in the files table."""
        if request.method == "POST":
            fileobj = request.files.get("file")
            error = None

            if fileobj is None or fileobj.filename == "":
                error = "No file selected."
            elif not allowed_file(fileobj.filename, FILE_EXTENSIONS):
                error = "Wrong file extension! Only .pdf files are allowed."
            else:
                # the extension can be faked, so also check the PDF magic bytes
                header = fileobj.stream.read(5)
                fileobj.stream.seek(0)
                if header != b"%PDF-":
                    error = "That file doesn't look like a valid PDF."

            if error is not None:
                flash(error)
            else:
                original_name = secure_filename(fileobj.filename) or "document.pdf"
                saved_name = f"{uuid.uuid4().hex}.pdf"  # random name on disk
                fileobj.save(os.path.join(current_app.config['FILES_FOLDER'], saved_name))

                db = get_db()
                db.execute(
                    "INSERT INTO files (filelink, filename, author_id) VALUES (?, ?, ?)",
                    (saved_name, original_name, g.user["id"]),
                )
                db.commit()
                return redirect(url_for("blog.index"))

        return render_template("blog/upload_file.html")

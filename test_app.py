import io
import os

from myfirstapp import create_app
from myfirstapp.db import get_db
from myfirstapp.controller.portfolio_controller import (
    allowed_file, IMAGE_EXTENSIONS
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n fake png"


def make_idp(client, title="Kitchen reno", status="completed", category_id=""):
    return client.post("/portfolio/new", data={
        "title": title, "description": "Nice", "status": status,
        "category_id": category_id,
    })


def login_as_designer(register, login, email="designer@example.com"):
    register(name="Dee", email=email, usertype="designer")
    login(email=email)


# ---------- app factory ----------
def test_config():
    assert not create_app().testing
    assert create_app({"TESTING": True}).testing


def test_hello(client):
    response = client.get("/hello")
    assert response.status_code == 200
    assert response.data == b"Hello, world!"


def test_home_page_loads(client):
    assert client.get("/").status_code == 200


# ---------- register / login ----------
def test_register_redirects_to_login(register):
    response = register()
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_register_stores_hashed_password(app, register):
    register(password="pass1234")
    with app.app_context():
        user = get_db().execute(
            "SELECT * FROM user WHERE email = ?", ("test@example.com",)
        ).fetchone()
    assert user is not None
    assert user["password"] != "pass1234"  # must be stored hashed


def test_login_success_sets_session(client, register, login):
    register()
    response = login()
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert "user_id" in session


def test_login_wrong_password_fails(client, register, login):
    register()
    response = login(password="wrong-password")
    assert response.status_code == 200  # form shown again with an error
    with client.session_transaction() as session:
        assert "user_id" not in session


def test_login_unknown_email_fails(client, login):
    login(email="nobody@example.com")
    with client.session_transaction() as session:
        assert "user_id" not in session


def test_logout_clears_session(client, register, login):
    register()
    login()
    client.get("/auth/logout")
    with client.session_transaction() as session:
        assert "user_id" not in session


# ---------- access control ----------
def test_portfolio_requires_login(client):
    response = client.get("/portfolio")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_create_idp_requires_login(client):
    response = client.get("/portfolio/new")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_customer_cannot_open_portfolio(client, register, login):
    register(usertype="customer")
    login()
    assert client.get("/portfolio").status_code == 403
    assert make_idp(client).status_code == 403


# ---------- IDP creation ----------
def test_designer_creates_idp(app, client, register, login):
    login_as_designer(register, login)
    response = make_idp(client, title="  Kitchen reno  ")
    assert response.status_code == 302
    with app.app_context():
        row = get_db().execute("SELECT * FROM idp").fetchone()
    assert row["title"] == "Kitchen reno"  # whitespace trimmed
    assert row["status"] == "completed"
    assert client.get("/portfolio").status_code == 200


def test_idp_requires_title(app, client, register, login):
    login_as_designer(register, login)
    response = make_idp(client, title="   ")
    assert response.status_code == 200  # form shown again
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM idp").fetchone()[0] == 0


def test_idp_rejects_bad_status_and_category(app, client, register, login):
    login_as_designer(register, login)
    make_idp(client, status="finished")
    make_idp(client, category_id="999")
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM idp").fetchone()[0] == 0


def test_idp_accepts_active_category(app, client, register, login):
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO category (name) VALUES ('Kitchen')")
        db.commit()
    login_as_designer(register, login)
    assert make_idp(client, category_id="1").status_code == 302
    with app.app_context():
        assert get_db().execute("SELECT category_id FROM idp").fetchone()[0] == 1


def test_designer_updates_idp(app, client, register, login):
    login_as_designer(register, login)
    make_idp(client)
    response = client.post("/portfolio/1/edit", data={
        "title": "Renamed", "description": "", "status": "ongoing", "category_id": ""})
    assert response.status_code == 302
    with app.app_context():
        row = get_db().execute("SELECT title, status FROM idp").fetchone()
    assert (row["title"], row["status"]) == ("Renamed", "ongoing")


def test_designer_cannot_touch_another_designers_idp(app, client, register, login):
    login_as_designer(register, login, email="a@example.com")
    make_idp(client)
    client.get("/auth/logout")
    login_as_designer(register, login, email="b@example.com")
    assert client.get("/portfolio/1").status_code == 403
    assert client.post("/portfolio/1/delete").status_code == 403
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM idp").fetchone()[0] == 1


def test_missing_idp_is_404(client, register, login):
    login_as_designer(register, login)
    assert client.get("/portfolio/999").status_code == 404


# ---------- media upload / removal ----------
def test_upload_image_saves_file_and_row(app, client, register, login):
    login_as_designer(register, login)
    make_idp(client)
    response = client.post("/portfolio/1/images", data={
        "file": (io.BytesIO(PNG_BYTES), "my.photo.PNG"), "caption": " Sofa "},
        content_type="multipart/form-data")
    assert response.status_code == 302
    with app.app_context():
        row = get_db().execute("SELECT * FROM idp_media").fetchone()
    assert row["kind"] == "image" and row["caption"] == "Sofa"
    assert row["link"].endswith(".png") and row["link"] != "my.photo.PNG"
    assert os.path.exists(os.path.join(app.config["UPLOAD_FOLDER"], row["link"]))


def test_upload_image_rejects_wrong_type(app, client, register, login):
    login_as_designer(register, login)
    make_idp(client)
    client.post("/portfolio/1/images", data={
        "file": (io.BytesIO(b"x"), "evil.exe")}, content_type="multipart/form-data")
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM idp_media").fetchone()[0] == 0


def test_remove_media_deletes_row_and_file(app, client, register, login):
    login_as_designer(register, login)
    make_idp(client)
    client.post("/portfolio/1/images", data={
        "file": (io.BytesIO(PNG_BYTES), "a.png")}, content_type="multipart/form-data")
    with app.app_context():
        link = get_db().execute("SELECT link FROM idp_media").fetchone()["link"]
    assert client.post("/portfolio/media/1/remove").status_code == 302
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM idp_media").fetchone()[0] == 0
    assert not os.path.exists(os.path.join(app.config["UPLOAD_FOLDER"], link))


def test_delete_idp_removes_media_files(app, client, register, login):
    login_as_designer(register, login)
    make_idp(client)
    client.post("/portfolio/1/images", data={
        "file": (io.BytesIO(PNG_BYTES), "a.png")}, content_type="multipart/form-data")
    assert client.post("/portfolio/1/delete").status_code == 302
    with app.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM idp").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM idp_media").fetchone()[0] == 0
    assert os.listdir(app.config["UPLOAD_FOLDER"]) == []


def test_other_designer_cannot_remove_media(app, client, register, login):
    login_as_designer(register, login, email="a@example.com")
    make_idp(client)
    client.post("/portfolio/1/images", data={
        "file": (io.BytesIO(PNG_BYTES), "a.png")}, content_type="multipart/form-data")
    client.get("/auth/logout")
    login_as_designer(register, login, email="b@example.com")
    assert client.post("/portfolio/media/1/remove").status_code == 403
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM idp_media").fetchone()[0] == 1


# ---------- upload validation (unit tests) ----------
def test_allowed_file_accepts_valid_images():
    for name in ("a.jpg", "b.JPEG", "c.png", "my.photo.gif"):
        assert allowed_file(name, IMAGE_EXTENSIONS)


def test_allowed_file_rejects_invalid_types():
    for name in ("a.exe", "noextension", "c.png.exe"):
        assert not allowed_file(name, IMAGE_EXTENSIONS)

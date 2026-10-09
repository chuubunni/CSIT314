import os
import uuid

from werkzeug.utils import secure_filename

from myfirstapp.controller.errors import NotFoundError, PermissionDenied, ValidationError
from myfirstapp.entities.category import Category
from myfirstapp.entities.idp import IDP
from myfirstapp.entities.idp_media import IDPMedia

# Each upload type has its own whitelist so a PDF can't end up as an image
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
IDP_STATUSES = ("ongoing", "completed")


def allowed_file(filename, allowed):
    """True if the filename's LAST extension is in the `allowed` set."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


class PortfolioController:
    """Control: business rules for a designer's IDP portfolio.

    Knows nothing about Flask requests: it receives plain values and file objects,
    raises ValidationError / NotFoundError / PermissionDenied, and uses the entity
    classes for all database access. That makes it easy to unit test.
    """

    def __init__(self, upload_folder):
        self.folders = {"image": upload_folder}

    # ----- IDP -----
    def list_portfolio(self, designer_id):
        return IDP.find_by_designer(designer_id)

    def categories(self):
        return Category.find_all_active()

    def create_idp(self, designer_id, title, description, category_id, status):
        title, description, category_id, status = self._clean_idp(
            title, description, category_id, status)
        return IDP.create(designer_id, title, description, category_id, status)

    def get_idp(self, idp_id, designer_id):
        return self._owned_idp(idp_id, designer_id)

    def get_idp_with_media(self, idp_id, designer_id):
        """Returns (idp, images, files) for the detail page."""
        idp = self._owned_idp(idp_id, designer_id)
        return (idp,
                IDPMedia.find_by_idp(idp_id, "image"))

    def update_idp(self, idp_id, designer_id, title, description, category_id, status):
        self._owned_idp(idp_id, designer_id)
        title, description, category_id, status = self._clean_idp(
            title, description, category_id, status)
        IDP.update(idp_id, title, description, category_id, status)

    def delete_idp(self, idp_id, designer_id):
        self._owned_idp(idp_id, designer_id)
        media = IDPMedia.find_by_idp(idp_id)
        IDPMedia.delete_by_idp(idp_id)
        IDP.delete(idp_id)
        for item in media:
            self._remove_from_disk(item)

    # ----- media -----
    def add_image(self, idp_id, designer_id, fileobj, caption=""):
        self._owned_idp(idp_id, designer_id)
        if fileobj is None or fileobj.filename == "":
            raise ValidationError("No file selected.")
        if not allowed_file(fileobj.filename, IMAGE_EXTENSIONS):
            raise ValidationError("Wrong file extension! Allowed: jpg, jpeg, png, gif.")

        ext = fileobj.filename.rsplit(".", 1)[1].lower()
        # random name: avoids overwriting other uploads and unsafe filenames
        saved_name = f"{uuid.uuid4().hex}.{ext}"
        fileobj.save(os.path.join(self.folders["image"], saved_name))
        return IDPMedia.create(idp_id, "image", saved_name, (caption or "").strip())

    def remove_media(self, media_id, designer_id):
        """Delete one image/PDF. Returns the idp_id so the boundary can redirect back."""
        media = IDPMedia.find(media_id)
        if media is None:
            raise NotFoundError(f"Media id {media_id} doesn't exist.")
        self._owned_idp(media["idp_id"], designer_id)
        IDPMedia.delete(media_id)
        self._remove_from_disk(media)
        return media["idp_id"]

    # ----- helpers -----
    def _owned_idp(self, idp_id, designer_id):
        idp = IDP.find(idp_id)
        if idp is None:
            raise NotFoundError(f"IDP id {idp_id} doesn't exist.")
        if idp["designer_id"] != designer_id:
            raise PermissionDenied("You can only manage your own projects.")
        return idp

    def _clean_idp(self, title, description, category_id, status):
        title = (title or "").strip()
        description = (description or "").strip()
        if not title:
            raise ValidationError("Title is required.")
        if status not in IDP_STATUSES:
            raise ValidationError("Status must be 'ongoing' or 'completed'.")

        if category_id in (None, ""):
            category_id = None
        else:
            try:
                category_id = int(category_id)
            except (TypeError, ValueError):
                raise ValidationError("Unknown category.")
            category = Category.find(category_id)
            if category is None or not category["active"]:
                raise ValidationError("Unknown category.")
        return title, description, category_id, status

    def _remove_from_disk(self, media):
        # basename guards against path tricks
        path = os.path.join(self.folders[media["kind"]], os.path.basename(media["link"]))
        try:
            os.remove(path)
        except FileNotFoundError:
            pass  # row is already gone; nothing left to clean up   

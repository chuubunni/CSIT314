import os
import uuid

from idfinder.controller.errors import NotFoundError, PermissionDenied, ValidationError
from idfinder.entities.category import Category
from idfinder.entities.idp import IDP
from idfinder.entities.idp_media import IDPMedia

# Each upload type has its own whitelist so a PDF can't end up as an image
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
IDP_STATUSES = ("ongoing", "completed")
# Canonical spellings; these become a house_type table later. Matching ignores case.
HOUSE_TYPES = ("HDB", "Condo", "Landed")
MAX_PRICE = 1_000_000_000


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

    def create_idp(self, designer_id, title, description, houseType, price, status,
                   category_ids=()):
        title, description, houseType, price, status = self._clean_idp(
            title, description, houseType, price, status)
        category_ids = self._clean_category_ids(category_ids)
        return IDP.create(designer_id, title, description, houseType, price, status,
                          category_ids=category_ids)

    def get_idp(self, idp_id, designer_id):
        return self._owned_idp(idp_id, designer_id)

    def get_category_ids(self, idp_id, designer_id):
        """Ids of the IDP's categories, for pre-ticking the edit form."""
        self._owned_idp(idp_id, designer_id)
        return IDP.find_category_ids(idp_id)

    def get_idp_with_media(self, idp_id, designer_id):
        """Returns (idp, images) for the detail page."""
        idp = self._owned_idp(idp_id, designer_id)
        return idp, IDPMedia.find_by_idp(idp_id)

    def update_idp(self, idp_id, designer_id, title, description, houseType, price, status,
                   category_ids=None):
        """category_ids=None leaves the categories alone; a list (even empty) replaces them."""
        self._owned_idp(idp_id, designer_id)
        title, description, houseType, price, status = self._clean_idp(
            title, description, houseType, price, status)
        if category_ids is not None:
            category_ids = self._clean_category_ids(category_ids)
        IDP.update(idp_id, title, description, houseType, status, price,
                   category_ids=category_ids)

    def delete_idp(self, idp_id, designer_id):
        self._owned_idp(idp_id, designer_id)
        media = IDPMedia.find_by_idp(idp_id)
        IDPMedia.delete_by_idp(idp_id)
        IDP.delete(idp_id)
        for item in media:
            self._remove_from_disk(item)

    # ----- media -----
    def add_image(self, idp_id, designer_id, fileobj):
        self._owned_idp(idp_id, designer_id)
        if fileobj is None or fileobj.filename == "":
            raise ValidationError("No file selected.")
        if not allowed_file(fileobj.filename, IMAGE_EXTENSIONS):
            raise ValidationError("Wrong file extension! Allowed: jpg, jpeg, png, gif.")

        ext = fileobj.filename.rsplit(".", 1)[1].lower()
        # random name: avoids overwriting other uploads and unsafe filenames
        saved_name = f"{uuid.uuid4().hex}.{ext}"
        fileobj.save(os.path.join(self.folders["image"], saved_name))
        return IDPMedia.create(idp_id, saved_name)

    def remove_media(self, mediaID, designer_id):
        """Delete one image. Returns the idp_id so the boundary can redirect back."""
        media = IDPMedia.find(mediaID)
        if media is None:
            raise NotFoundError(f"Media id {mediaID} doesn't exist.")
        self._owned_idp(media["idp_id"], designer_id)
        IDPMedia.delete(mediaID)
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

    def _clean_idp(self, title, description, houseType, price, status):
        title = (title or "").strip()
        description = (description or "").strip()
        if not title:
            raise ValidationError("Title is required.")
        if status not in IDP_STATUSES:
            raise ValidationError("Status must be 'ongoing' or 'completed'.")

        by_lower = {name.lower(): name for name in HOUSE_TYPES}
        houseType = by_lower.get((houseType or "").strip().lower())
        if houseType is None:
            raise ValidationError("Please choose a house type.")

        try:
            price = int(str(price).strip())
        except (TypeError, ValueError):
            raise ValidationError("Price must be a whole number of dollars.")
        if price < 0:
            raise ValidationError("Price can't be negative.")
        if price > MAX_PRICE:
            raise ValidationError("Price is too large.")

        return title, description, houseType, price, status

    def _clean_category_ids(self, category_ids):
        """List of ids from the form -> sorted unique ints, each an active category."""
        cleaned = set()
        for raw in (category_ids or ()):
            try:
                category_id = int(raw)
            except (TypeError, ValueError):
                raise ValidationError("Unknown category.")
            category = Category.find(category_id)
            if category is None or not category["active"]:
                raise ValidationError("Unknown category.")
            cleaned.add(category_id)
        return sorted(cleaned)

    def _remove_from_disk(self, media):
        # basename guards against path tricks
        path = os.path.join(self.folders["image"], os.path.basename(media["link"]))
        try:
            os.remove(path)
        except FileNotFoundError:
            pass  # row is already gone; nothing left to clean up
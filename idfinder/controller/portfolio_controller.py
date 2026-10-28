import os
import sqlite3
import uuid

from idfinder.controller.errors import NotFoundError, PermissionDenied, ValidationError
from idfinder.entities.category import Category
from idfinder.entities.idp import IDP
from idfinder.entities.housing import Housing
from idfinder.entities.idp_media import IDPMedia
from idfinder.entities.user import designers

# Each upload type has its own whitelist so a PDF can't end up as an image
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
IDP_STATUSES = ("ongoing", "completed")
PROPERTY_TYPES = ("HDB", "Condo", "Landed")

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
    def list_portfolio(self, designer_id, category_id=None):
        return IDP.find_by_designer(designer_id, category_id=category_id)

    def categories(self):
        return Category.find_all_active()

    def create_idp(self, designer_id, title, description, property_type, price, status,
                   category_ids=(), property_subtype_id=None, images=()):
        """images: uploaded files from the same form. Everything is checked before
        anything is saved, so a bad file never leaves a half-created project."""
        title, description, property_type, price, status = self._clean_idp(
            title, description, property_type, price, status)
        property_subtype_id = self._clean_housing(property_type, property_subtype_id)
        category_ids = self._clean_category_ids(category_ids)
        images = self._clean_images(images)
        idp_id = IDP.create(designer_id=designer_id, title=title, description=description,
                            property_type=property_type, price=price,
                            status=status, category_ids=category_ids,
                            property_subtype_id=property_subtype_id)
        for fileobj in images:
            self._save_image(idp_id, fileobj)
        return idp_id

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

    def update_idp(self, idp_id, designer_id, title, description, property_type, price, status,
                   category_ids=None, property_subtype_id=None, images=(), remove_media_ids=()):
        """images are added and remove_media_ids (images of this project) are deleted,
        after all the fields and files have been checked."""
        self._owned_idp(idp_id, designer_id)
        title, description, property_type, price, status = self._clean_idp(
            title, description, property_type, price, status)
        property_subtype_id = self._clean_housing(property_type, property_subtype_id)
        if category_ids is not None:
            category_ids = self._clean_category_ids(category_ids)
        images = self._clean_images(images)
        to_remove = self._clean_media_ids(idp_id, remove_media_ids)
        IDP.update(idp_id, title=title, description=description, property_type=property_type,
                   status=status, price=price, category_ids=category_ids,
                   property_subtype_id=property_subtype_id)
        for media in to_remove:
            IDPMedia.delete(media["mediaID"])
            self._remove_from_disk(media)
        for fileobj in images:
            self._save_image(idp_id, fileobj)

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
        self._clean_images([fileobj])
        return self._save_image(idp_id, fileobj)

    def remove_media(self, mediaID, designer_id):
        """Delete one image. Returns the idp_id so the boundary can redirect back."""
        media = IDPMedia.find(mediaID)
        if media is None:
            raise NotFoundError(f"Media id {mediaID} doesn't exist.")
        self._owned_idp(media["idp_id"], designer_id)
        IDPMedia.delete(mediaID)
        self._remove_from_disk(media)
        return media["idp_id"]

    # ----- profile -----
    def get_profile(self, designer_id):
        """The designer's own account and company details."""
        profile = designers.get_profile(designer_id)
        if profile is None:
            raise NotFoundError("Designer profile not found.")
        return profile

    def update_profile(self, designer_id, name, email, phone):
        self.get_profile(designer_id)          # 404 if this account has no designer profile

        name = (name or "").strip()
        email = (email or "").strip()
        phone = (phone or "").strip()
        if not name:
            raise ValidationError("Name is required.")
        if not email or "@" not in email:
            raise ValidationError("Please enter a valid email address.")
        if not phone:
            raise ValidationError("Phone number is required.")

        try:
            designers.update_profile(designer_id, name, email, phone)
        except sqlite3.IntegrityError:
            raise ValidationError("This email is already used by another account.")

    def update_company_profile(self, designer_id, companyName,
                               companyLine, companyEmail):
        self.get_profile(designer_id)

        if designers.get_company(designer_id) is None:
            raise NotFoundError('Company profile not found.')

        companyName = (companyName or '').strip()
        companyLine = (companyLine or '').strip()
        companyEmail = (companyEmail or '').strip()

        if not companyName:
            raise ValidationError('Company name is required.')

        if not companyLine:
            raise ValidationError('Company phone number is required.')

        if companyEmail and (
                '@' not in companyEmail
                or not all(companyEmail.split('@'))
                or companyEmail.count('@') != 1):
            raise ValidationError('Please enter a valid company email.')

        try:
            designers.update_company_profile(
                designer_id, companyName, companyLine, companyEmail
            )
        except sqlite3.IntegrityError as error:
            if 'companyLine' in str(error):
                raise ValidationError(
                    'This company phone number is already in use.'
                ) from error
            raise
        except ValueError as error:
            raise NotFoundError(str(error)) from error

    # ----- helpers -----
    def _owned_idp(self, idp_id, designer_id):
        idp = IDP.find(idp_id)
        if idp is None:
            raise NotFoundError(f"IDP id {idp_id} doesn't exist.")
        if idp["designer_id"] != designer_id:
            raise PermissionDenied("You can only manage your own projects.")
        return idp

    def _clean_idp(self, title, description, property_type, price, status):
        title = (title or "").strip()
        description = (description or "").strip()
        if not title:
            raise ValidationError("Title is required.")
        if status not in IDP_STATUSES:
            raise ValidationError("Status must be 'ongoing' or 'completed'.")

        by_lower = {t["code"].lower(): t["code"] for t in Housing.types()}
        property_type = by_lower.get((property_type or "").strip().lower())
        if property_type is None:
            raise ValidationError("Please choose a property type.")

        try:
            price = int(str(price).strip())
        except (TypeError, ValueError):
            raise ValidationError("Price must be a whole number of dollars.")
        if price < 0:
            raise ValidationError("Price can't be negative.")
        if price > MAX_PRICE:
            raise ValidationError("Price is too large.")

        return title, description, property_type, price, status

    def property_options(self):
        """(types, subtypes) for the IDP form's two dropdowns."""
        return Housing.types(), Housing.subtypes()

    def _clean_housing(self, property_type, raw_subtype):
        """Returns the subtype id after checking it belongs to property_type.
        Checked here so the user gets a friendly message instead of the database trigger's error."""
        try:
            subtype_id = int(raw_subtype)
        except (TypeError, ValueError):
            raise ValidationError("Please choose a housing subtype.")
        subtype = Housing.find_subtype(subtype_id)
        if subtype is None or subtype['type_code'] != property_type:
            raise ValidationError("The subtype must belong to the selected property type.")
        return subtype_id

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

    def _clean_images(self, images):
        """Uploaded files -> the ones actually chosen (an empty file input sends one
        blank entry), each with an allowed image extension."""
        chosen = [f for f in (images or ()) if f is not None and f.filename]
        for fileobj in chosen:
            if not allowed_file(fileobj.filename, IMAGE_EXTENSIONS):
                raise ValidationError("Wrong file extension! Allowed: jpg, jpeg, png, gif.")
        return chosen

    def _clean_media_ids(self, idp_id, raw_ids):
        """Ids from the edit form's Remove checkboxes -> media rows, each an image of this IDP."""
        media = []
        for raw in (raw_ids or ()):
            try:
                row = IDPMedia.find(int(raw))
            except (TypeError, ValueError):
                row = None
            if row is None or row["idp_id"] != idp_id:
                raise ValidationError("You can only remove images of this project.")
            media.append(row)
        return media

    def _save_image(self, idp_id, fileobj):
        ext = fileobj.filename.rsplit(".", 1)[1].lower()
        # random name: avoids overwriting other uploads and unsafe filenames
        saved_name = f"{uuid.uuid4().hex}.{ext}"
        fileobj.save(os.path.join(self.folders["image"], saved_name))
        return IDPMedia.create(idp_id, saved_name)

    def _remove_from_disk(self, media):
        # basename guards against path tricks
        path = os.path.join(self.folders["image"], os.path.basename(media["link"]))
        try:
            os.remove(path)
        except FileNotFoundError:
            pass  # row is already gone; nothing left to clean up

    # ID19: validate selection IDs; the entity checks and replaces all links atomically.
    def update_selected_categories(self, designer_id, idp_ids, category_ids):
        try:
            projects = sorted({int(value) for value in (idp_ids or ())})
        except (ValueError, TypeError):
            raise ValidationError('Invalid project selection.')
        if not projects or any(value <= 0 for value in projects):
            raise ValidationError('Select at least one valid project.')
        categories = self._clean_category_ids(category_ids)
        if not categories:
            raise ValidationError('Select at least one active category.')
        return IDP.update_categories_bulk(designer_id, projects, categories)

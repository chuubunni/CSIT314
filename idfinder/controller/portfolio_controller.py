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
# Canonical spellings; these become a property_type table later. Matching ignores case.
PROPERTY_TYPES = ("HDB", "Condo", "Landed")

HOUSE_TYPES = {
    "HDB": ["2-Room", "3-Room", "4-Room", "5-Room", "3 Gen", "Mansionette", "Jumbo", "Studio Apartment"],
    "Condo": ["Studio", "1-Bedroom", "2-Bedroom", "3-Bedroom", "4-Bedroom", "5+ Bedrooms", "Penthouse"],
    "Landed": ["Terrace House", "Semi-Detached House", "Bungalow / Detached House", "Good Class Bungalow (GCB)", "Townhouse"]
}

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

    def create_idp(self, designer_id, title, description, propertyType, price, status,
                   category_ids=(), property_subtype_id=None):
        title, description, propertyType, price, status = self._clean_idp(
            title, description, propertyType, price, status)
        property_subtype_id = self._clean_housing(propertyType, property_subtype_id)
        category_ids = self._clean_category_ids(category_ids)
        return IDP.create(designer_id=designer_id, title=title, description=description, propertyType=propertyType, price=price, status=status,
                          category_ids=category_ids, property_subtype_id=property_subtype_id)

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

    def update_idp(self, idp_id, designer_id, title, description, propertyType, price, status,
                   category_ids=None, property_subtype_id=None):
        """category_ids=None leaves the categories alone; a list (even empty) replaces them."""
        self._owned_idp(idp_id, designer_id)
        title, description, propertyType, price, status = self._clean_idp(
            title, description, propertyType, price, status)
        property_subtype_id = self._clean_housing(propertyType, property_subtype_id)
        if category_ids is not None:
            category_ids = self._clean_category_ids(category_ids)
        IDP.update(idp_id, title=title, description=description, propertyType=propertyType, status=status, price=price,
                   category_ids=category_ids, property_subtype_id=property_subtype_id)

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

    def _clean_idp(self, title, description, propertyType, houseType, price, status):
        title = (title or "").strip()
        description = (description or "").strip()
        if not title:
            raise ValidationError("Title is required.")
        if status not in IDP_STATUSES:
            raise ValidationError("Status must be 'ongoing' or 'completed'.")

        # Validate propertyType
        by_lower = {name.lower(): name for name in PROPERTY_TYPES}
        propertyType = by_lower.get((propertyType or "").strip().lower())
        if propertyType is None:
            raise ValidationError("Please choose a property type.")

        # Validate houseType against the selected propertyType
        houseType = (houseType or "").strip()

        if not houseType:
            raise ValidationError("Please choose a house type.")

        allowed_house_types = HOUSE_TYPES[propertyType]
        if houseType not in allowed_house_types:
            raise ValidationError("Please choose a valid house type for the selected property type.")

        try:
            price = int(str(price).strip())
        except (TypeError, ValueError):
            raise ValidationError("Price must be a whole number of dollars.")
        if price < 0:
            raise ValidationError("Price can't be negative.")
        if price > MAX_PRICE:
            raise ValidationError("Price is too large.")

        return title, description, propertyType, houseType, price, status

    def housing_options(self):
        return Housing.types(), Housing.subtypes()

    def _clean_housing(self, property_type, raw_subtype):
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

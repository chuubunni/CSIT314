import os
import sqlite3
import tempfile
from pathlib import Path

from flask import current_app, has_app_context

from idfinder.controller.errors import (
    NotFoundError,
    PermissionDenied,
    ValidationError
)
from idfinder.entities.category import Category
from idfinder.entities.idp import IDP
from idfinder.entities.housing import Housing
from idfinder.entities.idp_media import IDPMedia
from idfinder.entities.user import designers
from idfinder.services.image_similarity import ImageSimilarity


IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}
IDP_STATUSES = ('ongoing', 'completed')
# Compatibility: authentication and customer profile controllers import this.
# These values match property_type.code in the existing database.
PROPERTY_TYPES = ('HDB', 'Condo', 'Landed')
MAX_PRICE = 1_000_000_000


def allowed_file(filename, allowed):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in allowed
    )


class PortfolioController:
    """Designer portfolio operations, including reviewed image uploads.

    Keeps ID07's create/edit image fields compatible with the
    original forms, but routes every image write through the
    duplicate-image review controller.
    """

    def __init__(self, upload_folder, evidence_folder=None):
        self.folders = {'image': str(upload_folder)}

        if evidence_folder is None and has_app_context():
            evidence_folder = current_app.config.get(
                'REVIEW_EVIDENCE_FOLDER'
            )

        self.evidence_folder = str(
            evidence_folder
            or (
                Path(upload_folder).resolve().parent
                / 'review_evidence'
            )
        )

    def _review(self):
        from idfinder.controller.image_review_controller import (
            ImageReviewController
        )
        return ImageReviewController(
            self.folders['image'],
            self.evidence_folder
        )

    # ----- PROJECTS -----

    def list_portfolio(self, designer_id, category_id=None):
        return IDP.find_by_designer(
            designer_id,
            category_id=category_id
        )

    def categories(self):
        return Category.find_all_active()

    def property_options(self):
        return Housing.types(), Housing.subtypes()

    def create_idp(
        self,
        designer_id,
        title,
        description,
        property_type,
        price,
        status,
        category_ids=(),
        property_subtype_id=None,
        images=()
    ):
        title, description, property_type, price, status = (
            self._clean_idp(
                title,
                description,
                property_type,
                price,
                status
            )
        )

        property_subtype_id = self._clean_housing(
            property_type,
            property_subtype_id
        )

        category_ids = self._clean_category_ids(category_ids)

        # Validate all image files before saving a project.
        images = self._clean_images(images)

        project_id = IDP.create(
            designer_id=designer_id,
            title=title,
            description=description,
            property_type=property_type,
            price=price,
            status=status,
            category_ids=category_ids,
            property_subtype_id=property_subtype_id
        )

        try:
            # Every uploaded image goes through the duplication checker.
            for image in images:
                self.add_image(project_id, designer_id, image)

        except Exception:
            # Best-effort cleanup if an upload fails after creation.
            self.delete_idp(project_id, designer_id)
            raise

        return project_id

    def get_idp(self, idp_id, designer_id):
        return self._owned_idp(idp_id, designer_id)

    def get_category_ids(self, idp_id, designer_id):
        self._owned_idp(idp_id, designer_id)
        return IDP.find_category_ids(idp_id)

    def get_idp_with_media(self, idp_id, designer_id):
        return (
            self._owned_idp(idp_id, designer_id),
            IDPMedia.find_by_idp(idp_id)
        )

    def update_idp(
        self,
        idp_id,
        designer_id,
        title,
        description,
        property_type,
        price,
        status,
        category_ids=None,
        property_subtype_id=None,
        images=(),
        remove_media_ids=()
    ):
        self._owned_idp(idp_id, designer_id)

        title, description, property_type, price, status = (
            self._clean_idp(
                title,
                description,
                property_type,
                price,
                status
            )
        )

        property_subtype_id = self._clean_housing(
            property_type,
            property_subtype_id
        )

        if category_ids is not None:
            category_ids = self._clean_category_ids(category_ids)

        # Check image contents before modifying project details.
        images = self._clean_images(images)

        # Validate all image-removal requests first.
        to_remove = self._clean_media_ids(
            idp_id,
            remove_media_ids
        )

        IDP.update(
            idp_id,
            title=title,
            description=description,
            property_type=property_type,
            status=status,
            price=price,
            category_ids=category_ids,
            property_subtype_id=property_subtype_id
        )

        # Remove images through the review controller.
        for media in to_remove:
            self.remove_media(
                media['mediaID'],
                designer_id
            )

        # Add new images and check them for duplication.
        for image in images:
            self.add_image(idp_id, designer_id, image)

    def delete_idp(self, idp_id, designer_id):
        self._owned_idp(idp_id, designer_id)

        media = IDPMedia.find_by_idp(idp_id)

        IDPMedia.delete_by_idp(idp_id)
        IDP.delete(idp_id)

        for item in media:
            self._remove_from_disk(item)

    # ----- IMAGE HANDLING -----

    def add_image(self, idp_id, designer_id, fileobj):
        media_id, _status = self._review().add_image(
            idp_id,
            designer_id,
            fileobj
        )
        return media_id

    def remove_media(self, media_id, designer_id):
        return self._review().remove_image(
            media_id,
            designer_id
        )

    # ----- DESIGNER PROFILE -----

    def get_profile(self, designer_id):
        profile = designers.get_profile(designer_id)

        if profile is None:
            raise NotFoundError(
                'Designer profile not found.'
            )

        return profile

    def update_profile(self, designer_id, name, email, phone):
        self.get_profile(designer_id)

        name = (name or '').strip()
        email = (email or '').strip()
        phone = (phone or '').strip()

        if not name:
            raise ValidationError('Name is required.')

        if not email or '@' not in email:
            raise ValidationError(
                'Please enter a valid email address.'
            )

        if not phone:
            raise ValidationError(
                'Phone number is required.'
            )

        try:
            designers.update_profile(
                designer_id,
                name,
                email,
                phone
            )

        except sqlite3.IntegrityError:
            raise ValidationError(
                'This email is already used by another account.'
            )

    def update_company_profile(
        self,
        designer_id,
        companyName,
        companyLine,
        companyEmail
    ):
        self.get_profile(designer_id)

        if designers.get_company(designer_id) is None:
            raise NotFoundError(
                'Company profile not found.'
            )

        companyName = (companyName or '').strip()
        companyLine = (companyLine or '').strip()
        companyEmail = (companyEmail or '').strip()

        if not companyName:
            raise ValidationError(
                'Company name is required.'
            )

        if not companyLine:
            raise ValidationError(
                'Company phone number is required.'
            )

        if companyEmail and (
            '@' not in companyEmail
            or not all(companyEmail.split('@'))
            or companyEmail.count('@') != 1
        ):
            raise ValidationError(
                'Please enter a valid company email.'
            )

        try:
            designers.update_company_profile(
                designer_id,
                companyName,
                companyLine,
                companyEmail
            )

        except sqlite3.IntegrityError as error:
            if 'companyLine' in str(error):
                raise ValidationError(
                    'This company phone number is already in use.'
                ) from error
            raise

        except ValueError as error:
            raise NotFoundError(str(error)) from error

    # ----- VALIDATION HELPERS -----

    def _owned_idp(self, idp_id, designer_id):
        project = IDP.find(idp_id)

        if project is None:
            raise NotFoundError(
                f"IDP id {idp_id} doesn't exist."
            )

        if project['designer_id'] != designer_id:
            raise PermissionDenied(
                'You can only manage your own projects.'
            )

        return project

    def _clean_idp(
        self,
        title,
        description,
        property_type,
        price,
        status
    ):
        title = (title or '').strip()
        description = (description or '').strip()

        if not title:
            raise ValidationError(
                'Title is required.'
            )

        if status not in IDP_STATUSES:
            raise ValidationError(
                "Status must be 'ongoing' or 'completed'."
            )

        by_lower = {
            t['code'].lower(): t['code']
            for t in Housing.types()
        }

        property_type = by_lower.get(
            (property_type or '').strip().lower()
        )

        if property_type is None:
            raise ValidationError(
                'Please choose a property type.'
            )

        try:
            price = int(str(price).strip())

        except (TypeError, ValueError):
            raise ValidationError(
                'Price must be a whole number of dollars.'
            )

        if not 0 <= price <= MAX_PRICE:
            raise ValidationError(
                'Price must be between $0 and $1,000,000,000.'
            )

        return (
            title,
            description,
            property_type,
            price,
            status
        )

    def _clean_housing(self, property_type, raw_subtype):
        try:
            subtype_id = int(raw_subtype)

        except (TypeError, ValueError):
            raise ValidationError(
                'Please choose a housing subtype.'
            )

        subtype = Housing.find_subtype(subtype_id)

        if (
            subtype is None
            or subtype['type_code'] != property_type
        ):
            raise ValidationError(
                'The subtype must belong to '
                'the selected property type.'
            )

        return subtype_id

    def _clean_category_ids(self, category_ids):
        cleaned = set()

        for raw in category_ids or ():
            try:
                category_id = int(raw)

            except (TypeError, ValueError):
                raise ValidationError(
                    'Unknown category.'
                )

            category = Category.find(category_id)

            if category is None or not category['active']:
                raise ValidationError(
                    'Unknown category.'
                )

            cleaned.add(category_id)

        return sorted(cleaned)

    def _clean_images(self, images):
        """
        Validate genuine image data before project creation/editing.

        This deliberately rejects files that have a .jpg extension
        but do not contain valid image data.
        """

        chosen = [
            file
            for file in (images or ())
            if file is not None and file.filename
        ]

        for file in chosen:
            if not allowed_file(
                file.filename,
                IMAGE_EXTENSIONS
            ):
                raise ValidationError(
                    'Wrong file extension! '
                    'Allowed: jpg, jpeg, png, gif.'
                )

        with tempfile.TemporaryDirectory() as temp:
            for i, file in enumerate(chosen):
                extension = Path(
                    file.filename
                ).suffix.lower()

                candidate = (
                    Path(temp) / f'{i}{extension}'
                )

                try:
                    file.stream.seek(0)

                    content = file.stream.read(
                        ImageSimilarity.MAX_BYTES + 1
                    )

                    if len(content) > ImageSimilarity.MAX_BYTES:
                        raise ValidationError(
                            'Maximum image file size is 15 MB.'
                        )

                    candidate.write_bytes(content)

                    # Check that Pillow can decode the image
                    # and calculate its perceptual fingerprint.
                    ImageSimilarity.fingerprint(candidate)

                except (
                    OSError,
                    AttributeError,
                    ValueError
                ) as error:
                    raise ValidationError(
                        'Cannot read the selected image.'
                    ) from error

                finally:
                    # The review controller reads the file again.
                    file.stream.seek(0)

        return chosen

    def _clean_media_ids(self, idp_id, raw_ids):
        media = []
        seen = set()

        for raw in raw_ids or ():
            try:
                media_id = int(raw)

            except (TypeError, ValueError):
                raise ValidationError(
                    'You can only remove images of this project.'
                )

            if media_id in seen:
                continue

            seen.add(media_id)

            item = IDPMedia.find(media_id)

            if (
                item is None
                or item['idp_id'] != idp_id
            ):
                raise ValidationError(
                    'You can only remove images of this project.'
                )

            media.append(item)

        return media

    def _remove_from_disk(self, media):
        path = os.path.join(
            self.folders['image'],
            os.path.basename(media['link'])
        )

        try:
            os.remove(path)

        except FileNotFoundError:
            pass

    # ----- ID19 BULK CATEGORY EDITING -----

    def update_selected_categories(
        self,
        designer_id,
        idp_ids,
        category_ids
    ):
        try:
            projects = sorted({
                int(value)
                for value in (idp_ids or ())
            })

        except (ValueError, TypeError):
            raise ValidationError(
                'Invalid project selection.'
            )

        if not projects or any(
            value <= 0 for value in projects
        ):
            raise ValidationError(
                'Select at least one valid project.'
            )

        categories = self._clean_category_ids(
            category_ids
        )

        if not categories:
            raise ValidationError(
                'Select at least one active category.'
            )

        return IDP.update_categories_bulk(
            designer_id,
            projects,
            categories
        )
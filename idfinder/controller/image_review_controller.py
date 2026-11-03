import os
import shutil
import uuid
from pathlib import Path
from idfinder.controller.errors import ValidationError, NotFoundError
from idfinder.entities.image_review import ImageReview
from idfinder.services.image_similarity import ImageSimilarity


class ImageReviewController:
    def __init__(self, upload_folder, evidence_folder):
        self.uploads = Path(upload_folder)
        self.evidence = Path(evidence_folder)
        self.uploads.mkdir(parents=True,exist_ok=True)
        self.evidence.mkdir(parents=True,exist_ok=True)

    def media_path(self, link):
        if Path(link).name != link:
            raise ValidationError('Invalid image filename.')
        return self.uploads / link

    def ensure_fingerprint(self, media):
        fingerprint = ImageReview.fingerprint(media['mediaID'])
        if fingerprint is None:
            fingerprint = ImageSimilarity.fingerprint(self.media_path(media['link']))
            ImageReview.store_fingerprint(media['mediaID'],fingerprint)
        return fingerprint

    def index_existing(self):
        """Index existing files without retrospectively unpublishing projects."""
        indexed, unreadable = 0, []
        with ImageReview.transaction():
            for media in ImageReview.media():
                try:
                    self.ensure_fingerprint(media)
                    indexed += 1
                except ValidationError:
                    unreadable.append(media['mediaID'])
        return indexed, unreadable

    def scan_locked(self, project_id, snapshots):
        project = ImageReview.project(project_id)
        revision = project['image_revision'] + 1
        current = ImageReview.media(project_id)
        others = [m for m in ImageReview.media() if m['idp_id'] != project_id]
        matches = 0
        for uploaded in current:
            source_fp = self.ensure_fingerprint(uploaded)
            for candidate in others:
                try:
                    target_fp = self.ensure_fingerprint(candidate)
                except ValidationError:
                    # Missing/unreadable legacy assets cannot be compared. The
                    # setup command reports their IDs so they can be repaired.
                    continue
                result = ImageSimilarity.compare(source_fp,target_fp)
                if result is None:
                    continue
                source_name = uuid.uuid4().hex + Path(uploaded['link']).suffix
                target_name = uuid.uuid4().hex + Path(candidate['link']).suffix
                for media, name in ((uploaded,source_name),(candidate,target_name)):
                    destination = self.evidence/name
                    snapshots.append(destination)
                    shutil.copyfile(self.media_path(media['link']),destination)
                ImageReview.add_case(project_id,revision,uploaded['mediaID'],candidate,
                                     source_name,target_name,result,ImageSimilarity.VERSION)
                matches += 1
        if not current:
            status,reason = 'draft','Add an image before publishing.'
        elif matches:
            status,reason = 'pending','Potential image reuse detected. Pending approval.'
        else:
            status,reason = 'approved','Image check passed; no potential reuse detected.'
        ImageReview.set_state(project_id,status,reason,revision)
        return status

    @staticmethod
    def cleanup(paths):
        for path in paths:
            Path(path).unlink(missing_ok=True)

    def add_image(self, project_id, owner_id, fileobj):
        ImageReview.owned(project_id,owner_id)
        if fileobj is None or not fileobj.filename:
            raise ValidationError('Choose an image first.')
        extension = Path(fileobj.filename).suffix.lower()
        if extension not in ('.jpg','.jpeg','.png','.gif'):
            raise ValidationError('Use a JPEG, PNG or still GIF image.')
        path = self.uploads/(uuid.uuid4().hex+extension)
        snapshots=[]
        try:
            # Bound the read even if this controller is called outside Flask.
            data = fileobj.stream.read(ImageSimilarity.MAX_BYTES+1)
            if len(data)>ImageSimilarity.MAX_BYTES:
                raise ValidationError('Maximum image file size is 15 MB.')
            path.write_bytes(data)
            fingerprint=ImageSimilarity.fingerprint(path)
            with ImageReview.transaction():
                ImageReview.owned(project_id,owner_id)
                media_id=ImageReview.insert_media(project_id,path.name)
                ImageReview.store_fingerprint(media_id,fingerprint)
                status=self.scan_locked(project_id,snapshots)
            return media_id,status
        except Exception:
            self.cleanup([path]+snapshots)
            raise

    def remove_image(self, media_id, owner_id):
        snapshots=[]
        try:
            with ImageReview.transaction():
                media=next((m for m in ImageReview.media() if m['mediaID']==media_id),None)
                if media is None:
                    raise NotFoundError('Image not found.')
                project=ImageReview.owned(media['idp_id'],owner_id)
                ImageReview.remove_media(media_id)
                # Removing an image cannot silently overturn a manager rejection.
                if project['approval_status']=='rejected':
                    ImageReview.set_state(project['id'],'rejected',project['approval_reason'],project['image_revision']+1)
                else:
                    self.scan_locked(project['id'],snapshots)
            self.media_path(media['link']).unlink(missing_ok=True)
            return project['id']
        except Exception:
            self.cleanup(snapshots)
            raise

    def resubmit(self, project_id, owner_id):
        snapshots=[]
        try:
            with ImageReview.transaction():
                project=ImageReview.owned(project_id,owner_id)
                if project['approval_status']=='pending':
                    raise ValidationError('This project is already awaiting review.')
                if not ImageReview.media(project_id):
                    raise ValidationError('Upload at least one image before submitting.')
                return self.scan_locked(project_id,snapshots)
        except Exception:
            self.cleanup(snapshots)
            raise

    @staticmethod
    def decide(project_id, raw_revision, manager_id, decision, reason):
        if decision not in ('approved','rejected'):
            raise ValidationError('Choose approve or reject.')
        reason=(reason or '').strip()
        if not reason or len(reason)>2000:
            raise ValidationError('Enter a decision reason (1–2000 characters).')
        try:
            revision=int(raw_revision)
        except (TypeError,ValueError):
            raise ValidationError('Invalid review version. Reload this page.')
        with ImageReview.transaction():
            ImageReview.decide(project_id,revision,manager_id,decision,reason)
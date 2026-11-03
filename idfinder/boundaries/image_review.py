from pathlib import Path
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_from_directory, url_for
from flask.views import MethodView
from idfinder.boundaries.platform import ManagerOnlyView
from idfinder.boundaries.form_security import form_token, validate_form_token
from idfinder.controller.image_review_controller import ImageReviewController
from idfinder.controller.errors import ValidationError, NotFoundError, PermissionDenied
from idfinder.entities.image_review import ImageReview
from idfinder.entities.idp import IDP
from idfinder.entities.idp_media import IDPMedia

bp=Blueprint('image_review',__name__)


class ReviewBoundary:
    @staticmethod
    def controller():
        return ImageReviewController(current_app.config['UPLOAD_FOLDER'],current_app.config['REVIEW_EVIDENCE_FOLDER'])

    @staticmethod
    def context():
        if getattr(g,'user',None) is not None and g.user['Usertype']=='manager':
            return {'pending_image_reviews':len(ImageReview.queue())}
        return {}

    @staticmethod
    def protect_uploads():
        if request.endpoint!='static':
            return None
        filename=(request.view_args or {}).get('filename','')
        if not filename.startswith('uploads/'):
            return None
        link=filename[len('uploads/'):]
        if Path(link).name!=link:
            abort(404)
        rows=ImageReview.media_access(link)
        if not rows:
            abort(404)
        user=getattr(g,'user',None)
        allowed=any(row['approval_status']=='approved' or
                    (user is not None and (user['Usertype']=='manager' or user['id']==row['designer_id']))
                    for row in rows)
        if not allowed:
            abort(404)
        # Serving inside Flask enforces visibility even for a direct file URL.
        response=send_from_directory(current_app.config['UPLOAD_FOLDER'],link,conditional=False,max_age=0)
        response.headers['Cache-Control']='private, no-store'
        return response

    @staticmethod
    def private_response(response):
        # Prevent a rejected project's previously visited HTML being cached.
        response.headers['Cache-Control']='private, no-store'
        return response


class ReviewQueueView(ManagerOnlyView):
    def get(self):
        return render_template('platform/image_reviews.html',projects=ImageReview.queue())


class ReviewProjectView(ManagerOnlyView):
    def get(self,project_id):
        project=IDP.find(project_id)
        if project is None:
            abort(404)
        return render_template('platform/image_review_detail.html',project=project,
            images=IDPMedia.find_by_idp(project_id),cases=ImageReview.cases(project_id,project['image_revision']),
            history=ImageReview.history(project_id),review_token=form_token())

    def post(self,project_id):
        validate_form_token()
        try:
            ImageReviewController.decide(project_id,request.form.get('revision'),g.user['id'],
                                         request.form.get('decision'),request.form.get('reason'))
            flash('Review decision saved. The designer can see the result in their portfolio.')
        except ValidationError as error:
            flash(str(error))
            return redirect(url_for('image_review.project',project_id=project_id)),303
        except NotFoundError:
            abort(404)
        except PermissionDenied:
            abort(403)
        return redirect(url_for('image_review.queue')),303


class ReviewEvidenceView(ManagerOnlyView):
    def get(self,case_id,side):
        case=ImageReview.evidence(case_id)
        if case is None or side not in ('uploaded','matched'):
            abort(404)
        filename=case[side+'_snapshot']
        return send_from_directory(current_app.config['REVIEW_EVIDENCE_FOLDER'],filename,conditional=False,max_age=0)


class ResubmitView(MethodView):
    def post(self,project_id):
        if g.user is None:
            return redirect(url_for('auth.login'))
        if g.user['Usertype']!='designer':
            abort(403)
        validate_form_token()
        try:
            status=ReviewBoundary.controller().resubmit(project_id,g.user['id'])
            flash('Potential image reuse detected. Your project is pending approval.' if status=='pending'
                  else 'Image check passed. Your project is published.')
        except ValidationError as error:
            flash(str(error))
        except NotFoundError:
            abort(404)
        except PermissionDenied:
            abort(403)
        return redirect(url_for('designer.view_idp',idp_id=project_id)),303


bp.add_url_rule('/platform/image-reviews',view_func=ReviewQueueView.as_view('queue'))
bp.add_url_rule('/platform/image-reviews/projects/<int:project_id>',view_func=ReviewProjectView.as_view('project'),methods=['GET','POST'])
bp.add_url_rule('/platform/image-reviews/evidence/<int:case_id>/<side>',view_func=ReviewEvidenceView.as_view('evidence'))
bp.add_url_rule('/portfolio/<int:project_id>/resubmit',view_func=ResubmitView.as_view('resubmit'),methods=['POST'])
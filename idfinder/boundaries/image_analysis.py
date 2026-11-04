"""AI auto-fill endpoint: designer-only, read-only, independent of image approval."""
from collections import defaultdict, deque
from threading import Lock
import time

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from idfinder.boundaries.form_security import form_token, validate_form_token
from idfinder.controller.errors import ValidationError
from idfinder.entities.category import Category
from idfinder.services.image_analysis import ImageAnalysis, ImageAnalysisUnavailable

bp = Blueprint('image_analysis', __name__)


class AnalysisRateLimit:
    """Bound accidental repeated paid requests for each authenticated designer."""
    def __init__(self):
        self.calls = defaultdict(deque)
        self.lock = Lock()

    def allow(self, user_id):
        now = time.monotonic()
        with self.lock:
            for key in list(self.calls):
                if not self.calls[key] or self.calls[key][-1] <= now - 60:
                    del self.calls[key]
            calls = self.calls[user_id]
            while calls and calls[0] <= now - 60:
                calls.popleft()
            if len(calls) >= 5:
                return False
            calls.append(now)
            return True


@bp.app_context_processor
def analysis_context():
    user = getattr(g, 'user', None)
    return {'image_analysis_form_token': form_token()} if user is not None and user['Usertype'] == 'designer' else {}


@bp.errorhandler(RequestEntityTooLarge)
def image_too_large(error):
    return jsonify(error='The upload exceeds the 15 MB request limit.'), 413


@bp.route('/api/analyze-image', methods=['POST'])
def analyze_image():
    if g.user is None:
        return jsonify(error='Sign in as an interior designer to analyse an image.'), 401
    if g.user['Usertype'] != 'designer':
        return jsonify(error='Only interior designers can analyse project images.'), 403
    try:
        validate_form_token()
        file = request.files.get('image')
        image = ImageAnalysis.prepare_image(file)
        categories = [r['name'] for r in Category.find_all_active()]
        key = current_app.config.get('GEMINI_API_KEY', '')
        model = (current_app.config.get('GEMINI_IMAGE_MODEL') or current_app.config.get('GEMINI_MODEL'))
        if key and not current_app.extensions['image_analysis_rate_limit'].allow(g.user['id']):
            response = jsonify(error='Please wait a minute before analysing more images.')
            response.headers['Retry-After'] = '60'
            return response, 429
        result = ImageAnalysis(key, model).analyse(image, categories)
        return jsonify(result)
    except RequestEntityTooLarge:
        return image_too_large(None)
    except BadRequest:
        return jsonify(error='The form expired or is invalid. Reload the page and try again.'), 400
    except ValidationError as error:
        return jsonify(error=str(error)), 400
    except ImageAnalysisUnavailable as error:
        return jsonify(error=str(error)), error.status

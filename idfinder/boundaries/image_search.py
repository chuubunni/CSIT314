"""Customer route: HTTP input/output only; core decisions live in controller."""
from flask import Blueprint, render_template, request, session
from idfinder.boundaries.auth import auth_boundary
from idfinder.boundaries.customer import customer_boundary
from idfinder.boundaries.form_security import form_token, validate_form_token
from idfinder.controller.errors import ValidationError
from idfinder.controller.image_search_controller import ImageSearchController
from idfinder.controller.search_controller import SearchController

bp = Blueprint('image_search', __name__)


@bp.route('/search/image', methods=['GET', 'POST'])
@auth_boundary.login_required
@customer_boundary.customer_required
def index():
    ctrl = ImageSearchController
    error = None
    # Opening Image Search from Browse Projects starts a fresh search.
    # Regular GETs (filter links and style chips) preserve the current image.
    if request.method == 'GET' and request.args.get('new') == '1':
        session.pop('image_search_features', None)
        session.pop('image_search_method', None)
    if request.method == 'POST':
        validate_form_token()
        photo = request.files.get('photo')
        if photo is None:
            session.pop('image_search_features', None)
            error = 'Choose a JPG or PNG picture.'
        else:
            try:
                raw = photo.stream.read(5 * 1024 * 1024 + 1)
                features, method = ctrl.analyse_upload(raw, photo.filename or '')
                session['image_search_features'] = features
                session['image_search_method'] = method
            except ValidationError as exc:
                session.pop('image_search_features', None)
                error = str(exc)
    features = session.get('image_search_features') if not error else None
    # A newly uploaded photo starts a fresh search. GET requests retain filters
    # so customers can refine the current image without uploading it again.
    selected = {name: (request.args.get(name, '') if request.method == 'GET' else '') for name in
                ('property_type', 'property_subtype_id', 'category_id', 'min_price', 'max_price')}
    results = []
    if features:
        try:
            results = ctrl.results(features, selected['property_type'], selected['property_subtype_id'],
                                   selected['category_id'], selected['min_price'], selected['max_price'])
        except ValidationError as exc:
            error = str(exc)
    types, subtypes = SearchController.options()
    return render_template('search/image.html', results=results, features=features,
                           method=session.get('image_search_method', ''), error=error,
                           property_types=types, property_subtypes=subtypes,
                           categories=SearchController.categories(), selected=selected,
                           story_form_token=form_token()), 400 if error else 200

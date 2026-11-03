# C18: AI customer chat assistant, search results and relevant page navigation.
"""C18: customer-only page and JSON endpoints. No automatic redirects or writes."""
import secrets
import json
from math import ceil
from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import abort
from idfinder.boundaries.form_security import form_token, validate_form_token
from idfinder.controller.chatbot_controller import ChatbotController
from idfinder.controller.errors import ValidationError
from idfinder.entities.chatbot_catalogue import ChatbotCatalogue
from idfinder.services.gemini_chat import ChatbotUnavailable, GeminiChat

bp = Blueprint('chatbot', __name__, url_prefix='/chat')
DESTINATIONS = {
    'home': ('home.index', 'Browse projects'),
    'profile': ('customer.profile', 'My profile'),
    'favourites': ('favourites.list_favourites', 'My favourites'),
    'designers': ('search.designers', 'Find designers'),
    'chat': ('chatbot.chat', 'Uncle David'),
    'project_search': ('chatbot.project_results', 'View all matching projects'),
    'leaderboard': ('reviews.leaderboard', 'View full leaderboard'),  # C18: existing ranked results page.
}


def project_search_params(filters):
    """C18: share validated names/values, never raw SQL or internal query fragments."""
    params = {key: filters[key] for key in ('min_price', 'max_price')
              if filters.get(key) is not None}
    housing = filters.get('housing_options')
    if housing:
        params['housing'] = [json.dumps({k: option[k] for k in ('property_type', 'subtype_name') if option.get(k)}, separators=(',', ':')) for option in housing]
    else:
        params.update({key: filters[key] for key in ('property_type', 'subtype_name') if filters.get(key)})
    terms = filters.get('keywords') or ([filters['keyword']] if filters.get('keyword') else [])
    if terms:
        params.update(keyword=terms, keyword_mode=filters.get('keyword_mode', 'any'))
    styles = filters.get('categories') or ([filters['category']] if filters.get('category') else [])
    if styles:
        params.update(category=styles, mode=filters.get('category_mode', 'any'))
    return params


# C18: enforce customer login and role restrictions before chat access.
def customer_access(api=False):
    if g.user is None:
        if api:
            return jsonify(reply='Please log in again.', login_url=url_for('auth.login')), 401
        return redirect(url_for('auth.login'))
    if g.user['Usertype'] != 'customer':
        return jsonify(reply='Uncle David is available to customer accounts.'), 403
    return None


# C18: isolate conversation memory by authenticated user and login session.
def conversation_key():
    if 'chatbot_session' not in session:
        session['chatbot_session'] = secrets.token_urlsafe(24)
    return (g.user['id'], session['chatbot_session'])


@bp.app_context_processor
def widget_context():
    # C18: every customer page includes the same floating assistant.
    if getattr(g, 'user', None) is None or g.user['Usertype'] != 'customer':
        return {}
    conversation_key()
    return {'chat_widget_token': form_token(),
            'chat_widget_configured': bool(current_app.config['GEMINI_API_KEY']),
            'chat_widget_storage_key': 'idfinder-chat-' + session['chatbot_session']}


@bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.errorhandler(400)
def bad_request(error):
    if request.endpoint in ('chatbot.message', 'chatbot.reset'):
        return jsonify(reply='Your form expired or the request was invalid. Reload the page and try again.'), 400
    return error


class chatbot_boundary:
    # C18: list every matching project in pages without another Gemini request.
    @bp.route('/projects')
    def project_results():
        denied = customer_access()
        if denied is not None:
            return denied
        try:
            allowed = {'property_type', 'subtype_name', 'housing', 'keyword', 'keyword_mode', 'min_price', 'max_price', 'category', 'mode', 'page'}
            if set(request.args) - allowed:
                raise ValidationError('That search option is not supported.')
            for name in allowed - {'category', 'housing', 'keyword'}:
                if len(request.args.getlist(name)) > 1:
                    raise ValidationError('Please supply one value for each search option.')
            incoming = {name: request.args[name] for name in ('property_type', 'subtype_name') if name in request.args}
            if 'housing' in request.args:
                raw_options = request.args.getlist('housing')
                if len(raw_options) > 10 or any(len(value) > 300 for value in raw_options):
                    raise ValidationError('Choose up to 10 valid housing alternatives.')
                try:
                    incoming['housing_options'] = [json.loads(value) for value in raw_options]
                except ValueError:
                    raise ValidationError('Use valid housing alternatives.') from None
            if 'keyword' in request.args:
                incoming['keywords'] = request.args.getlist('keyword')
            if 'keyword_mode' in request.args:
                incoming['keyword_mode'] = request.args['keyword_mode']
            for name in ('min_price', 'max_price'):
                if name in request.args:
                    try:
                        incoming[name] = int(request.args[name])
                    except ValueError:
                        raise ValidationError('Use a valid budget in whole Singapore dollars.') from None
            if 'category' in request.args:
                incoming['categories'] = request.args.getlist('category')
            if 'mode' in request.args:
                incoming['category_mode'] = request.args['mode']
            try:
                page = int(request.args.get('page', '1'))
            except ValueError:
                raise ValidationError('Choose a valid results page.') from None
            if not 1 <= page <= 10000:
                raise ValidationError('Choose a valid results page.')
            filters = ChatbotController(None).clean_filters(incoming, {}, False)
            total, projects = ChatbotCatalogue.search(filters, limit=20, offset=(page - 1) * 20)
            pages = max(1, ceil(total / 20))
            if page > pages:
                abort(404)
            params = project_search_params(filters)
            previous = url_for('chatbot.project_results', **params, page=page - 1) if page > 1 else None
            next_page = url_for('chatbot.project_results', **params, page=page + 1) if page < pages else None
            return render_template('chatbot/results.html', projects=projects, total=total, filters=filters,
                                   page=page, pages=pages, previous=previous, next_page=next_page, error=None)
        except ValidationError as error:
            return render_template('chatbot/results.html', projects=[], total=0, filters={}, page=1,
                                   pages=1, previous=None, next_page=None, error=str(error)), 400

    @bp.route('/')
    def chat():
        denied = customer_access()
        if denied is not None:
            return denied
        return render_template('chatbot/chat.html')

    # C18: restore recent conversation when customers move between pages.
    @bp.route('/history')
    def history():
        denied = customer_access(api=True)
        if denied is not None:
            return denied
        messages, pending = current_app.extensions['chatbot_state'].history(conversation_key(), g.user['id'])
        return jsonify(messages=messages, pending=pending)

    # C18: validate submitted messages and return grounded replies and safe links.
    @bp.route('/message', methods=('POST',))
    def message():
        denied = customer_access(api=True)
        if denied is not None:
            return denied
        if request.content_length is None or request.content_length > 8192:
            return jsonify(reply='Please send a shorter message.'), 413
        validate_form_token()
        if len(request.form.getlist('message')) != 1:
            return jsonify(reply='Send one message at a time.'), 400
        text = request.form.get('message', '').strip()
        if not text or len(text) > 600:
            return jsonify(reply='Enter a message between 1 and 600 characters.'), 400
        key, user_id = conversation_key(), g.user['id']
        store = current_app.extensions['chatbot_state']
        try:
            state = store.begin(key, user_id)
        except ChatbotUnavailable as error:
            return jsonify(reply=str(error)), error.status
        updated = None
        try:
            answer, updated = ChatbotController(GeminiChat(
                current_app.config['GEMINI_API_KEY'], current_app.config['GEMINI_MODEL'])).reply(text, state)
            # C18: derive every URL from known endpoints and actual database IDs.
            for project in answer['projects']:
                project['url'] = url_for('home.project_detail', idp_id=project['id'])
            # C18: profile links come from real ranked designer IDs, never AI URLs.
            for designer in answer.get('leaderboard', []):
                designer['url'] = url_for('reviews.designer_profile', designer_id=designer['id'])
            for action in answer['actions']:
                page = action.pop('page')
                endpoint, label = DESTINATIONS[page]
                # C18: ranking links retain exactly the validated board filters and weights.
                params = action.pop('leaderboard_params', {}) if page == 'leaderboard' else (
                    project_search_params(action.pop('filters')) if 'filters' in action else (
                        {'name': action.pop('name')} if 'name' in action else {}))
                action.update(label=label, url=url_for(endpoint, **params))
            # C18: retain only validated display data across page loads.
            updated['transcript'] = (state.get('transcript', []) + [
                {'role': 'user', 'text': text}, {'role': 'assistant', 'data': answer}])[-16:]
            return jsonify(answer)
        except ValidationError as error:
            return jsonify(reply=str(error), recoverable=True), 422
        except ChatbotUnavailable as error:
            return jsonify(reply=str(error)), error.status
        finally:
            store.finish(key, user_id, updated)

    # C18: allow customers to clear conversation and search context.
    @bp.route('/reset', methods=('POST',))
    def reset():
        denied = customer_access(api=True)
        if denied is not None:
            return denied
        validate_form_token()
        try:
            current_app.extensions['chatbot_state'].clear(conversation_key(), g.user['id'])
        except ChatbotUnavailable as error:
            return jsonify(reply=str(error)), error.status
        return jsonify(reply='New conversation started. What would you like to find?')

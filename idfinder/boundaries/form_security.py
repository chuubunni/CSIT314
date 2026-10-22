# C08 / ID19: session-bound form tokens for the new state-changing forms.
import secrets
from flask import abort, request, session


def form_token():
    if 'story_form_token' not in session:
        session['story_form_token'] = secrets.token_hex(32)
    return session['story_form_token']


def validate_form_token():
    expected = session.get('story_form_token', '')
    supplied = request.form.get('form_token', '')
    if not expected or not secrets.compare_digest(expected, supplied):
        abort(400, 'Form expired. Reload the page and try again.')

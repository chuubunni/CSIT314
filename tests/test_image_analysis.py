"""AI auto-fill and duplicate-image review coexist; no live Gemini calls."""
import base64
import io
import json
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from PIL import Image, ImageDraw
from werkzeug.datastructures import FileStorage

from story_fixture import StoryFixture
from idfinder.db import get_db
from idfinder.entities.idp import IDP
from idfinder.services.image_analysis import ImageAnalysis, ImageAnalysisUnavailable
from idfinder.controller.errors import ValidationError


def photo():
    image = Image.new('RGB', (600, 400), '#dedbc8')
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 190, 240), fill='#6595ad')
    draw.rectangle((210, 140, 550, 300), fill='#47392a')
    draw.ellipse((180, 300, 390, 380), fill='#22472c')
    stream = io.BytesIO()
    image.save(stream, 'JPEG')
    return stream.getvalue()


class Response:
    def __init__(self, action=None, raw=None, finish='STOP'):
        action = action or {'title': 'Warm timber living room', 'description': 'Timber cabinetry frames a bright seating area. Soft colours and natural light create a calm interior.', 'category': 'Modern'}
        self.raw = raw if raw is not None else json.dumps({'candidates': [{'finishReason': finish, 'content': {'parts': [{'text': json.dumps(action)}]}}]}).encode()
    def __enter__(self):return self
    def __exit__(self, *args):return False
    def read(self, limit):return self.raw[:limit]


class ImageAnalysisTests(StoryFixture):
    def setUp(self):
        super().setUp()
        self.app.config.update(GEMINI_API_KEY='test-key-only', GEMINI_MODEL='gemini-test')

    def form(self, user=1):
        self.login(user)
        assert self.client.get('/portfolio/new').status_code == 200
        with self.client.session_transaction() as session:return session['story_form_token']

    def analyse(self, token=None, contents=None, name='room.jpg'):
        return self.client.post('/api/analyze-image', data={
            'form_token': token or '', 'image': (io.BytesIO(contents if contents is not None else photo()), name),
        })

    def snapshot(self):
        db = get_db()
        return {r[0]: [tuple(row) for row in db.execute(f'SELECT * FROM "{r[0]}" ORDER BY rowid')]
                for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}

    @patch('idfinder.services.image_analysis.build_opener')
    def test_analysis_is_read_only_and_uses_server_config(self, opener):
        token = self.form()
        before = self.snapshot()
        files = sorted(str(p) for p in Path(self.temp.name).rglob('*'))
        opener.return_value.open.return_value = Response()
        response = self.analyse(token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['category'], 'Modern')
        self.assertEqual(before, self.snapshot())
        self.assertEqual(files, sorted(str(p) for p in Path(self.temp.name).rglob('*')))
        args, kwargs = opener.return_value.open.call_args
        request = args[0]
        self.assertIn('/gemini-test:generateContent', request.full_url)
        self.assertEqual(request.get_header('X-goog-api-key'), 'test-key-only')
        self.assertEqual(kwargs['timeout'], 20)
        payload = json.loads(request.data)
        encoded = payload['contents'][0]['parts'][1]['inlineData']
        self.assertEqual(encoded['mimeType'], 'image/jpeg')
        with Image.open(io.BytesIO(base64.b64decode(encoded['data']))) as image:
            self.assertLessEqual(max(image.size), 1536)
        schema = payload['generationConfig']['responseSchema']
        self.assertEqual(set(schema['properties']['category']['enum']), {'Modern', 'Minimalist', 'Empty'})

    @patch('idfinder.services.image_analysis.build_opener')
    def test_auth_token_and_invalid_images_prevent_ai_calls(self, opener):
        self.assertEqual(self.analyse().status_code, 401)
        for user in (3, 4):
            self.login(user)
            self.assertEqual(self.analyse().status_code, 403)
        token = self.form()
        self.assertEqual(self.analyse('invalid').status_code, 400)
        self.assertEqual(self.analyse(token, b'not really an image').status_code, 400)
        self.assertEqual(self.analyse(token, name='room.webp').status_code, 400)
        self.assertEqual(self.analyse(token, name='jpg').status_code, 400)
        self.assertEqual(self.client.post('/api/analyze-image', data={'form_token': token}).status_code, 400)
        stream = io.BytesIO()
        Image.new('RGB', (20,20), 'red').save(stream, 'GIF', save_all=True, append_images=[Image.new('RGB',(20,20),'blue')])
        self.assertEqual(self.analyse(token, stream.getvalue(), 'room.gif').status_code, 400)
        opener.assert_not_called()

    @patch('idfinder.services.image_analysis.build_opener')
    def test_missing_key_does_not_break_pages_or_image_save(self, opener):
        self.app.config['GEMINI_API_KEY'] = ''
        token = self.form()
        self.assertEqual(self.analyse(token).status_code, 503)
        self.ctrl.add_image(1, 1, FileStorage(io.BytesIO(photo()), filename='normal.jpg'))
        self.assertEqual(IDP.find(1)['approval_status'], 'approved')
        opener.assert_not_called()

    @patch('idfinder.services.image_analysis.build_opener')
    def test_successful_analysis_does_not_bypass_duplicate_approval(self, opener):
        self.ctrl.add_image(1, 1, FileStorage(io.BytesIO(photo()), filename='original.jpg'))
        token = self.form()
        opener.return_value.open.return_value = Response()
        result = self.analyse(token).json
        subtype = IDP.find(1)['property_subtype_id']
        response = self.client.post('/portfolio/new', data={
            'title': result['title'], 'description': result['description'], 'property_type': 'HDB',
            'property_subtype_id': subtype, 'price': '20000', 'status': 'completed',
            'category_ids': '1', 'images': (io.BytesIO(photo()), 'copy.jpg'), 'form_token': token,
        })
        self.assertEqual(response.status_code, 302)
        db = get_db()
        project = db.execute('SELECT * FROM idp ORDER BY id DESC LIMIT 1').fetchone()
        self.assertEqual(project['approval_status'], 'pending')
        self.assertEqual(db.execute('SELECT count(*) FROM image_review_case WHERE project_id=?', (project['id'],)).fetchone()[0], 1)
        self.login(3)
        self.assertEqual(self.client.get(f'/projects/{project["id"]}').status_code, 404)
        media = db.execute('SELECT link FROM idp_media WHERE idp_id=?', (project['id'],)).fetchone()[0]
        self.assertEqual((Path(self.temp.name)/media).read_bytes(), photo())
        self.assertEqual(self.client.get('/static/uploads/' + media).status_code, 404)
        self.login(4)
        self.assertEqual(self.client.get(f'/platform/image-reviews/projects/{project["id"]}').status_code, 200)
        with self.client.session_transaction() as session:manager_token = session['story_form_token']
        response = self.client.post(f'/platform/image-reviews/projects/{project["id"]}', data={
            'form_token': manager_token, 'revision': project['image_revision'],
            'decision': 'approved', 'reason': 'Permission to reuse has been checked.',
        })
        self.assertEqual(response.status_code, 303)
        self.assertEqual(IDP.find(project['id'])['approval_status'], 'approved')
        self.login(3)
        self.assertEqual(self.client.get(f'/projects/{project["id"]}').status_code, 200)

    @patch('idfinder.services.image_analysis.build_opener')
    def test_edit_save_still_checks_images_after_analysis(self, opener):
        self.ctrl.add_image(3, 2, FileStorage(io.BytesIO(photo()), filename='other.jpg'))
        token = self.form()
        opener.return_value.open.return_value = Response()
        self.assertEqual(self.analyse(token).status_code, 200)
        response = self.client.post('/portfolio/1/edit', data={
            'title': 'Changed', 'description': 'Revised details', 'property_type': 'HDB',
            'property_subtype_id': IDP.find(1)['property_subtype_id'], 'price': '25000',
            'status': 'completed', 'category_ids': '1', 'images': (io.BytesIO(photo()), 'copy.jpg'),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(IDP.find(1)['approval_status'], 'pending')

    @patch('idfinder.services.image_analysis.build_opener')
    def test_rate_limit_and_current_sort_controls(self, opener):
        token = self.form()
        opener.return_value.open.return_value = Response()
        for _ in range(5):self.assertEqual(self.analyse(token).status_code, 200)
        response = self.analyse(token)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(opener.return_value.open.call_count, 5)
        html = self.client.get('/portfolio?sort_by=views').get_data(as_text=True)
        self.assertIn('Sort projects by', html)
        self.assertIn('Most viewed', html)
        self.assertIn('Most favourited', html)
        html = self.client.get('/portfolio/new').get_data(as_text=True)
        self.assertEqual(html.count('name="images"'), 1)
        self.assertIn('data-form-token=', html)

    @patch('idfinder.services.image_analysis.build_opener')
    def test_api_failures_are_controlled_without_leaking_errors(self, opener):
        token = self.form()
        for code, expected in [(400,503),(401,503),(403,503),(404,503),(429,429),(500,503)]:
            self.app.extensions['image_analysis_rate_limit'].calls.clear()
            opener.return_value.open.side_effect = HTTPError('secret-url',code,'sensitive details',{},None)
            response = self.analyse(token)
            self.assertEqual(response.status_code, expected)
            self.assertNotIn('secret', response.get_data(as_text=True))
        opener.return_value.open.side_effect = URLError('private network details')
        self.app.extensions['image_analysis_rate_limit'].calls.clear()
        self.assertEqual(self.analyse(token).status_code, 503)

    @patch('idfinder.services.image_analysis.build_opener')
    def test_size_limits_reject_before_google_call(self, opener):
        token = self.form()
        with patch('idfinder.services.image_analysis.ImageSimilarity.MAX_PIXELS', 100):
            self.assertEqual(self.analyse(token).status_code, 400)
        with patch('idfinder.services.image_analysis.ImageSimilarity.MAX_BYTES', 100):
            self.assertEqual(self.analyse(token).status_code, 400)
        self.app.config['MAX_CONTENT_LENGTH'] = 100
        response = self.analyse(token)
        self.assertEqual(response.status_code, 413)
        self.assertIn('error', response.json)
        opener.assert_not_called()

    @patch('idfinder.services.image_analysis.build_opener')
    def test_invalid_or_approval_changing_ai_output_is_rejected(self, opener):
        token = self.form()
        for action in [
            {'title':'Room','description':'Interior','category':'Inactive'},
            {'title':'Room','description':'Interior','category':'Modern','approval_status':'approved'},
            {'title':42,'description':'Interior','category':'Modern'},
        ]:
            self.app.extensions['image_analysis_rate_limit'].calls.clear()
            opener.return_value.open.return_value = Response(action)
            self.assertEqual(self.analyse(token).status_code, 502)
        self.app.extensions['image_analysis_rate_limit'].calls.clear()
        opener.return_value.open.return_value = Response(finish='MAX_TOKENS')
        self.assertEqual(self.analyse(token).status_code, 502)
        self.app.extensions['image_analysis_rate_limit'].calls.clear()
        opener.return_value.open.return_value = Response({'title':'Room','description':'A bright room.','category':None})
        self.assertEqual(self.analyse(token).status_code, 200)

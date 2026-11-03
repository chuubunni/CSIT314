# ID06 / ID07: create and edit a project and its images on one page.
import io
import os
from story_fixture import StoryFixture
from idfinder.db import get_db
from idfinder.entities.idp_media import IDPMedia


class ID07Tests(StoryFixture):
    def subtype(self, code='HDB'):
        return get_db().execute(
            'SELECT s.id FROM property_subtype s JOIN property_type t ON t.id = s.property_type_id'
            ' WHERE t.code = ? ORDER BY s.id LIMIT 1', (code,)).fetchone()[0]

    def form(self, **extra):
        data = {'title': 'Kitchen', 'description': 'New kitchen', 'property_type': 'HDB',
                'property_subtype_id': str(self.subtype()), 'price': '5000', 'status': 'completed'}
        data.update(extra)
        return data

    def image(self, name='photo.jpg'):
        return (io.BytesIO(b'fake image bytes'), name)

    def media(self, idp_id):
        return IDPMedia.find_by_idp(idp_id)

    def on_disk(self, link):
        return os.path.exists(os.path.join(self.temp.name, link))

    def test_id07_create_project_with_several_images(self):
        self.login(1)
        response = self.client.post('/portfolio/new', content_type='multipart/form-data',
                                    data=self.form(images=[self.image('a.jpg'), self.image('b.PNG')]))
        self.assertEqual(response.status_code, 302)
        idp_id = int(response.headers['Location'].rsplit('/', 1)[1])
        images = self.media(idp_id)
        self.assertEqual(len(images), 2)
        self.assertEqual([m['link'].rsplit('.', 1)[1] for m in images], ['jpg', 'png'])
        self.assertTrue(all(self.on_disk(m['link']) for m in images))

    def test_id07_create_project_without_images(self):
        self.login(1)
        response = self.client.post('/portfolio/new', content_type='multipart/form-data', data=self.form())
        self.assertEqual(response.status_code, 302)
        idp_id = int(response.headers['Location'].rsplit('/', 1)[1])
        self.assertEqual(self.media(idp_id), [])

    def test_id07_bad_image_saves_nothing(self):
        self.login(1)
        before = get_db().execute('SELECT COUNT(*) FROM idp').fetchone()[0]
        response = self.client.post('/portfolio/new', content_type='multipart/form-data',
                                    data=self.form(images=[self.image('a.jpg'), self.image('notes.pdf')]))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Wrong file extension', response.data)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM idp').fetchone()[0], before)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM idp_media').fetchone()[0], 0)
        self.assertEqual([f for f in os.listdir(self.temp.name) if f.endswith('.jpg')], [])

    def test_id07_edit_adds_images_and_keeps_existing(self):
        old = self.ctrl.add_image(1, 1, self.file('old.jpg'))
        self.login(1)
        response = self.client.post('/portfolio/1/edit', content_type='multipart/form-data',
                                    data=self.form(images=[self.image('new.gif')]))
        self.assertEqual(response.status_code, 302)
        images = self.media(1)
        self.assertEqual(len(images), 2)
        self.assertEqual(images[0]['mediaID'], old)

    def test_id07_edit_removes_ticked_images(self):
        keep = self.ctrl.add_image(1, 1, self.file('keep.jpg'))
        drop = self.ctrl.add_image(1, 1, self.file('drop.jpg'))
        dropped_link = IDPMedia.find(drop)['link']
        self.login(1)
        response = self.client.post('/portfolio/1/edit', content_type='multipart/form-data',
                                    data=self.form(remove_media_ids=[str(drop)]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual([m['mediaID'] for m in self.media(1)], [keep])
        self.assertFalse(self.on_disk(dropped_link))

    def test_id07_cannot_remove_another_projects_image(self):
        other = self.ctrl.add_image(3, 2, self.file('theirs.jpg'))   # project 3 belongs to designer 2
        self.login(1)
        response = self.client.post('/portfolio/1/edit', content_type='multipart/form-data',
                                    data=self.form(title='Changed', remove_media_ids=[str(other)]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(IDPMedia.find(other))
        self.assertEqual(get_db().execute('SELECT title FROM idp WHERE id=1').fetchone()[0], 'First')

    def test_id07_form_and_detail_pages(self):
        self.ctrl.add_image(1, 1, self.file('shown.jpg'))
        self.login(1)
        new_page = self.client.get('/portfolio/new').data.decode()
        self.assertIn('enctype="multipart/form-data"', new_page)
        self.assertIn('name="images"', new_page)
        self.assertIn('multiple', new_page)
        edit_page = self.client.get('/portfolio/1/edit').data.decode()
        self.assertIn('name="remove_media_ids"', edit_page)
        detail = self.client.get('/portfolio/1').data.decode()
        self.assertNotIn('type="file"', detail)
        self.assertIn('href="/portfolio/1/edit"', detail)

    def test_designer_header_links_line_up(self):
        self.login(1)
        for path in ('/portfolio', '/portfolio/1'):
            page = self.client.get(path).data.decode()
            header = page[page.index('<header>'):page.index('</header>')]
            self.assertNotIn('<a href=', header, path)    # every header link uses class="action"

    def file(self, name):
        from werkzeug.datastructures import FileStorage
        return FileStorage(stream=io.BytesIO(b'fake image bytes'), filename=name)

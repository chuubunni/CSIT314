# C08 / ID19: integration tests for the supplied idfinder repository and schema.
from pathlib import Path
import sqlite3
import tempfile
import unittest
from urllib.parse import urlsplit, parse_qs
from werkzeug.security import generate_password_hash
from idfinder import create_app
from idfinder.db import get_db, init_db
from idfinder.housing_migration import migrate_housing
from idfinder.entities.idp import IDP
from idfinder.controller.portfolio_controller import PortfolioController
from idfinder.controller.errors import ValidationError, PermissionDenied, NotFoundError


class StoryFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-only',
                              'DATABASE': str(Path(self.temp.name)/'test.sqlite'),
                              'UPLOAD_FOLDER': self.temp.name})
        self.context = self.app.app_context(); self.context.push()
        init_db(); migrate_housing(get_db())
        db = get_db()
        for user_id, role in [(1,'designer'),(2,'designer'),(3,'customer'),(4,'manager'),(5,'customer'),(6,'customer')]:
            db.execute('INSERT INTO user(id,name,password,email,phone,Usertype) VALUES (?,?,?,?,?,?)',
                       (user_id,role,generate_password_hash('test-pass',method='pbkdf2:sha256:1000'),f'{user_id}@example.test',str(user_id),role))
        db.executemany('INSERT INTO company(companyID,companyName,companyLine) VALUES (?,?,?)',[(1,'Studio A','111'),(2,'Studio B','222')])
        db.executemany('INSERT INTO designer(userID,companyID) VALUES (?,?)',[(1,1),(2,2)])
        db.executemany('INSERT INTO customer(cust_id,current_property_type,received_keys) VALUES (?, ?, ?)',[(3,'HDB',1),(5,'Condo',0)])
        db.execute('INSERT INTO platform(managerID) VALUES (4)')
        db.executemany('INSERT INTO category(id,name,active) VALUES (?,?,?)',[(1,'Modern',1),(2,'Minimalist',1),(3,'Inactive',0),(4,'Empty',1)])
        subtype=db.execute("SELECT s.id FROM property_subtype s JOIN property_type t ON t.id=s.property_type_id WHERE t.code='HDB' ORDER BY s.id LIMIT 1").fetchone()[0]
        for project,designer,title in [(1,1,'First'),(2,1,'Second'),(3,2,'Other designer')]:
            columns=['id','designer_id','title','description','propertyType','price','status','property_subtype_id']
            values=[project,designer,title,'Sample project','HDB',10000,'completed',subtype]
            if any(row[1]=='houseType' for row in db.execute('PRAGMA table_info(idp)')):
                columns.append('houseType');values.append('2-Room')
            db.execute('INSERT INTO idp('+','.join(columns)+') VALUES ('+','.join('?' for _ in values)+')',values)
        db.executemany('INSERT INTO idp_category VALUES (?,?)',[(1,1),(2,1),(3,2)])
        db.commit()
        self.client=self.app.test_client(); self.ctrl=PortfolioController(self.temp.name)

    def tearDown(self):
        self.context.pop();self.temp.cleanup()

    def login(self,user_id):
        with self.client.session_transaction() as session:
            session.clear();session['user_id']=user_id

    def token(self,path='/'):
        response=self.client.get(path);self.assertEqual(response.status_code,200)
        with self.client.session_transaction() as session:return session['story_form_token']

    def save(self,project=1,**extra):
        return self.client.post(f'/favourites/projects/{project}',data={'form_token':self.token(),**extra})

    def categories(self,project):return sorted(IDP.find_category_ids(project))

    # C08: persisted state and duplicate handling use favourite_idp, not the old favourite table.

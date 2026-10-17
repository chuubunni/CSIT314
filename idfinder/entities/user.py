from werkzeug.security import generate_password_hash #this is because DB only stores password hash!

from idfinder.db import get_db #MUST match the name of the app folder!!!!!! 

class Users(): 
    def __init__(self, name, password, email, phone, Usertype):
        self.name = name 
        self.password = password
        self.email = email
        self.phone = phone
        self.Usertype = Usertype
        
    @staticmethod
    def create_user(name, password, email, phone, Usertype):
        db = get_db()
        cursor = db.execute('INSERT INTO user (name, password, email, phone, Usertype)'
                   ' VALUES (?, ?, ?, ?, ?)', (name, generate_password_hash(password), email, phone, Usertype))
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def get_info(id):
        return get_db().execute('SELECT * FROM user WHERE id = ?', (id,)).fetchone()

    @staticmethod 
    def check_email(email):
        db = get_db()
        isMailIn = db.execute('SELECT * FROM user WHERE email = ?',(email,)).fetchone()
        #.fetchone() returns one row from query
        #if query returns no results, returns None 
        #.fetchall() returns a list of all results
        return isMailIn
    
    @staticmethod
    def get_username(id):
        row = get_db().execute('SELECT name FROM user WHERE id = ?', (id,)).fetchone()
        return row['name'] if row else None

    @staticmethod
    def get_id(email):
        row = get_db().execute('SELECT id FROM user WHERE email = ?', (email,)).fetchone()
        return row['id'] if row else None

class customers(Users):
    @staticmethod 
    def create_customer(id, customerHouse):
        db = get_db()
        cursor = db.execute('INSERT INTO customer (cust_id, customerHouse)'
                            ' VALUES (?, ?)',(id, customerHouse))
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def get_customer_house(id):
        db = get_db()
        customerHouse = db.execute('SELECT customerHouse FROM customer WHERE cust_id = ?', (id,)).fetchone()
        return customerHouse

class designers(Users):
    """Designer accounts. A designer row links a user to a company (many designers per company)."""

    # --- low-level inserts: no commit, so callers can combine them in one transaction ---
    @staticmethod
    def _insert_company(db, companyName, companyLine, companyEmail):
        return db.execute(
            'INSERT INTO company (companyName, companyLine, companyEmail)'
            ' VALUES (?, ?, ?)',
            (companyName, companyLine, companyEmail)).lastrowid

    @staticmethod
    def _insert_designer(db, user_id, companyID):
        return db.execute(
            'INSERT INTO designer (userID, companyID) VALUES (?, ?)',
            (user_id, companyID)).lastrowid

    # --- single steps (each commits on its own) ---
    @staticmethod
    def create_company(companyName, companyLine, companyEmail):
        """Create a company on its own. Returns the new companyID."""
        db = get_db()
        companyID = designers._insert_company(
            db, companyName, companyLine, companyEmail)
        db.commit()
        return companyID

    @staticmethod
    def create_designer(id, companyID):
        """Attach an existing user to an EXISTING company (e.g. a second designer joining)."""
        db = get_db()
        cursor_id = designers._insert_designer(db, id, companyID)
        db.commit()
        return cursor_id

    # --- registration: company + designer together, all or nothing ---
    @staticmethod
    def register_designer(id, companyName, companyLine, companyEmail):
        """Create a NEW company and the designer row for user `id` in one transaction.

        If either insert fails (duplicate company phone number, designer already
        exists...) nothing is saved and sqlite3.IntegrityError is re-raised.
        Returns the new companyID.
        """
        db = get_db()
        try:
            companyID = designers._insert_company(
                db, companyName, companyLine, companyEmail)
            designers._insert_designer(db, id, companyID)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return companyID

    @staticmethod
    def get_company(id):
        """The company row of a designer, or None."""
        return get_db().execute(
            'SELECT c.* FROM designer d JOIN company c ON c.companyID = d.companyID'
            ' WHERE d.userID = ?', (id,)).fetchone()

class managers(Users):
    @staticmethod
    def create_manager(id):
        db = get_db()
        cursor = db.execute('INSERT INTO platform (managerID)'
                            ' VALUES (?)', (id,))
        db.commit()
        return cursor.lastrowid   


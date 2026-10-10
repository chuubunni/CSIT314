import functools 

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for,current_app
)

from werkzeug.security import check_password_hash, generate_password_hash #this is because DB only stores password hash!

from myfirstapp.db import get_db #MUST match the name of the app folder!!!!!! 

class Users(): 
    @staticmethod
    def create_user(name, password, email, phone, Usertype):
        db = get_db()
        cursor = db.execute('INSERT INTO user (name, password, email, phone, Usertype)'
                   ' VALUES (?, ?, ?, ?, ?)', (name, generate_password_hash(password), email, phone, Usertype))
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def create_customer(id):
        db = get_db()
        cursor = db.execute('INSERT INTO customer (cust_id)'
                            ' VALUES (?)', (id,))
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def create_manager(id):
        db = get_db()
        cursor = db.execute('INSERT INTO platform (managerID)'
                            ' VALUES (?)', (id,))
        db.commit()
        return cursor.lastrowid   

    @staticmethod 
    def create_designer(id, companyName, comapnyLine, companyDescription, companyEmail):
        db = get_db()
        cursor = db.execute('INSERT INTO designer (userID, companyName, companyLine, companyDescription, companyEmail)'
                            ' VALUES (?, ?, ?, ?, ?)', (id, companyName, comapnyLine, companyDescription, companyEmail))
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
    pass 

class designers(Users):
    pass

class managers(Users):
    pass
import functools 

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for,current_app
)

from werkzeug.security import check_password_hash, generate_password_hash #this is because DB only stores password hash!

from myfirstapp.db import get_db #MUST match the name of the app folder!!!!!! 

class Users(): 
    def get_username():
        db = get_db()
        username = db.execute(
            'SELECT name FROM user WHERE id = ?', (id, )
            #'SQL STATEMENT = ? ',(variable_that_replaces_?,)
        )
        return username
import functools 

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for,current_app
)

from werkzeug.security import check_password_hash, generate_password_hash

from myfirstapp.db import get_db #MUST match the name of the app folder!!!!!! 
from myfirstapp.entities.user import Users

def authenticate_user(email, password):
        user = Users.check_email(email)
        if user is None:
            error = 'Incorrect email address'
            return error
        elif not check_password_hash(user['password'],password):
        #check_password_hash = hashes the submitted password and compares them
            error = 'Incorrect password'
            return error
        else:
            return user

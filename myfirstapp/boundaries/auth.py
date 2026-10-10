import functools 

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for,current_app
)

from werkzeug.security import check_password_hash, generate_password_hash

from myfirstapp.db import get_db #MUST match the name of the app folder!!!!!! 
from myfirstapp.entities.user import Users


bp = Blueprint('auth', __name__, url_prefix='/auth')
#creates a blueprint named auth 
#blueprint needs to know where it is defined --> pass __name__ as second arg 
#url_prefix --> prepended to all urls associated with blueprint

#when user visists /auth/register url --> register view will return HTML form 
#user submit form --> validation 



@bp.before_app_request 
#before_app_request registers a function that runs before the view function, no matter what URL is requested!
def load_logged_in_user():
    user_id = session.get('user_id')
    #checks if a user id is stored in the session and gets the user's data from the DB, storing it on g.user 

    if user_id is None: 
        g.user = None
        #if user does not exist, g.user will be None
    else: 
        g.user = Users.get_info(user_id) #query to store data in g.user
        #g.user lasts for the length of the request

@bp.route('/logout')
def log_out_user():
    #no need to get user id, just clear session directly!

    session.clear() #removes user_id from session
    return redirect(url_for('index'))

#to require user to be logged in for editing: 
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None: 
            return redirect(url_for('auth.login'))
            #url_for() function gerenates url to a view based on name and args 
            #name associated with view = endpoint 
            #when used with blueprint, the name of blueprint prepended to function name 
            #endpoint for Login function is auth.Login --> added to auth blueprint
        return view (**kwargs)
    return wrapped_view 
#returns a new view function that wraps original view 
#function checks if user is loaded and redirects to the login page otherwise 
#if user is loaded original view continues 

@bp.route('/login', methods=('GET','POST'))
def login():
    if request.method == 'POST': #not GET but POST!
        email = request.form['email']
        password = request.form['password'] #prompt user to enter password and username 
        error = None 
        user = Users.check_email(email)
        #start fetching results from database after user has entered (if user enters nothing will show generic error message)

        if user is None:
            error = 'Incorrect email address'
        elif not check_password_hash(user['password'],password):
        #check_password_hash = hashes the submitted password and compares them
            error = 'Incorrect password'
        #wrong!!!!
        # else: <-- this is for USER not ERROR!
        #     return render_template('homepage') 

        #redirect user when login success
        if error is None: 
            session.clear()
            #session = dict that stores data across requests 
            #when validation succeeds, user's id stored in new session 
            session['user_id'] = user['id']

            #to get user type: g.user['Usertype']
            return redirect(url_for('index'))
        flash(error)
    return render_template('/auth/login.html') #always send user to login.html after error!

@bp.route('/register', methods=('GET','POST')) 
#associates the url '/register' with the 'register' view function
#when Flask recieves a request to /auth/register it will call register view and use return value as response 
#MUST BE PAIRED ALONG WITH def register()....
def register():
    if request.method == 'POST':
        #if user has submitted form, request.method will be 'POST'
        #starts validating the output
        name = request.form['name']
        #request.form = special type of dict mapping submmited form keys and values 
        password = request.form['password']
        email = request.form['email']
        phoneNo = request.form['phone']
        Usertype = request.form['type']
        db = get_db() #from db.py
        error = None

        if not name:
            error = 'name is required'
        elif not password:
            error = 'password is required'
        #ensure that username and password are not empty

        if error is None: 
        #validation succeeds 
            try: 
                Users.create_user(name, password, email, phoneNo, Usertype)
                    #takes SQL query with ? as placeholders for user input 
                    #DB will escape values --> no SQL inject
                    #add comma after every item in biggest bracket!
                    #for security, store passwords as hash using generate_password_hash
            except db.IntegrityError:
            #db.IntegrityError --> occurs if email already exists 
                error = f"This email {email} has already registered."
            else:
                if Usertype == 'designer':
                    return redirect(url_for("auth.designer_register", email=email))
                return redirect(url_for("auth.login"))
                #after storing user, redirected to login page 

        flash(error)
        #if validation fails, error shown to user 
        #flash() stores messages that can be retrieved when rendering template 

    return render_template('auth/register.html')
    #when user initially navigates to auth/register or there was validation error, HTML page with registration form is shown

@bp.route('/<string:email>/designer_register', methods=('GET','POST'))
def designer_register(email):
    if request.method == "POST":
        db = get_db()
        companyName = request.form['companyName']
        companyLine = request.form['companyLine']
        companyDescription = request.form['companyDescription']
        companyEmail = request.form['companyEmail']
        designerid = Users.get_id(email)
        try: 
            Users.create_designer(designerid, companyName, companyLine, companyDescription, companyEmail)
        except db.IntegrityError: 
            error = f"You have already registered as a designer."
        else: 
            return redirect(url_for("auth.login"))
    return render_template('auth/designer_register.html')
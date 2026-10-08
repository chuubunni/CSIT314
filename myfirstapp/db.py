import sqlite3 
from datetime import datetime 

import click 
from flask import current_app, g #g is unique for each request
#current_app = special object that points to Flask app handling the request

def get_db(): #called when app has been created and is handling a request
    if 'db' not in g: 
        g.db = sqlite3.connect( #establishes connection to the file pointed by DATABASE in create_app in __init__.py
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row #tells the connection to return rows that behave like dicts --> columns can be accessed by name
    return g.db

def close_db(e=None): #checks if connection was created by checking if g.db was set
    db = g.pop('db', None)

    if db is not None:  #if connection exists, closed 
        db.close() 

def init_db():
    db = get_db() #returns DB connection

    with current_app.open_resource('schema.sql') as f: #opens a file relative to myfirstapp package 
        db.executescript(f.read().decode('utf-8'))
        #use connection from get_db to read commands from schema.sql

@click.command('init-db') #defines command line 'init-db' that called the init-db function 
def init_db_command():
    #clear existing data and make new tables 
    init_db()
    click.echo('Initialzied the database')#shows success message to user 

sqlite3.register_converter( #tells python how to interpret timestamp values in DB
    "timestamp", lambda v: datetime.fromisoformat(v.decode())
)

def init_app(app):
    app.teardown_appcontext(close_db) #tells flask to call 'close_db' during cleanup after returning response 
    app.cli.add_command(init_db_command) #adds a new command that can be called with the flask command

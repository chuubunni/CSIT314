from flask import Blueprint, render_template

from myfirstapp.entities.idp import IDP
from myfirstapp.entities.idp_media import IDPMedia

bp = Blueprint('home', __name__)


@bp.route('/')
def index():
    """Home page: all IDPs, newest first."""
    return render_template('home/index.html', idps=IDP.find_all())
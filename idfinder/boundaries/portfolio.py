
from flask import (
    Blueprint, current_app, flash, g, redirect, render_template, request, url_for
)

from idfinder.boundaries.auth import login_required

from idfinder.controller.portfolio_controller import PortfolioController

bp = Blueprint('portfolio',__name__)

# boundaries/portfolio.py
@bp.route("/portfolio/upload", methods=("GET", "POST"))
@login_required
def upload():
    if request.method == "POST":
        try:
            PortfolioController().upload_image(
                request.files.get("file"),
                g.user["id"], current_app.config["UPLOAD_FOLDER"])
            return redirect(url_for("portfolio.show_stuff"))
        except ValueError as e:
            flash(str(e))
    return render_template("designer/upload.html") #use for GET

# return redirect(url_for("portfolio.show_stuff")) use redirect for POST requests AND if 'show_stuff' is a defined method!

# return render_template("designer/upload_file.html") use for GET 

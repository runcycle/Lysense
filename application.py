import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///lysense.db")

@app.route("/")
@login_required
def index():

    if session["user_id"]:

        # Select data to be inserted into tables
        software = db.execute("SELECT * FROM software WHERE id=:id", id=session["user_id"])
        licenses = db.execute("SELECT * FROM licenses WHERE id=:id", id=session["user_id"])

        return render_template("index.html", software=software, licenses=licenses)
    else:
        return redirect("/login")


@app.route("/addSoftware", methods=["GET", "POST"])
@login_required
def addSoftware():
    """Add Software"""

    if request.method == "POST":

        # Insert user input in software db
        db.execute("INSERT INTO software (brand, software, licensesAllowed, licensesRemaining, id) VALUES (:brand, :software, :licensesAllowed, :licensesRemaining, :id)",
                brand=request.form.get("brand"),
                software=request.form.get("software"),
                licensesAllowed=request.form.get("licensesAllowed"),
                licensesRemaining=request.form.get("licensesAllowed"),
                id=session["user_id"])

        # Remove spaces from data
        db.execute("UPDATE software SET software=REPLACE(software, ' ', '')")
        db.execute("UPDATE software SET brand=REPLACE(brand, ' ','')")

        flash("You have successfully added %s %s." % (request.form.get("brand"), request.form.get("software")))

        return redirect("/")

    else:
        return render_template("addSoftware.html")


@app.route("/addLicense", methods=["GET", "POST"])
@login_required
def addLicense():
    """Add License"""

    if request.method == "POST":

        # Insert user input into licenses db
        db.execute("INSERT INTO licenses (serialNumber, version, computerName, authCode, id, software) VALUES (:serialNumber, :version, :computerName, :authCode, :id, :software)",
                serialNumber=request.form.get("serialNumber"),
                version=request.form.get("version"),
                computerName=request.form.get("computerName"),
                authCode=request.form.get("authCode"),
                id=session["user_id"],
                software=request.form.get("software"))

        count = db.execute("SELECT licensesRemaining FROM software WHERE id=:id AND software=:software",
                        id=session["user_id"],
                        software=request.form.get("software"))

        # Update license count
        db.execute("UPDATE software SET licensesRemaining=licensesRemaining-1 WHERE id=:id AND software=:software",
                id=session["user_id"],
                software=request.form.get("software"))

        flash("You have successfully added the %s license." % (request.form.get("software")))

        return redirect("/")

    else:
        # Select software, loop over data, and send to addLicense
        allSoftware = db.execute("SELECT software FROM software WHERE id=:id", id=session["user_id"])

        softwareArr = []

        for element in allSoftware:
            softwareArr.append(element["software"])

        # Select brand, loop over data, and send to addLicense
        allBrands = db.execute("SELECT brand FROM software WHERE id=:id", id=session["user_id"])

        brandArr = []

        for element in allBrands:
            brandArr.append(element["brand"])

        return render_template("addLicense.html", softwareArr=softwareArr, brandArr=brandArr)


@app.route("/selectComputer", methods=["GET", "POST"])
@login_required
def selectComputer():
    """Remove license"""
    if request.method == "POST":
        # Add computer Id to session variable
        session["computerName"] = request.form.get("computerName")

        compSelect = session["computerName"]
        # Use compSelect to isolate data for select
        selectSoftware = db.execute("SELECT software FROM licenses WHERE id=:id AND computerName=:computerName",
                                id=session["user_id"],
                                computerName=compSelect)
        # Loop over all software installed for computer
        softwareArr = []

        for element in selectSoftware:
            softwareArr.append(element["software"])

        return render_template("/subtractLicense.html", softwareArr=softwareArr, compSelect=compSelect)
    else:
        # Select all computers, removing duplicates, to loop over and send to selectComputer
        allComputers = db.execute("SELECT DISTINCT computerName from licenses WHERE id=:id", id=session["user_id"])

        computerArr = []

        for element in allComputers:
            computerArr.append(element["computerName"])

        return render_template("selectComputer.html", computerArr=computerArr)


@app.route("/subtractLicense", methods=["GET", "POST"])
@login_required
def subtractLicense():
    """Remove license"""
    if request.method == "POST":
        # Execute the license delete based on user input
        db.execute("DELETE FROM licenses WHERE id=:id AND computerName=:computerName AND software=:software",
                id=session["user_id"],
                computerName=session["computerName"],
                software=request.form.get("software"))
        # Update license count
        db.execute("UPDATE software SET licensesRemaining=licensesRemaining+1 WHERE id=:id AND software=:software",
                id=session["user_id"],
                software=request.form.get("software"))

        flash("You have successfully removed the %s license." % (request.form.get("software")))

        return redirect("/")


@app.route("/subtractSoftware", methods=["GET", "POST"])
@login_required
def subtractSoftware():
    """Remove software"""
    if request.method == "POST":
        # Delete from software db
        db.execute("DELETE FROM software WHERE id=:id AND software=:software",
                id=session["user_id"],
                software=request.form.get("software"))
        # Delete from licenses db
        db.execute("DELETE FROM licenses WHERE id=:id AND software=:software",
                id=session["user_id"],
                software=request.form.get("software"))

        flash("You have successfully removed %s." % (request.form.get("software")))

        return redirect("/")
    else:
        # Loop over all installed software for user
        selectSoftware = db.execute("SELECT software FROM software WHERE id=:id", id=session["user_id"])

        softwareArr = []

        for element in selectSoftware:
            softwareArr.append(element["software"])

        return render_template("subtractSoftware.html", softwareArr=softwareArr)


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    # Get username from input
    username = request.args.get("username")

    # Check if username has been input
    if len(username) < 1:
        return jsonify(False)

    # Select username from DB
    check_username = db.execute("SELECT username FROM users WHERE username=:username", username=username)

    # Check if username is available
    if len(check_username) == 0:
        return jsonify(True)
    else:
        return jsonify(False)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("You must provide a username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("You must provide a password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username=:username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("Invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Inform user that login was successful
        flash("You are now logged in.")

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("confirmation") == request.form.get("password"):
            return apology("passwords do not match", 400)

        # Create a hash of the user's password
        hash = generate_password_hash(request.form.get("password"))
        new_user = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                            username=request.form.get("username"), hash=hash)

        # Check to see if username already exists
        if not new_user:
            return apology("sorry, this username is already taken.", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username=:username", username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

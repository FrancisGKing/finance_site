import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

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

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    #select stocks and shares from portfolio table
    stocks = db.execute("SELECT stock, sum(shares) AS number FROM portfolio WHERE user_id = :user GROUP BY stock ORDER BY stock",
    user=session["user_id"])

    #select cash for users table
    cashrow = db.execute("SELECT cash FROM users WHERE id = :user", user=session["user_id"])
    cash = int(cashrow[0]["cash"])

    totalval = 0


    #loop through rows array, retrieving stock and current price
    for stock in stocks:

        price = lookup(stock["stock"])
        stockprice = price["price"]
        stock["price"] = stockprice

        total = price["price"] * stock["number"]
        stock["total"] = total

        #add total to totalval
        totalval += total

    totalval += cash


    return render_template("index.html", stocks=stocks, cash=cash, totalval=totalval)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        stock = lookup(request.form.get("stock"))

        #ensure valid input
        if stock == None:
            return apology("Please input a valid stock")

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Please input in a valid number of shares")

        if shares < 1:
            return apology("Please input a valid number of shares")


        rows = db.execute("SELECT cash FROM users WHERE id = :user", user=session["user_id"])
        money = rows[0]["cash"]
        sprice = stock["price"]
        total = shares * sprice

        #check if user has enough money in account
        if money > total:

            db.execute("INSERT INTO 'portfolio' (user_id, stock, shares, price) VALUES(:user,:stock, :shares, :sprice)",
            user=session["user_id"], stock=request.form.get("stock"), shares=shares, sprice=sprice)

            db.execute("UPDATE users SET cash = :cash WHERE id = :user", cash=(money-total), user=session["user_id"])

            # Redirect user to home page
            return redirect("/")

        #if not enough money, apologize
        else:
            return apology("Not Enough Funds")

    #user reached via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    transactions = db.execute("SELECT stock, shares, price, date FROM portfolio WHERE user_id = :user", user=session["user_id"])

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    #user reached route via POST
    if request.method == "POST":

        #ensure quote was submitted
        if not request.form.get("quote"):
            return apology("Must input a stock")

        elif lookup(request.form.get("quote")) == None:
            return apology("Must input a valid stock")

        else:
            price = lookup(request.form.get("quote"))
            quote = price.get("price")
            name  = request.form.get("quote")
            return render_template("quoted.html", name=name, quote=quote)

    #user reached route via GET
    else:
        return render_template("quote.html")




@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    #user reached route via POST
    if request.method == "POST":

        #ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        #ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        #ensure password was confirmed
        elif not request.form.get("confirmpass"):
            return apology("must confirm password", 403)

        #ensure passwords match
        elif request.form.get("confirmpass") != request.form.get("password"):
            return apology("passwords must match", 403)

        else:
            phash = generate_password_hash(request.form.get("password"))

            db.execute("INSERT INTO users (username, hash) VALUES(:username, :phash)", username=request.form.get("username"), phash=phash)

            # Query database for username
            row = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
            session["user_id"] = row[0]["id"]

            #redirect user to homepage
            return redirect("/")

    #user reached route via GET
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        stock = lookup(request.form.get("stock"))

        if stock == None:
            return apology("Invalid Stock")

        try:
            shares = int(request.form.get("shares"))

        except:
            return apology("Must be a number")

        if shares <= 0:
            return apology("Must be a positive number")

        available_shares = db.execute("SELECT SUM(shares) AS total_shares FROM portfolio WHERE user_id = :user and stock = :stock GROUP BY stock",
        user=session["user_id"], stock=request.form.get("stock"))

        if shares > available_shares[0]["total_shares"] or available_shares[0]["total_shares"] < 1:
            return apology("Not Enough Shares")


        share_price = stock["price"]

        total_price = shares * share_price

        db.execute("UPDATE users set cash = cash + :total_price WHERE id = :user", user=session["user_id"], total_price=total_price)


        #Multiply shares by -1 to substract shares from user portfolio
        db.execute("INSERT INTO 'portfolio' (user_id, stock, shares, price) VALUES(:user, :stock, :shares, :price)", user=session["user_id"],
        stock=request.form.get("stock"), shares=(shares * -1), price=share_price)



        return redirect("/")

    #user reached route via GET
    else:
        available_stocks = db.execute("SELECT stock, SUM(shares) AS total_shares FROM portfolio WHERE user_id = :user GROUP BY stock",
        user=session["user_id"])
        return render_template("sell.html", available_stocks=available_stocks)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

if __name__ == '__main__':
 app.debug = True
 port = int(os.environ.get("localhost", 3000))
 app.run(host='0.0.0.0', port=port)

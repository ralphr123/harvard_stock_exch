from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from helpers import *
import time
import datetime
import csv
import os
import urllib.request
from flask.exthook import ExtDeprecationWarning
from warnings import simplefilter
simplefilter("ignore", ExtDeprecationWarning)
import psycopg2

def buylookup(x):
    """Look up quote for symbol."""

    # reject symbol if it starts with caret
    if x.startswith("^"):
        return None

    # reject symbol if it contains comma
    if "," in x:
        return None

    # query Yahoo for quote
    # http://stackoverflow.com/a/21351911
    try:
        url = "http://download.finance.yahoo.com/d/quotes.csv?f=snl1&s={}".format(x)
        webpage = urllib.request.urlopen(url)
        datareader = csv.reader(webpage.read().decode("utf-8").splitlines())
        row = next(datareader)
    except:
        return None

    # ensure stock exists
    try:
        price = float(row[2])
    except:
        return None
    
    def types():
        try: 
            return int(request.form.get("buyshares"))
        except:
            return int(request.form.get("shares"))
        else:
            return 2
            
                
    types = types()
    # return stock"s name (as a str), price (as a float), and (uppercased) symbol (as a str)
    stockinfo = {
        "name": row[1],
        "price": price,
        "symbol": row[0].upper(),
        "shares": types,
        
    }
    stockinfo["total"] = stockinfo["price"]*stockinfo["shares"]
    stockinfo["cash"] = 10000 - stockinfo["total"]
    return stockinfo
    


# configure application
app = Flask(__name__)

# ensure responses aren"t cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL(os.environ.get("DATABASE_URL") or "sqlite:///finance.db") 


@app.route("/")
@login_required
def index():
    balance = db.execute("SELECT balance FROM users WHERE id=:id", id = session["user_id"])[0]["balance"]
    symbol1 = db.execute("SELECT * FROM stocks WHERE userid = :id", id = session["user_id"])
    newbalance = float(balance)
    for stock in symbol1:
        stock["total"] = usd(stock["total"])
        balance = usd(newbalance)
    return render_template("index.html", mainbalance=balance, symbol = symbol1)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    elif request.method == "POST":
        shares = request.form.get("buyshares")
        x = request.form.get("buysymbol")
        if not request.form.get("buysymbol"):
            return apology("must provide code")
        buystock = buylookup(x)
        if not buystock:
             return apology("invalid symbol")
        elif not shares.isdigit():
            return apology("invalid shares")
        else:
            already = db.execute("SELECT * FROM stocks WHERE symbol = :used AND userid=:id", used = request.form.get("buysymbol"), id = session["user_id"])
            stockinfo = buylookup(x)
            if len(already) == 1:
                newb = (db.execute("SELECT balance FROM users WHERE id=:id", id = session["user_id"])[0]["balance"])
                if stockinfo["total"] <= newb:
                    newb = (db.execute("SELECT balance FROM users WHERE id=:id", id = session["user_id"])[0]["balance"])
                    newb1 = usd(float(newb))
                    stockinfo = buylookup(x)
                    db.execute("UPDATE stocks SET sharesbought = sharesbought + :newbought WHERE symbol = :symbol and userid = :id", 
                    newbought = request.form.get("buyshares"), symbol = request.form.get("buysymbol"), id = session["user_id"])
                    db.execute("UPDATE stocks SET total = total + :newtotal WHERE symbol = :symbol and userid = :id", 
                    newtotal = stockinfo["total"], symbol = request.form.get("buysymbol"), id = session["user_id"])
                    date = datetime.datetime.now().strftime("%y-%m-%d-%H-%M")
                    db.execute("UPDATE users SET balance = balance - :cost WHERE id = :id", 
                    cost = stockinfo["total"], id = session["user_id"])
                    db.execute("INSERT INTO history (symbol, sharesbought, date, userid) VALUES(:symbol, :sharesbought, :date, :userid)", 
                    symbol=x, sharesbought=shares, date = date, userid=session["user_id"])
                    newb1 = usd(float(newb))
                    return render_template("bought.html", name=stockinfo["name"], price=stockinfo["price"], symbol=stockinfo["symbol"], 
                    shares=stockinfo["shares"], total=stockinfo["total"], cash=stockinfo["cash"], balance=newb1)
                else:
                    return apology("not enough money")
            else:
                newb = db.execute("SELECT balance FROM users WHERE id=:id", id = session["user_id"])[0]["balance"]
                stockinfo = buylookup(x)
                if stockinfo["total"] <= newb:
                    newb = db.execute("SELECT balance FROM users WHERE id=:id", id = session["user_id"])[0]["balance"]
                    newb1 = usd(float(newb))
                    stockinfo = buylookup(x)
                    db.execute("INSERT INTO stocks (symbol, sharesbought, userid, total) VALUES(:symbol, :sharesbought, :userid, :stocktotal)", 
                    symbol=x, sharesbought=shares, userid=session["user_id"], stocktotal= stockinfo["total"])
                    db.execute("UPDATE users SET balance = balance - :total WHERE id=:id", total=stockinfo["total"], id = session["user_id"])
                    return render_template("bought.html", name=stockinfo["name"], price=stockinfo["price"], symbol=stockinfo["symbol"], 
                    shares=stockinfo["shares"], total=stockinfo["total"], cash=stockinfo["cash"], balance=newb1)
                else:
                    return apology("not enough money")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["password"]): 
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))



@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")

@app.route("/ajax")
def ajax():
        url = "http://download.finance.yahoo.com/d/quotes.csv?f=snl1&s={}".format(request.args.get("symbol"))
        webpage = urllib.request.urlopen(url)
        datareader = csv.reader(webpage.read().decode("utf-8").splitlines())
        row = next(datareader)
        return jsonify({"name": row[1], "price": float(row[2]), "symbol": row[0].upper()})


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not request.form.get("name"):
            return apology("must provide name")

        elif not request.form.get("password"):
            return apology("must provide password")
        
        elif not request.form.get("username"):
            return apology("must provide username")

        elif not request.form.get("password"):
            return apology("must provide password")
        
        elif request.form.get("password") != request.form.get("password1"):
            return apology("Passwords are not identical")
        
        else:
            print(request.form)
            result = db.execute("INSERT INTO users (name, username, password) VALUES(:name, :username, :password)", name=request.form["name"], 
            username=request.form["username"], password=pwd_context.hash(request.form["password"]))
            if not result:
                return apology("Username taken")
            return redirect(url_for("login"))
        
    else:
        return render_template("register.html")
         

    
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        return render_template("sell.html")
    elif request.method == "POST":
        shares = request.form.get("shares")
        x = request.form.get("symbol")
        if not request.form.get("symbol"):
            return apology("must provide code")
        if not buylookup(x):
             return apology("invalid code")
        elif not shares.isdigit():
            return apology("invalid shares")
        else:
            already = db.execute("SELECT * FROM stocks WHERE symbol = :used AND userid=:id", used = request.form.get("symbol"), id = session["user_id"])
            checkbought = db.execute("SELECT sharesbought FROM stocks WHERE symbol = :symbol and userid = :id", symbol = request.form.get("symbol"), id = session["user_id"])
            
            if len(already) == 1:
                if checkbought[0]["sharesbought"] < int(request.form.get("shares")):
                    return apology("no available shares")
                else:
                    xa = request.form.get("symbol")
                    shares = ("-" + request.form.get("shares"))
                    date = datetime.datetime.now().strftime("%y-%m-%d-%H-%M")
                    stockinfo = buylookup(x)
                    newb = db.execute("SELECT balance FROM users WHERE id=:id", id = session["user_id"])[0]["balance"]
                    newb1 = usd(float(newb))
                    db.execute("UPDATE stocks SET sharesbought = sharesbought - :newbought WHERE symbol = :symbol and userid = :id", 
                    newbought = request.form.get("shares"), symbol = request.form.get("symbol"), id = session["user_id"])
                    db.execute("UPDATE stocks SET total = total - :total WHERE symbol = :symbol and userid = :id", 
                    total = stockinfo["total"], symbol = request.form.get("symbol"), id = session["user_id"])
                    db.execute("INSERT INTO history (symbol, sharesbought, date, userid) VALUES(:symbol, :sharesbought, :date, :userid)", 
                    symbol=xa, sharesbought=shares, date = date, userid=session["user_id"])
                    db.execute("UPDATE users SET balance = balance + :total WHERE id=:id", total=stockinfo["total"], id = session["user_id"])
                    return render_template("bought.html", name=stockinfo["name"], price=stockinfo["price"], symbol=stockinfo["symbol"], 
                    shares=stockinfo["shares"], total=stockinfo["total"], cash=stockinfo["cash"], balance=newb1)
            else:
                return apology("no available shares")
            

@app.route("/history")
@login_required
def history():
    already = db.execute("SELECT * FROM history WHERE userid=:id", id = session["user_id"])
    if len(already) >= 1:
        symbol2 = db.execute("SELECT * FROM history WHERE userid = :id", id = session["user_id"])
        return render_template("history.html", symbol = symbol2)
    else:
        return apology("No history available")
        

if __name == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
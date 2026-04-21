from flask import Flask, render_template, redirect, url_for, request, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import flash
import pandas as pd
import pytz
import os

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# ------------------ DATABASE ------------------

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ✅ REMOVE DEFAULT LOGIN MESSAGE
login_manager.login_message = None


# ✅ ADD THIS BLOCK (VERY IMPORTANT)
@app.before_request
def force_password_change():

    if not current_user.is_authenticated:
        return

    allowed_routes = ['change_password', 'logout', 'login', 'static']

    if request.endpoint in allowed_routes:
        return

    if hasattr(current_user, 'must_change_password') and current_user.must_change_password:
        return redirect(url_for('change_password'))


# ------------------ TIMEZONE ------------------

def get_ist_date():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist).date()


# ------------------ MODELS ------------------

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(50))
    must_change_password = db.Column(db.Boolean, default=True)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    suggested_time = db.Column(db.String(50))


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    date = db.Column(db.String(50))


class ReportTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer)
    task_id = db.Column(db.Integer)
    actual_time = db.Column(db.String(50))
    notes = db.Column(db.String(500))


# ------------------ LOGIN ------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':

        user = User.query.filter_by(
            username=request.form['username']
        ).first()

        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)

            if user.must_change_password:
                return redirect(url_for('change_password'))

            return redirect(url_for('dashboard'))

        else:
            error = "Invalid username or password"

    return render_template('login.html', error=error)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

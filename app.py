# =============================================================
#  app.py  –  Employee Dashboard (Flask)
#  Roles: manager > senior > employee
# =============================================================

from flask import (Flask, render_template, redirect, url_for,
                   request, send_file, flash)
from flask_login import (LoginManager, UserMixin,
                         login_user, login_required,
                         logout_user, current_user)
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import pytz
import os

# ------------------------------------------------------------------
# APP & CONFIG
# ------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-before-production")

db_url = os.environ.get("DATABASE_URL", "sqlite:///database.db")
# Heroku gives postgres:// but SQLAlchemy needs postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = None

# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------
def get_ist_now():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

def get_ist_date():
    return str(get_ist_now().date())

def deny_unless(*roles):
    """Return a redirect if current_user lacks one of the given roles, else None."""
    if current_user.role not in roles:
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    return None

# ------------------------------------------------------------------
# MODELS
# ------------------------------------------------------------------
class User(db.Model, UserMixin):
    id                  = db.Column(db.Integer, primary_key=True)
    username            = db.Column(db.String(100), unique=True, nullable=False)
    password            = db.Column(db.String(200), nullable=False)
    role                = db.Column(db.String(50),  nullable=False, default="employee")
    must_change_password = db.Column(db.Boolean, default=True)

class Task(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(200), nullable=False)
    suggested_time = db.Column(db.String(50))

class Client(db.Model):
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)

class Region(db.Model):
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)

class Report(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date    = db.Column(db.String(50), nullable=False)
    user    = db.relationship("User", backref="reports")

class ReportTask(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    report_id   = db.Column(db.Integer, db.ForeignKey("report.id"),  nullable=False)
    task_id     = db.Column(db.Integer, db.ForeignKey("task.id"),    nullable=False)
    actual_time = db.Column(db.String(50))
    notes       = db.Column(db.String(500))
    client_id   = db.Column(db.Integer, db.ForeignKey("client.id"),  nullable=True)
    region_id   = db.Column(db.Integer, db.ForeignKey("region.id"),  nullable=True)
    task        = db.relationship("Task")
    client      = db.relationship("Client")
    region      = db.relationship("Region")

# ------------------------------------------------------------------
# HOOKS
# ------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.before_request
def force_password_change():
    if not current_user.is_authenticated:
        return
    exempt = {"change_password", "logout", "login", "static", "reset_password"}
    if not request.endpoint or request.endpoint in exempt:
        return
    if current_user.must_change_password:
        return redirect(url_for("change_password"))

# ------------------------------------------------------------------
# AUTH
# ------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"].strip()).first()
        if user and check_password_hash(user.password, request.form["password"]):
            login_user(user)
            return redirect(
                url_for("change_password") if user.must_change_password
                else url_for("dashboard")
            )
        error = "Invalid username or password."
    return render_template("login.html", error=error)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    error = None
    if request.method == "POST":
        cur  = request.form.get("current_password", "")
        new  = request.form.get("new_password", "")
        conf = request.form.get("confirm_password", "")
        if not check_password_hash(current_user.password, cur):
            error = "Current password is incorrect."
        elif len(new) < 6:
            error = "New password must be at least 6 characters."
        elif new != conf:
            error = "Passwords do not match."
        else:
            current_user.password = generate_password_hash(new)
            current_user.must_change_password = False
            db.session.commit()
            flash("Password updated successfully!", "success")
            return redirect(url_for("dashboard"))
    return render_template("change_password.html", error=error)

@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    error = success = None
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"].strip()).first()
        if not user:
            error = "Username not found."
        else:
            user.password = generate_password_hash("temp123")
            user.must_change_password = True
            db.session.commit()
            success = "Password reset to 'temp123'. Please log in and change it immediately."
    return render_template("reset_password.html", error=error, success=success)

@app.route("/fix_passwords_secure")
@login_required
def fix_passwords_secure():

    # Only manager can run this
    if current_user.role != "manager":
        return "Access denied"

    users = User.query.all()

    fixed_count = 0

    for u in users:
        # If already hashed, skip
        if not u.password.startswith("pbkdf2"):
            u.password = generate_password_hash(u.password)
            fixed_count += 1

    db.session.commit()

    return f"Fixed {fixed_count} users"

# ------------------------------------------------------------------
# DASHBOARD
# ------------------------------------------------------------------
@app.route("/")
@login_required
def dashboard():
    now   = get_ist_now()
    today = str(now.date())
    submitted_today = Report.query.filter_by(
        user_id=current_user.id, date=today
    ).first() is not None
    return render_template("dashboard.html",
                           today=today,
                           now_hour=now.hour,
                           submitted_today=submitted_today)

# ------------------------------------------------------------------
# SUBMIT REPORT
# ------------------------------------------------------------------
@app.route("/submit_report", methods=["GET", "POST"])
@login_required
def submit_report():
    today           = get_ist_date()
    existing_report = Report.query.filter_by(user_id=current_user.id, date=today).first()

    if request.method == "POST":
        task_ids    = request.form.getlist("task")
        times       = request.form.getlist("time")
        notes_list  = request.form.getlist("notes")
        client_ids  = request.form.getlist("client")
        region_ids  = request.form.getlist("region")

        if existing_report:
            ReportTask.query.filter_by(report_id=existing_report.id).delete()
            report = existing_report
        else:
            report = Report(user_id=current_user.id, date=today)
            db.session.add(report)
            db.session.flush()          # get report.id before bulk insert

        for i in range(len(task_ids)):
            if task_ids[i] and (i < len(times)) and times[i]:
                db.session.add(ReportTask(
                    report_id   = report.id,
                    task_id     = task_ids[i],
                    actual_time = times[i],
                    notes       = notes_list[i] if i < len(notes_list) else "",
                    client_id   = (client_ids[i] or None) if i < len(client_ids) else None,
                    region_id   = (region_ids[i] or None) if i < len(region_ids) else None,
                ))

        db.session.commit()
        action = "updated" if existing_report else "submitted"
        flash(f"Report {action} successfully!", "success")
        return redirect(url_for("dashboard"))

    tasks          = Task.query.order_by(Task.name).all()
    existing_tasks = (ReportTask.query.filter_by(report_id=existing_report.id).all()
                      if existing_report else [])
    clients        = Client.query.order_by(Client.name).all()
    regions        = Region.query.order_by(Region.name).all()

    return render_template("submit_report.html",
                           tasks=tasks,
                           existing_tasks=existing_tasks,
                           clients=clients,
                           regions=regions,
                           today=today,
                           is_edit=bool(existing_report))

# ------------------------------------------------------------------
# MY REPORTS
# ------------------------------------------------------------------
@app.route("/my_reports")
@login_required
def my_reports():
    today   = get_ist_date()
    reports = (Report.query
               .filter_by(user_id=current_user.id)
               .order_by(Report.date.desc())
               .all())
    return render_template("my_reports.html", reports=reports, today=today)

# ------------------------------------------------------------------
# ALL REPORTS  (manager / senior only)
# ------------------------------------------------------------------
@app.route("/all_reports")
@login_required
def all_reports():
    denied = deny_unless("manager", "senior")
    if denied:
        return denied

    selected_user = request.args.get("user_id", "").strip()
    selected_date = request.args.get("date", "").strip()

    query = Report.query
    if selected_user:
        query = query.filter_by(user_id=selected_user)
    if selected_date:
        query = query.filter(Report.date == selected_date)

    reports = query.order_by(Report.date.desc()).all()
    users   = User.query.order_by(User.username).all()

    return render_template("all_reports.html",
                           reports=reports, users=users,
                           selected_user=selected_user,
                           selected_date=selected_date)

# ------------------------------------------------------------------
# REPORT DETAILS
# ------------------------------------------------------------------
@app.route("/report/<int:report_id>")
@login_required
def report_details(report_id):
    report = Report.query.get_or_404(report_id)
    if (current_user.role not in ["manager", "senior"]
            and report.user_id != current_user.id):
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    user         = db.session.get(User, report.user_id)
    report_tasks = ReportTask.query.filter_by(report_id=report.id).all()

    detailed_tasks = []
    for rt in report_tasks:
        task = db.session.get(Task, rt.task_id)
        if task:
            detailed_tasks.append({
                "name":   task.name,
                "time":   rt.actual_time or "—",
                "notes":  rt.notes       or "—",
                "client": rt.client.name if rt.client else "—",
                "region": rt.region.name if rt.region else "—",
            })

    today    = get_ist_date()
    can_edit = (report.date == today and report.user_id == current_user.id)

    return render_template("report_details.html",
                           report=report, user=user,
                           tasks=detailed_tasks, can_edit=can_edit)

# ------------------------------------------------------------------
# ADMIN PANEL
# ------------------------------------------------------------------
@app.route("/admin")
@login_required
def admin():
    denied = deny_unless("manager", "senior")
    if denied:
        return denied
    return render_template("admin.html",
                           users   = User.query.order_by(User.username).all(),
                           clients = Client.query.order_by(Client.name).all(),
                           regions = Region.query.order_by(Region.name).all(),
                           tasks   = Task.query.order_by(Task.name).all())

# ---- User management ----
@app.route("/add_user", methods=["POST"])
@login_required
def add_user():
    denied = deny_unless("manager", "senior")
    if denied:
        return denied
    username = request.form["username"].strip()
    if User.query.filter_by(username=username).first():
        flash("Username already exists.", "danger")
    else:
        db.session.add(User(
            username=username,
            password=generate_password_hash(request.form["password"]),
            role=request.form["role"],
            must_change_password=True,
        ))
        db.session.commit()
        flash(f"User '{username}' added.", "success")
    return redirect(url_for("admin"))

@app.route("/delete_user/<int:user_id>")
@login_required
def delete_user(user_id):
    denied = deny_unless("manager", "senior")
    if denied:
        return denied
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "warning")
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f"User '{user.username}' deleted.", "success")
    return redirect(url_for("admin"))

@app.route("/reset_user_password/<int:user_id>")
@login_required
def reset_user_password(user_id):
    denied = deny_unless("manager", "senior")
    if denied:
        return denied
    user = User.query.get_or_404(user_id)
    user.password = generate_password_hash("temp123")
    user.must_change_password = True
    db.session.commit()
    flash(f"Password for '{user.username}' reset to temp123.", "warning")
    return redirect(url_for("admin"))

# ---- Data management (manager only) ----
@app.route("/add_task", methods=["POST"])
@login_required
def add_task():
    denied = deny_unless("manager")
    if denied:
        return denied
    name = request.form.get("name", "").strip()
    if name:
        db.session.add(Task(name=name,
                            suggested_time=request.form.get("suggested_time", "").strip()))
        db.session.commit()
        flash("Task added.", "success")
    return redirect(url_for("admin"))

@app.route("/delete_task/<int:id>")
@login_required
def delete_task(id):
    denied = deny_unless("manager")
    if denied:
        return denied
    task = Task.query.get_or_404(id)
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "success")
    return redirect(url_for("admin"))

@app.route("/add_client", methods=["POST"])
@login_required
def add_client():
    denied = deny_unless("manager")
    if denied:
        return denied
    name = request.form.get("name", "").strip()
    if name:
        db.session.add(Client(name=name))
        db.session.commit()
        flash("Client added.", "success")
    return redirect(url_for("admin"))

@app.route("/delete_client/<int:id>")
@login_required
def delete_client(id):
    denied = deny_unless("manager")
    if denied:
        return denied
    client = Client.query.get_or_404(id)
    db.session.delete(client)
    db.session.commit()
    flash("Client deleted.", "success")
    return redirect(url_for("admin"))

@app.route("/add_region", methods=["POST"])
@login_required
def add_region():
    denied = deny_unless("manager")
    if denied:
        return denied
    name = request.form.get("name", "").strip()
    if name:
        db.session.add(Region(name=name))
        db.session.commit()
        flash("Region added.", "success")
    return redirect(url_for("admin"))

@app.route("/delete_region/<int:id>")
@login_required
def delete_region(id):
    denied = deny_unless("manager")
    if denied:
        return denied
    region = Region.query.get_or_404(id)
    db.session.delete(region)
    db.session.commit()
    flash("Region deleted.", "success")
    return redirect(url_for("admin"))

# ------------------------------------------------------------------
# EXPORT
# ------------------------------------------------------------------
@app.route("/export")
@login_required
def export_excel():
    denied = deny_unless("manager", "senior")
    if denied:
        return denied

    sel_user = request.args.get("user_id", "").strip()
    sel_date = request.args.get("date", "").strip()

    query = Report.query
    if sel_user:
        query = query.filter_by(user_id=sel_user)
    if sel_date:
        query = query.filter(Report.date == sel_date)

    data = []
    for report in query.all():
        user = db.session.get(User, report.user_id)
        for rt in ReportTask.query.filter_by(report_id=report.id).all():
            task   = db.session.get(Task,   rt.task_id)
            client = db.session.get(Client, rt.client_id) if rt.client_id else None
            region = db.session.get(Region, rt.region_id) if rt.region_id else None
            if task:
                data.append({
                    "Employee": user.username if user else "Unknown",
                    "Date":     report.date,
                    "Task":     task.name,
                    "Time":     rt.actual_time or "",
                    "Notes":    rt.notes       or "",
                    "Client":   client.name    if client else "",
                    "Region":   region.name    if region else "",
                })

    df        = pd.DataFrame(data)
    file_path = "/tmp/report_export.xlsx"
    df.to_excel(file_path, index=False)
    return send_file(file_path, as_attachment=True, download_name="report_export.xlsx")

# ------------------------------------------------------------------
# INIT DB
# ------------------------------------------------------------------
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=False)

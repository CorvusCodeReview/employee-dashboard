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

login_manager.login_message = None


@app.before_request
def force_password_change():

    # if user not logged in → allow
    if not current_user.is_authenticated:
        return

    # allowed routes
    allowed_routes = ['change_password', 'logout', 'login', 'static']

    # ✅ FIX: handle None endpoint safely
    if not request.endpoint or request.endpoint in allowed_routes:
        return

    # enforce password change
    if current_user.must_change_password:
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

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))

class Region(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))


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
    client_id = db.Column(db.Integer)
    region_id = db.Column(db.Integer)

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


@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():

    if request.method == 'POST':

        current_password = request.form['current_password']
        new_password = request.form['new_password']

        if not check_password_hash(current_user.password, current_password):
            return render_template('change_password.html', error="Current password incorrect")

        current_user.password = generate_password_hash(new_password)
        current_user.must_change_password = False

        db.session.commit()

        flash("Password updated successfully!", "success")
        return redirect(url_for('dashboard'))

    return render_template('change_password.html')


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():

    error = None

    if request.method == 'POST':
        username = request.form['username']
        user = User.query.filter_by(username=username).first()

        if not user:
            error = "User not found"
        else:
            user.password = generate_password_hash("temp123")
            user.must_change_password = True
            db.session.commit()
            return "Password reset to temp123. Please login and change password."

    return render_template('reset_password.html', error=error)


# ------------------ SUBMIT REPORT ------------------

@app.route('/submit_report', methods=['GET', 'POST'])
@login_required
def submit_report():

    today = str(get_ist_date())

    existing_report = Report.query.filter_by(user_id=current_user.id, date=today).first()

    if request.method == 'POST':

        task_ids = request.form.getlist('task')
        times = request.form.getlist('time')
        notes_list = request.form.getlist('notes')
        client_ids = request.form.getlist('client')
        region_ids = request.form.getlist('region')

        if existing_report:
            ReportTask.query.filter_by(report_id=existing_report.id).delete()

            for i in range(len(task_ids)):
                if task_ids[i] and times[i]:
                    db.session.add(ReportTask(
                        report_id=existing_report.id,
                        task_id=task_ids[i],
                        actual_time=times[i],
                        notes=notes_list[i],
                        client_id=client_ids[i] if i < len(client_ids) else None,
                        region_id=region_ids[i] if i < len(region_ids) else None
                    ))

            db.session.commit()
            flash("Report updated successfully!", "success")
            return redirect(url_for('dashboard'))

        else:
            report = Report(user_id=current_user.id, date=today)
            db.session.add(report)
            db.session.commit()

            for i in range(len(task_ids)):
                if task_ids[i] and times[i]:
                    db.session.add(ReportTask(
                        report_id=report.id,
                        task_id=task_ids[i],
                        actual_time=times[i],
                        notes=notes_list[i]
                    ))

            db.session.commit()
            flash("Report submitted successfully!", "success")
            return redirect(url_for('dashboard'))

    tasks = Task.query.all()
    existing_tasks = ReportTask.query.filter_by(report_id=existing_report.id).all() if existing_report else []

    clients = Client.query.all()
    regions = Region.query.all()

    return render_template(
        'submit_report.html',
        tasks=tasks,
        existing_tasks=existing_tasks,
        clients=clients,
        regions=regions
    )


# ------------------ MY REPORTS ------------------

@app.route('/my_reports')
@login_required
def my_reports():
    reports = Report.query.filter_by(user_id=current_user.id).all()
    today = str(get_ist_date())
    return render_template('my_reports.html', reports=reports, today=today)


# ------------------ ALL REPORTS ------------------

@app.route('/all_reports')
@login_required
def all_reports():

    if current_user.role not in ['manager', 'senior']:
        flash("Access Denied", "danger") 
        return redirect(url_for('dashboard'))

    selected_user = request.args.get('user_id')
    selected_date = request.args.get('date')

    query = Report.query

    if selected_user:
        query = query.filter_by(user_id=selected_user)

    if selected_date:
        query = query.filter(Report.date.like(f"%{selected_date}%"))

    reports = query.all()
    users = User.query.all()

    return render_template('all_reports.html', reports=reports, users=users, selected_user=selected_user, selected_date=selected_date)

# ------------------ REPORT DETAILS ------------------

@app.route('/report/<int:report_id>')
@login_required
def report_details(report_id):

    report = Report.query.get_or_404(report_id)

    # 🔒 Access control
    if current_user.role not in ['manager', 'senior'] and report.user_id != current_user.id:
        flash("Access Denied", "danger") 
        return redirect(url_for('dashboard'))

    tasks = ReportTask.query.filter_by(report_id=report.id).all()
    user = User.query.get(report.user_id)

    detailed_tasks = []

    for t in tasks:
        task = Task.query.get(t.task_id)

        if task:
            detailed_tasks.append({
                "name": task.name,
                "time": t.actual_time,
                "notes": t.notes
            })

    return render_template(
        'report_details.html',
        report=report,
        user=user,
        tasks=detailed_tasks
    )

# ------------------ MANAGE TASKS ------------------

@app.route('/manage_tasks', methods=['GET', 'POST'])
@login_required
def manage_tasks():

    # Only manager can add tasks
    if current_user.role != 'manager':
        tasks = Task.query.all()
        return render_template('manage_tasks.html', tasks=tasks)

    if request.method == 'POST':
        name = request.form['name']
        suggested_time = request.form['suggested_time']

        if name and suggested_time:
            db.session.add(Task(name=name, suggested_time=suggested_time))
            db.session.commit()
            flash("Task added successfully!", "success")
            return redirect(url_for('manage_tasks'))

    tasks = Task.query.all()
    return render_template('manage_tasks.html', tasks=tasks)

# ------------------ ADMIN PANEL ------------------

@app.route('/admin')
@login_required
def admin():

    if current_user.role not in ['manager', 'senior']:
        flash("Access Denied", "danger")
        return redirect(url_for('dashboard'))

    users = User.query.all()
    clients = Client.query.all()
    regions = Region.query.all()
    tasks = Task.query.all()

    return render_template(
        'admin.html',
        users=users,
        clients=clients,
        regions=regions,
        tasks=tasks
    )


@app.route('/add_user', methods=['POST'])
@login_required
def add_user():

    if current_user.role not in ['manager', 'senior']:
        flash("Access Denied", "danger")
        return redirect(url_for('dashboard'))

    username = request.form['username']
    password = generate_password_hash(request.form['password'])
    role = request.form['role']

    # prevent duplicate usernames
    existing = User.query.filter_by(username=username).first()
    if existing:
        flash("User already exists", "danger")
        return redirect(url_for('admin'))

    new_user = User(
        username=username,
        password=password,
        role=role,
        must_change_password=True
    )

    db.session.add(new_user)
    db.session.commit()

    flash("User added successfully!", "success")
    return redirect(url_for('admin'))


@app.route('/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):

    if current_user.role not in ['manager', 'senior']:
        flash("Access Denied", "danger") 
        return redirect(url_for('dashboard'))

    user = User.query.get(user_id)

    # prevent deleting yourself
    if user.id == current_user.id:
        flash("You cannot delete yourself", "warning")
        return redirect(url_for('admin'))

    db.session.delete(user)
    db.session.commit()

    flash("User deleted", "success")
    return redirect(url_for('admin'))


@app.route('/reset_user_password/<int:user_id>')
@login_required
def reset_user_password(user_id):

    if current_user.role not in ['manager', 'senior']:
        flash("Access Denied", "danger") 
        return redirect(url_for('dashboard'))

    user = User.query.get(user_id)

    user.password = generate_password_hash("temp123")
    user.must_change_password = True

    db.session.commit()

    flash("Password reset to temp123", "warning")
    return redirect(url_for('admin'))

@app.route('/add_client', methods=['POST'])
@login_required
def add_client():
    if current_user.role != 'manager':
        flash("Access Denied", "danger")
        return redirect(url_for('dashboard'))

    name = request.form['name']
    db.session.add(Client(name=name))
    db.session.commit()
    flash("Client added successfully", "success")
    return redirect(url_for('admin'))


@app.route('/add_region', methods=['POST'])
@login_required
def add_region():
    if current_user.role != 'manager':
        flash("Access Denied", "danger")
        return redirect(url_for('dashboard'))

    name = request.form['name']
    db.session.add(Region(name=name))
    db.session.commit()
    flash("Region added successfully", "success")
    return redirect(url_for('admin'))

@app.route('/delete_task/<int:id>')
@login_required
def delete_task(id):
    if current_user.role != 'manager':
        flash("Access Denied", "danger")
        return redirect(url_for('dashboard'))

    task = Task.query.get(id)
    if task:
        db.session.delete(task)
        db.session.commit()
        flash("Task deleted", "success")

    return redirect(url_for('manage_tasks'))


@app.route('/delete_client/<int:id>')
@login_required
def delete_client(id):
    if current_user.role != 'manager':
        flash("Access Denied", "danger")
        return redirect(url_for('dashboard'))

    client = Client.query.get(id)
    if client:
        db.session.delete(client)
        db.session.commit()
        flash("Client deleted", "success")

    return redirect(url_for('admin'))


@app.route('/delete_region/<int:id>')
@login_required
def delete_region(id):
    if current_user.role != 'manager':
        flash("Access Denied", "danger")
        return redirect(url_for('dashboard'))

    region = Region.query.get(id)
    if region:
        db.session.delete(region)
        db.session.commit()
        flash("Region deleted", "success")

    return redirect(url_for('admin'))

# ------------------ EXPORT ------------------

@app.route('/export')
@login_required
def export_excel():

    if current_user.role not in ['manager', 'senior']:
        flash("Access Denied", "danger")
        return redirect(url_for('dashboard'))

    reports = Report.query.all()
    data = []

    for report in reports:
        user = User.query.get(report.user_id)
        tasks = ReportTask.query.filter_by(report_id=report.id).all()

        for t in tasks:
            task_name = Task.query.get(t.task_id).name
            data.append({"Employee": user.username, "Date": report.date, "Task": task_name, "Time": t.actual_time, "Notes": t.notes})

    df = pd.DataFrame(data)
    file_path = "report.xlsx"
    df.to_excel(file_path, index=False)

    flash("Excel exported successfully!", "success")

    return send_file(file_path, as_attachment=True)


# ------------------ INIT ------------------

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run()

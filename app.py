from flask import Flask, render_template, redirect, url_for, request, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from datetime import date
import pandas as pd

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# ------------------ MODELS ------------------

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(50))


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
    if request.method == 'POST':
        user = User.query.filter_by(
            username=request.form['username'],
            password=request.form['password']
        ).first()

        if user:
            login_user(user)
            return redirect(url_for('dashboard'))

        return "Invalid credentials"

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ------------------ SUBMIT REPORT ------------------

@app.route('/submit_report', methods=['GET', 'POST'])
@login_required
def submit_report():

    today = str(date.today())
    existing_report = Report.query.filter_by(user_id=current_user.id, date=today).first()

    if request.method == 'POST':
        task_ids = request.form.getlist('task')
        times = request.form.getlist('time')
        notes_list = request.form.getlist('notes')

        # ✅ Basic validation
        if not task_ids or not times:
            return "Please fill all required fields"

        if existing_report:
            ReportTask.query.filter_by(report_id=existing_report.id).delete()

            for i in range(len(task_ids)):
                if not times[i]:
                    continue

                db.session.add(ReportTask(
                    report_id=existing_report.id,
                    task_id=task_ids[i],
                    actual_time=times[i],
                    notes=notes_list[i]
                ))

            db.session.commit()
            return "Report updated successfully!"

        else:
            report = Report(user_id=current_user.id, date=today)
            db.session.add(report)
            db.session.commit()

            for i in range(len(task_ids)):
                if not times[i]:
                    continue

                db.session.add(ReportTask(
                    report_id=report.id,
                    task_id=task_ids[i],
                    actual_time=times[i],
                    notes=notes_list[i]
                ))

            db.session.commit()
            return "Report submitted successfully!"

    tasks = Task.query.all()

    existing_tasks = []
    if existing_report:
        existing_tasks = ReportTask.query.filter_by(report_id=existing_report.id).all()

    return render_template('submit_report.html', tasks=tasks, existing_tasks=existing_tasks)


# ------------------ MY REPORTS ------------------

@app.route('/my_reports')
@login_required
def my_reports():
    reports = Report.query.filter_by(user_id=current_user.id).all()
    return render_template('my_reports.html', reports=reports)


# ------------------ ALL REPORTS ------------------

@app.route('/all_reports')
@login_required
def all_reports():

    if current_user.role not in ['manager', 'senior']:
        return "Access Denied"

    selected_user = request.args.get('user_id')
    selected_date = request.args.get('date')

    query = Report.query

    if selected_user:
        query = query.filter_by(user_id=selected_user)

    if selected_date:
        query = query.filter_by(date=selected_date)

    reports = query.all()
    users = User.query.all()

    return render_template(
        'all_reports.html',
        reports=reports,
        users=users,
        selected_user=selected_user,
        selected_date=selected_date
    )


# ------------------ REPORT DETAILS ------------------

@app.route('/report/<int:report_id>')
@login_required
def report_details(report_id):

    report = Report.query.get(report_id)

    tasks = ReportTask.query.filter_by(report_id=report.id).all()
    task_names = {task.id: task.name for task in Task.query.all()}
    user = User.query.get(report.user_id)

    return render_template(
        'report_details.html',
        report=report,
        tasks=tasks,
        task_names=task_names,
        user=user
    )


# ------------------ MANAGE TASKS ------------------

@app.route('/manage_tasks', methods=['GET', 'POST'])
@login_required
def manage_tasks():

    if current_user.role not in ['manager', 'senior']:
        return "Access Denied"

    if request.method == 'POST':
        name = request.form['name']
        time = request.form['time']

        if name and time:
            db.session.add(Task(name=name, suggested_time=time))
            db.session.commit()

    tasks = Task.query.all()
    return render_template('manage_tasks.html', tasks=tasks)


# ------------------ EXPORT EXCEL ------------------

@app.route('/export')
@login_required
def export_excel():

    if current_user.role not in ['manager', 'senior']:
        return "Access Denied"

    reports = Report.query.all()

    data = []

    for report in reports:
        user = User.query.get(report.user_id)
        tasks = ReportTask.query.filter_by(report_id=report.id).all()

        for t in tasks:
            task_name = Task.query.get(t.task_id).name

            data.append({
                "Employee": user.username,
                "Date": report.date,
                "Task": task_name,
                "Time": t.actual_time,
                "Notes": t.notes
            })

    df = pd.DataFrame(data)
    file_path = "report.xlsx"
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)


# ------------------ INIT DATA ------------------

with app.app_context():
    db.create_all()

    if not User.query.first():
        db.session.add_all([
            User(username="employee1", password="123", role="employee"),
            User(username="senior1", password="123", role="senior"),
            User(username="manager1", password="123", role="manager")
        ])
        db.session.commit()

    if not Task.query.first():
        db.session.add_all([
            Task(name="Prepare Report", suggested_time="1-2 hrs"),
            Task(name="Client Call", suggested_time="30 mins"),
            Task(name="Data Entry", suggested_time="1 hr")
        ])
        db.session.commit()


# ------------------ RUN ------------------

if __name__ == '__main__':
    app.run()


from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///firefighter.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ------------------------ MODELS ------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False)

class EmployeeProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    role = db.Column(db.String(100))
    monthly_salary = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

# ------------------------ ROUTES ------------------------
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'employee':
                return redirect(url_for('employee_dashboard'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    employees = EmployeeProfile.query.all()
    return render_template('admin_dashboard.html', employees=employees)

@app.route('/employee')
def employee_dashboard():
    if session.get('role') != 'employee':
        return redirect(url_for('login'))
    user_id = session.get('user_id')
    profile = EmployeeProfile.query.filter_by(user_id=user_id).first()
    return render_template('employee_dashboard.html', profile=profile)

from flask import flash, redirect

@app.route('/create-profile', methods=['GET', 'POST'])
def create_profile():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        role = 'employee'

        new_user = User(username=username, password=hashed_pw, role=role)
        db.session.add(new_user)
        db.session.commit()

        profile = EmployeeProfile(
            employee_id=request.form['employee_id'],
            name=request.form['name'],
            phone=request.form['phone'],
            address=request.form['address'],
            role=request.form['emp_role'],
            monthly_salary=request.form['salary'],
            user_id=new_user.id
        )
        db.session.add(profile)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    return render_template('create_profile.html')

@app.route('/update-profile', methods=['GET', 'POST'])
def update_profile():
    if session.get('role') != 'employee':
        return redirect(url_for('login'))
    user_id = session.get('user_id')
    profile = EmployeeProfile.query.filter_by(user_id=user_id).first()

    if request.method == 'POST':
        profile.name = request.form['name']
        profile.phone = request.form['phone']
        profile.address = request.form['address']
        profile.role = request.form['role']
        db.session.commit()
        return redirect(url_for('employee_dashboard'))

    return render_template('update_profile.html', profile=profile)

@app.route('/edit-role/<int:user_id>', methods=['GET', 'POST'])
def edit_role(user_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.role = request.form['role']
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_role.html', user=user)

# ------------------------ INIT ------------------------
if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists('firefighter.db'):
            db.create_all()
    app.run(debug=True)

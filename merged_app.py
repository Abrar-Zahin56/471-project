
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from flask import jsonify
from flask_migrate import Migrate
from twilio.rest import Client 
import requests
import stripe

stripe.api_key = 'sk_test_51RLkiOHGFG6UeFUe6JqQgtGYoBCFZG0eADguyWIpwKMN7Kxrw9Nnpco6ECDwTHrWrsrdLD1JrPzORbSdI2ItOP7700rS4PkoUZ'



app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///firefighter.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

migrate = Migrate(app, db)




# ------------------------ MODELS ------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False)


class Emergency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(200), nullable=False)
    
    emergency_type = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'dispatched', 'resolved'
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
    assigned_employee_id = db.Column(db.Integer, db.ForeignKey('employee_profile.id', name='fk_emergency_employee'), nullable=True)
    assigned_employee = db.relationship('EmployeeProfile', foreign_keys=[assigned_employee_id])
    acknowledged = db.Column(db.Boolean, default=False)

class Alarm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default='inactive')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    activated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.String(200), default='Return to station immediately!')


class EmployeeProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    role = db.Column(db.String(100))
    monthly_salary = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(50), default='available')
    hours_worked = db.Column(db.Float, default=0.0)  # Monthly hours
    salary_paid = db.Column(db.Boolean, default=False)

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(200))



# ------------------------ ROUTES ------------------------
@app.route('/')
def home():
    active_fire_emergencies = Emergency.query.filter(
        Emergency.emergency_type == 'fire',
        Emergency.status != 'resolved'
    ).order_by(Emergency.timestamp.desc()).all()

    return render_template('home.html', active_fire_emergencies=active_fire_emergencies)

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

    emergencies = Emergency.query.filter(Emergency.status != 'resolved').all()
    resolved_emergencies = Emergency.query.filter_by(status='resolved').all()

    # All employees for Personnel Status table
    personnel = EmployeeProfile.query.all()

    # Get employees assigned to unresolved emergencies
    assigned_ids = db.session.query(Emergency.assigned_employee_id)\
        .filter(Emergency.status != 'resolved', Emergency.assigned_employee_id.isnot(None)).distinct()

    # Only unassigned employees (for dropdown)
    unassigned_employees = EmployeeProfile.query.filter(~EmployeeProfile.id.in_(assigned_ids)).all()

    for employee in personnel:
        # Find all dispatched emergencies assigned to this employee
        calls = [e for e in emergencies if e.assigned_employee_id == employee.id]
        employee.on_calls = calls  # Attach to employee object
        employee.on_call = len(calls) > 0

    inventory_items = Inventory.query.all()

    weather_info = { 
        "Mirpur": get_weather("Mirpur"),
        "Badda": get_weather("Badda"),
        "Uttara": get_weather("Uttara"),
        "Dhanmondi": get_weather("Dhanmondi")  
    }


    return render_template(
        'admin_dashboard.html',
        emergencies=emergencies,
        resolved_emergencies=resolved_emergencies,
        personnel=personnel,               # ✅ for personnel status table
        employees=unassigned_employees, 
        calculate_salary=calculate_salary,
        weather_info=weather_info,
        inventory=inventory_items    
    )

# Get only employees not in the assigned list
    unassigned_employees = EmployeeProfile.query.filter(~EmployeeProfile.id.in_(assigned_ids)).all()
    emergencies = Emergency.query.filter(Emergency.status != 'resolved').all()
    
    resolved_emergencies = Emergency.query.filter(Emergency.status == 'resolved').all()
    personnel = EmployeeProfile.query.all()
    return render_template('admin_dashboard.html', employees=employees, emergencies=emergencies, personnel=personnel, resolved_emergencies=resolved_emergencies,)

@app.route('/employee')
def employee_dashboard():
    if session.get('role') != 'employee':
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    profile = EmployeeProfile.query.filter_by(user_id=user_id).first()

    # Check for active alarm
    active_alarm = Alarm.query.filter_by(status='active').order_by(Alarm.id.desc()).first()

    assigned_emergency = Emergency.query.filter_by(
    assigned_employee_id=profile.id).filter(Emergency.status != 'resolved').first()

    return render_template('employee_dashboard.html', profile=profile, active_alarm=active_alarm, assigned_emergency=assigned_emergency)

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


@app.route('/respond/<int:emergency_id>', methods=['POST'])
def respond_emergency(emergency_id):
    if 'user_id' not in session or session.get('role') != 'employee':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))

    # Get the employee's profile
    profile = EmployeeProfile.query.filter_by(user_id=session.get('user_id')).first()

    # Get the emergency
    emergency = Emergency.query.get(emergency_id)

    if emergency and profile and emergency.assigned_employee_id == profile.id:
        # Mark the emergency as acknowledged
        emergency.acknowledged = True

        # Update employee status to 'active'
        profile.status = 'active'

        db.session.commit()

        print(f"Updated employee {profile.name} to status: {profile.status}")

        flash('You have responded to the emergency. Status updated to active.', 'success')

    return redirect(url_for('employee_dashboard'))

@app.route('/resolve_emergency/<int:emergency_id>', methods=['POST'])
def resolve_emergency(emergency_id):
    emergency = Emergency.query.get_or_404(emergency_id)
    emergency.status = 'resolved'

    profile = EmployeeProfile.query.filter_by(user_id=session.get('user_id')).first()
    if profile:
        profile.status = 'available' # Reset employee status to available

    db.session.commit()
    flash('Emergency resolved. Your status is now available.', 'success')
    return redirect(url_for('employee_dashboard'))











@app.route('/delete-profile/<int:employee_id>', methods=['POST'])
def delete_profile(employee_id):
    if session.get('role') != 'admin':
        flash("Unauthorized", "danger")
        return redirect(url_for('login'))

    profile = EmployeeProfile.query.get_or_404(employee_id)
    user = User.query.get(profile.user_id)

    # Delete all emergencies assigned to this employee (optional)
    Emergency.query.filter_by(assigned_employee_id=employee_id).update({'assigned_employee_id': None})

    db.session.delete(profile)
    db.session.delete(user)
    db.session.commit()

    flash(f'Profile for {profile.name} deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/pay_salary/<int:employee_id>', methods=['POST'])
def pay_salary(employee_id):
    employee = EmployeeProfile.query.get(employee_id)
    amount = employee.monthly_salary

    intent = stripe.PaymentIntent.create(
        amount=int(amount * 100),  # in cents
        currency='usd',
        automatic_payment_methods={
            'enabled': True,
            'allow_redirects': 'never'
        }
    )

    return render_template('confirm_payment.html', client_secret=intent.client_secret)

@app.route('/admin/inventory')
def view_inventory():
    inventory_items = Inventory.query.all()
    weather_info = {}  
    return render_template('admin_dashboard.html', inventory=inventory_items,  weather_info=weather_info)

@app.route('/add_item', methods=['POST'])
def add_inventory_item():
    name = request.form['name']
    quantity = int(request.form['quantity'])
    description = request.form['description']
    item = Inventory(name=name, quantity=quantity, description=description)
    db.session.add(item)
    db.session.commit()
    flash('Inventory item added!', 'success')
    return redirect(url_for('admin_dashboard'))

#used this to debug the flask app 
@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'EmployeeProfile': EmployeeProfile, 'Emergency': Emergency}

# ------------------------ INIT ------------------------
if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists('firefighter.db'):
            db.create_all()
    app.run(debug=True)

from flask_migrate import Migrate, upgrade
migrate = Migrate(app, db)

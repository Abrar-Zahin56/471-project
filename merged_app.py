
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
app.config['SECRET_KEY'] = 'your_secret_here'
app.secret_key = 'your_secret_key'

@app.before_first_request
def create_tables():
    db.create_all()

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

def calculate_salary(profile):
    base_salary = profile.monthly_salary or 0
    hours = profile.hours_worked if profile.hours_worked is not None else 0

    if hours < 192:
        deduction = base_salary * 0.1
        return base_salary - deduction
    elif hours > 192:
        bonus = base_salary * 0.2
        return base_salary + bonus
    return base_salary

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

@app.route('/emergencies')
def view_emergencies():
    emergencies = Emergency.query.filter(Emergency.status != 'resolved').all()
    employees = User.query.all()  # or however you're loading employees
    return render_template('emergencies.html', emergencies=emergencies, employees=employees)


@app.route('/emergency/new', methods=['GET', 'POST'])
def new_emergency():
    if request.method == 'POST':
        location = request.form['location']
        emergency_type = request.form['emergency_type']

        new_em = Emergency(location=location, emergency_type=emergency_type)
        db.session.add(new_em)
        db.session.commit()

        flash('Emergency reported!', 'success')
        return redirect(url_for('view_emergencies'))

    return render_template('new_emergency.html')

@app.route('/alarms')
def view_alarms():
    alarms = Alarm.query.all()
    return render_template('alarms.html', alarms=alarms)

@app.route('/alarm/activate', methods=['GET', 'POST'])
def activate_alarm():
    if 'user_id' not in session:
        flash('Login required to activate alarm.', 'danger')
        return redirect(url_for('login'))

    alarm = Alarm(status='active', activated_by=session['user_id'])
    db.session.add(alarm)
    db.session.commit()
    flash('Alarm activated!', 'warning')
    return redirect(url_for('view_alarms'))

@app.route('/alarm/deactivate', methods=['POST'])
def deactivate_alarm():
    if 'user_id' not in session:
        flash('Login required to deactivate alarm.', 'danger')
        return redirect(url_for('login'))

    latest_active_alarm = Alarm.query.filter_by(status='active').order_by(Alarm.id.desc()).first()
    if latest_active_alarm:
        latest_active_alarm.status = 'inactive'
        db.session.commit()
        flash('Alarm deactivated.', 'info')
    else:
        flash('No active alarm to deactivate.', 'warning')



    return redirect(url_for('view_alarms'))

@app.route('/check_alarm')
def check_alarm():
    latest_active_alarm = Alarm.query.filter_by(status='active').order_by(Alarm.id.desc()).first()
    return jsonify({'active': bool(latest_active_alarm)})

@app.route('/deactivate_alarm', methods=['POST'])
def api_deactivate_alarm():
    latest_active_alarm = Alarm.query.filter_by(status='active').order_by(Alarm.id.desc()).first()
    if latest_active_alarm:
        latest_active_alarm.status = 'inactive'
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'no_active_alarm'})

@app.route('/assign_emergency/<int:emergency_id>', methods=['POST'])
def assign_emergency(emergency_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        emergency = Emergency.query.get(emergency_id)
        employee_id = request.form['employee_id']

#Update assignment
        emergency.assigned_employee_id = employee_id
        emergency.status = 'dispatched'

#Update employee status to 'on_call'
        employee = User.query.get(employee_id)
        employee.status = 'on_call'

        db.session.commit()
        flash('Assignment successful!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')

    return redirect(request.referrer or url_for('dashboard'))

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




#SUBMIT AND GENERATE REPORT 

from flask import send_file
from io import BytesIO
from reportlab.pdfgen import canvas 
import os
from datetime import datetime

@app.route('/submit-report', methods=['GET', 'POST'])
def submit_report():
    if request.method == 'POST':
        disaster_type = request.form['disaster_type']
        disaster_location = request.form['disaster_location']
        num_employees = request.form['employees_present']
        people_affected = request.form['people_affected']
        description = request.form['description']

        # 🔹 Ensure folder exists
        reports_folder = 'generated_reports'
        os.makedirs(reports_folder, exist_ok=True)

        # 🔹 Create filename using timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.pdf"
        filepath = os.path.join(reports_folder, filename)

        # 🔹 Generate and save PDF
        p = canvas.Canvas(filepath)
        p.setFont("Helvetica", 12)
        p.drawString(100, 800, "Disaster Report")
        p.drawString(100, 780, f"Type: {disaster_type}")
        p.drawString(100, 760, f"Location: {disaster_location}")
        p.drawString(100, 740, f"Employees Present: {num_employees}")
        p.drawString(100, 720, f"People Affected: {people_affected}")
        p.drawString(100, 700, f"Description: {description}")
        p.showPage()
        p.save()

        return f"✅ Report submitted and saved as {filename}"

    return render_template('index.html')

@app.route('/report_archive')
def report_archive():
    reports_folder = 'generated_reports'
    files = os.listdir(reports_folder)
    files.sort(reverse=True)
    return render_template('report_archive.html', files=files)
 
@app.route('/generated_reports/<filename>')
def download_report(filename):
    return send_file(os.path.join('generated_reports', filename), as_attachment=True)





@app.route('/debug/alarms')
def debug_alarms():
    alarms = Alarm.query.order_by(Alarm.id.desc()).limit(5).all()
    return '<br>'.join([f'#{a.id} - {a.status}' for a in alarms]) 



# CHATBOX FOR CONSTANT COMMUNICATION 
from flask import request, jsonify

chat_messages = []

@app.route('/chat', methods=['POST'])
def chat():
    sender = request.form['sender']
    message = request.form['message']
    chat_messages.append({'sender': sender, 'message': message})
    return '', 204

@app.route('/get_messages')
def get_messages():
    return jsonify(chat_messages) 


# ADMIN WILL ALERT NEARBY RESIDENTS

resident_emails = {
    "Mirpur": ["rayatun007@gmail.com"],
    "Badda": ["rayatun007@gmail.com"],
    "Uttara": ["rayatun007@gmail.com"],
    "Kalabagan": ["rayatun007@gmail.com"]
} 

import smtplib
from email.message import EmailMessage

def send_emergency_email(location, subject, body):
    sender_email = "FirefighterSystem444@gmail.com"
    sender_password = "kaojyajdumdimadu"  # App-specific password

    print(f"🔔 Attempting to send email for location: {location}")
    print(f"📨 Subject: {subject}")
    print(f"📝 Body: {body}")

    if location not in resident_emails:
        print("❌ Location not found in resident_emails")
        return False

    try:
        for recipient in resident_emails[location]:
            print(f"➡️ Sending to: {recipient}")
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = sender_email
            msg['To'] = recipient
            msg.set_content(body)

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(sender_email, sender_password)
                smtp.send_message(msg)
                print(f"✅ Email successfully sent to {recipient}")

        print("🎉 All emails sent successfully.")
        return True

    except Exception as e:
        print("❌ Email send failed:", e)
        return False 


@app.route('/send_email', methods=['GET', 'POST'])
def send_email():
    if request.method == 'POST':
        print("✅ Form submitted!") 
        location = request.form['location']
        subject = request.form['subject']
        body = request.form['body']

        success = send_emergency_email(location, subject, body)
        if success:
            flash(f"Emergency email sent to residents of {location}.", "success")
        else:
            flash(f"Failed to send email to {location}.", "danger")

        return redirect(url_for('admin_dashboard'))

    return render_template('send_email.html')  



# SHOW WEATHER STATUS 
import requests

OPENWEATHER_API_KEY = "d9c5ffa72c05966cd7de5760634ee132"  

def get_weather(location):
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHER_API_KEY}&units=metric"
        response = requests.get(url)
        data = response.json() 

        if data.get("cod") != 200:
            return "Weather unavailable"

        desc = data["weather"][0]["description"].title()
        temp = data["main"]["temp"]
        return f"{desc}, {temp}°C"

    except Exception as e:
        print("❌ Weather API error:", e)
        return "Weather unavailable"
 






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

@app.route('/declare_emergency', methods=['POST'])
def declare_emergency():
    location = request.form['location']
    emergency_type = request.form['emergency_type'].lower()  # Normalize to lowercase

    print(f"Emergency Type: {emergency_type}")  # Debug print to ensure emergency type is received correctly

    assigned = False
    crew = None

    # Automatically assign crew based on emergency type
    if emergency_type == 'fire':
        # Find an available firefighter
        crew = EmployeeProfile.query.filter_by(role='Firefighter', status='available').first()
        print(f"Assigned Crew for Fire: {crew}")  # Debug print for crew assignment

    elif emergency_type == 'medical':
        # Find an available paramedic
        crew = EmployeeProfile.query.filter_by(role='Paramedic', status='available').first()
        print(f"Assigned Crew for Medical: {crew}")  # Debug print for crew assignment

    elif emergency_type == 'rescue':
        # Find an available rescuer
        crew = EmployeeProfile.query.filter_by(role='Rescuer', status='available').first()
        print(f"Assigned Crew for Rescue: {crew}")  # Debug print for crew assignment

    elif emergency_type == 'hazardous':
        # Find an available hazardous material handler (assuming role 'HazMat')
        crew = EmployeeProfile.query.filter_by(role='HazMat', status='available').first()
        print(f"Assigned Crew for Hazardous Material: {crew}")  # Debug print for crew assignment

    if crew:
        # Assign employee to the emergency
        new_emergency = Emergency(
            location=location,
            emergency_type=emergency_type,
            assigned_employee_id=crew.id,
            status='dispatched'  # Mark as dispatched
        )
        crew.status = 'on_call'  # Change crew status to on_call
        db.session.add(new_emergency)
        db.session.commit()
        assigned = True
        print(f"Emergency Declared and Crew Assigned: {crew.name}")  # Debug print to confirm assignment
    else:
        # No crew found, create the emergency with status 'pending' for manual assignment
        new_emergency = Emergency(
            location=location,
            emergency_type=emergency_type,
            status='pending',  # Status is 'pending' when no crew is assigned
            assigned_employee_id=None  # No employee assigned
        )
        db.session.add(new_emergency)
        db.session.commit()
        flash('⚠️ Emergency declared, but no available crew found! It is now pending for manual assignment.', 'warning')

    if assigned:
        flash('✅ Emergency declared and crew assigned!', 'success')

    return redirect(url_for('admin_dashboard'))









    


@app.route('/unassign_emergency/<int:emergency_id>', methods=['POST'])
def unassign_emergency(emergency_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    emergency = Emergency.query.get_or_404(emergency_id)

    # Only allow unassigning for dispatched emergencies
    if emergency.status != 'dispatched':
        flash('This emergency cannot be unassigned as it is not dispatched.', 'danger')
        return redirect(url_for('admin_dashboard'))

    # Unassign the employee from the emergency
    emergency.assigned_employee_id = None
    emergency.status = 'pending'  # Set status back to 'pending'

    # Optionally, update the employee status back to 'available'
    if emergency.assigned_employee:
        employee = emergency.assigned_employee
        employee.status = 'available'
        db.session.commit()

    db.session.commit()
    flash('Emergency unassigned successfully!', 'success')
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

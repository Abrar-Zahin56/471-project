
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from flask import jsonify
from twilio.rest import Client 


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


class Emergency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(200), nullable=False)
    
    emergency_type = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'dispatched', 'resolved'
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
    assigned_employee_id = db.Column(db.Integer, db.ForeignKey('employee_profile.id'), nullable=True)
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
    emergencies = Emergency.query.filter(Emergency.status != 'resolved').all()
    return render_template('admin_dashboard.html', employees=employees, emergencies=emergencies)

@app.route('/employee')
def employee_dashboard():
    if session.get('role') != 'employee':
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    profile = EmployeeProfile.query.filter_by(user_id=user_id).first()

    # Check for active alarm
    active_alarm = Alarm.query.filter_by(status='active').order_by(Alarm.id.desc()).first()

    assigned_emergency = Emergency.query.filter_by(assigned_employee_id=profile.id).first()

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

@app.route('/assign-emergency/<int:emergency_id>', methods=['POST'])
def assign_emergency(emergency_id):
    if session.get('role') != 'admin':
        flash('Unauthorized', 'danger')
        return redirect(url_for('login'))

    emergency = Emergency.query.get_or_404(emergency_id)
    employee_id = request.form.get('employee_id')

    if employee_id:
        emergency.assigned_employee_id = int(employee_id)
        emergency.status = 'dispatched'
        db.session.commit()
        flash(f'Emergency #{emergency.id} assigned.', 'success')
    else:
        flash('No employee selected.', 'warning')

    return redirect(url_for('admin_dashboard'))

@app.route('/respond/<int:emergency_id>', methods=['POST'])
def respond_emergency(emergency_id):
    if 'user_id' not in session or session.get('role') != 'employee':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))

    emergency = Emergency.query.get(emergency_id)
    if emergency and emergency.assigned_employee_id == profile.id:
        # Update emergency as acknowledged
        emergency.acknowledged = True
        db.session.commit()

        # Update personnel status to "active"
        profile = EmployeeProfile.query.filter_by(user_id=session.get('user_id')).first()
        if profile:
            profile.status = 'active'
            db.session.commit()

        flash('You have responded to the emergency.', 'success')

    return redirect(url_for('employee_dashboard'))

from flask import send_file
from io import BytesIO
from reportlab.pdfgen import canvas

@app.route('/submit-report', methods=['GET', 'POST'])
def submit_report():
    if request.method == 'POST':
        disaster_type = request.form['disaster_type']
        disaster_location = request.form['disaster_location']
        num_employees = request.form['employees_present']
        people_affected = request.form['people_affected']
        description = request.form['description']

        # Create a PDF in memory
        buffer = BytesIO()
        p = canvas.Canvas(buffer)
        p.setFont("Helvetica", 12)

        # Add text to the PDF
        p.drawString(100, 800, "Disaster Report")
        p.drawString(100, 780, f"Type: {disaster_type}")
        p.drawString(100, 760, f"Location: {disaster_location}")
        p.drawString(100, 740, f"Employees Present: {num_employees}")
        p.drawString(100, 720, f"People Affected: {people_affected}")
        p.drawString(100, 700, f"Description: {description}")

        p.showPage()
        p.save()
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name="disaster_report.pdf",
            mimetype='application/pdf'
        )

    return render_template('index.html')

@app.route('/debug/alarms')
def debug_alarms():
    alarms = Alarm.query.order_by(Alarm.id.desc()).limit(5).all()
    return '<br>'.join([f'#{a.id} - {a.status}' for a in alarms]) 


#chatbox for constant communication 
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


#admin will alert nearby residents 
# Twilio credentials
TWILIO_ACCOUNT_SID = "AC2f794b4881621f32e9c0da907f1a26d1"
TWILIO_AUTH_TOKEN = "e84948c3669c988fb5a3db88fafdebef"
TWILIO_PHONE = "+14013891339" 

# Sample resident phone numbers
resident_contacts = {
    "Mirpur": ["+8801718231315"],
    "Badda": ["+8801718231315"]
}


def send_emergency_sms(location, message):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    if location in resident_contacts:
        for number in resident_contacts[location]:
            client.messages.create(
                body=message,
                from_=TWILIO_PHONE,
                to=number
            )

@app.route('/notify_residents/<location>')
def notify_residents(location):
    if location not in resident_contacts:
        flash("Invalid location selected.", "danger")
        return redirect(url_for('admin_dashboard'))

    message = f"🚨 Emergency Alert: An emergency has been reported in {location}. Stay safe and follow instructions."
    send_emergency_sms(location, message)

    flash(f"Residents in {location} have been notified successfully.", "success")
    return redirect(url_for('admin_dashboard'))




# ------------------------ INIT ------------------------
if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists('firefighter.db'):
            db.create_all()
    app.run(debug=True)

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from datetime import timedelta, datetime  # Good to have both for time operations

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this!
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fire_department.db'  # Add this line
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  



@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Not found",
        "message": str(error)
    }), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({
        "error": "Server error",
        "message": str(error)
    }), 500

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin' or 'employee'
    status = db.Column(db.String(20), default='available')  # 'available' or 'on_call'
    current_location = db.Column(db.String(200))

class Emergency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(200), nullable=False)
    emergency_type = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'dispatched', 'resolved'
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
    assigned_employee_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Alarm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default='inactive')  # Fixed missing parenthesis
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    activated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.String(200), default='Return to station immediately!')

# Create tables
with app.app_context():
    db.create_all()

# Routes
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Invalid username or password', 'danger')
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()  # This should be ONLY in logout
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if user.role == 'admin':
        employees = User.query.filter_by(role='employee').all()
        emergencies = Emergency.query.all()
        return render_template('admin_dashboard.html', 
                            employees=employees, 
                            emergencies=emergencies,
                            Alarm=Alarm)  # Pass Alarm to admin template
    else:
        assigned_emergencies = Emergency.query.filter_by(
            assigned_employee_id=user.id,
            status='dispatched'
        ).all()
        return render_template('employee_dashboard.html',
                            emergencies=assigned_emergencies,
                            user=user,
                            Alarm=Alarm)  # Pass Alarm to employee template
@app.route('/declare_emergency', methods=['POST'])
def declare_emergency():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    location = request.form['location']
    emergency_type = request.form['emergency_type']
    
    new_emergency = Emergency(
        location=location,
        emergency_type=emergency_type
    )
    db.session.add(new_emergency)
    db.session.commit()
    
    flash('Emergency declared!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/assign_emergency/<int:emergency_id>', methods=['POST'])
def assign_emergency(emergency_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        # Your existing assignment logic
        emergency = Emergency.query.get(emergency_id)
        employee_id = request.form['employee_id']
        
        # Update assignment
        emergency.assigned_employee_id = employee_id
        emergency.status = 'dispatched'
        
        # Update employee status
        employee = User.query.get(employee_id)
        employee.status = 'on_call'
        
        db.session.commit()
        flash('Assignment successful!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    # Stay on same page instead of redirecting
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/update_status/<int:emergency_id>', methods=['POST'])
def update_status(emergency_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        emergency = Emergency.query.get(emergency_id)
        emergency.status = request.form['status']
        
        if emergency.status == 'resolved':
            employee = User.query.get(emergency.assigned_employee_id)
            if employee:
                employee.status = 'available'
        
        db.session.commit()
        flash('Status updated!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('dashboard'))
@app.route('/trigger_alarm', methods=['POST'])
def trigger_alarm():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        new_alarm = Alarm(
            status='active',
            activated_by=session['user_id'],
            message='Return to station immediately!'
        )
        db.session.add(new_alarm)
        db.session.commit()
        flash('General alarm activated!', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error activating alarm: {str(e)}', 'danger')
        app.logger.error(f'Alarm activation failed: {str(e)}')  # Log the error
    
    return redirect(url_for('dashboard'))

@app.route('/deactivate_alarm', methods=['POST'])
def deactivate_alarm():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        # Find the most recent active alarm
        active_alarm = Alarm.query.filter_by(status='active').order_by(Alarm.timestamp.desc()).first()
        
        if active_alarm:
            # Update the existing alarm instead of creating new one
            active_alarm.status = 'inactive'
            active_alarm.timestamp = datetime.utcnow()
            db.session.commit()
            flash('Alarm deactivated', 'success')
        else:
            flash('No active alarm found', 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error deactivating alarm: {str(e)}', 'danger')
        app.logger.error(f"Alarm deactivation failed: {str(e)}")
    
    return redirect(url_for('dashboard'))

@app.route('/debug_routes')
def debug_routes():
    try:
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                'endpoint': rule.endpoint,
                'path': str(rule),
                'methods': list(rule.methods)
            })
        return jsonify({
            'status': 'success',
            'routes': routes,
            'total_routes': len(routes)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1221, debug=True)
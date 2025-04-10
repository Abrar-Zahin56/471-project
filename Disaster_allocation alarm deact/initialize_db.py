# initialize_db.py
from datetime import datetime
from app import app, db, User, Emergency
from werkzeug.security import generate_password_hash

def initialize_database():
    with app.app_context():
        # Create all database tables
        db.drop_all()  # Clear existing data
        db.create_all()
        
        # Create admin user if doesn't exist
        if not User.query.first():
            # Create admin
            admin = User(
                username="admin",
                password=generate_password_hash("admin123"),
                role="admin",
                status="available"
            )
            
            # Create employees
            employees = [
                User(username="firefighter1", password=generate_password_hash("pass123"), role="employee", status="available"),
                User(username="firefighter2", password=generate_password_hash("pass123"), role="employee", status="available"),
                User(username="paramedic1", password=generate_password_hash("pass123"), role="employee", status="available"),
                User(username="dispatcher1", password=generate_password_hash("pass123"), role="employee", status="available")
            ]
            
            # Create sample emergencies
            emergencies = [
                Emergency(
                    location="123 Main St",
                    emergency_type="fire",
                    status="pending",
                    timestamp=datetime.utcnow()
                ),
                Emergency(
                    location="456 Oak Ave",
                    emergency_type="medical",
                    status="dispatched",
                    timestamp=datetime.utcnow(),
                    assigned_employee_id=2  # Assign to firefighter1
                )
            ]
            
            # Add all to database
            db.session.add(admin)
            db.session.add_all(employees)
            db.session.add_all(emergencies)
            db.session.commit()
            
            print("✅ Database initialized with:")
            print(f"- Admin account (username: 'admin', password: 'admin123')")
            print(f"- {len(employees)} employee accounts")
            print(f"- {len(emergencies)} sample emergencies")
        else:
            print("ℹ️ Database already contains data - no changes made")

if __name__ == '__main__':
    initialize_database()
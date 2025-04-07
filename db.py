from app.models import db
from run import app

with app.app_context():
    db.create_all()
    print("Tables created successfully.")
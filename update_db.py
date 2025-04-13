from merged_app import app, db
from sqlalchemy import text  # ✅ Make sure this is imported

with app.app_context():
    with db.engine.connect() as con:
        # ✅ Use text() here — this is the key fix
        con.execute(text('ALTER TABLE emergency ADD COLUMN acknowledged BOOLEAN DEFAULT FALSE;'))

print("Column 'acknowledged' added successfully.")
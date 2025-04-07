from flask import render_template, request, redirect, url_for, flash, Blueprint
from .models import db, User

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return redirect(url_for('main.create_profile'))

@bp.route('/create-profile', methods=['GET', 'POST'])
def create_profile():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Profile created successfully!')
        return redirect(url_for('main.create_profile'))

    return render_template('create_profile.html')
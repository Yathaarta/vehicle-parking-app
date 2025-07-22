from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from models.dbmodel import *
from app import app
from werkzeug.security import generate_password_hash, check_password_hash
from slugify import slugify
from datetime import timedelta
app.permanent_session_lifetime = timedelta(minutes=10)

# -------------------------
# Public Home
# -------------------------
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'GET':
        return render_template('home2.html')
    else:
        flash("Please login to continue with booking", "info")
        return redirect(url_for('login'))


# -------------------------
# LOGIN
# -------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form.get('email')
    password = request.form.get('password')
    user = User.query.filter_by(email_id=email).first()

    if not user:
        flash("User does not exist, Please register", "warning")
        return redirect(url_for('register'))

    if not check_password_hash(user.pass_wd, password):
        flash("Incorrect Password", "warning")
        return redirect(url_for('login'))

    # Store session
    session['user_id'] = user.user_id
    session['username'] = user.user_name
    session['is_admin'] = user.is_admin
    session.permanent = True

    flash("Login Successful", "success")

    if user.is_admin:
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('user_home', user_id=user.user_id, slug=slugify(user.user_name)))


# -------------------------
# REGISTER
# -------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    username = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    cnf_password = request.form.get('confirm_password')

    if password != cnf_password:
        flash("Both passwords must match", "warning")
        return redirect(url_for('register'))

    existing_user = User.query.filter_by(email_id=email).first()
    if existing_user:
        flash("A User with this email id already exists!", "warning")
        return redirect(url_for('register'))

    passhash = generate_password_hash(password)
    new_user = User(email_id=email, pass_wd=passhash, user_name=username, is_admin=False)
    db.session.add(new_user)
    db.session.commit()

    flash("User registered successfully, Please Login to continue", "success")
    return redirect(url_for('login'))


# -------------------------
# USER HOME
# -------------------------
@app.route('/<int:user_id>-<slug>/home')
def user_home(user_id, slug):
    if 'user_id' not in session:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for('login'))
    
    if user.is_admin:
        flash("Admins cannot access user home", "danger")
        return redirect(url_for('admin_dashboard'))

    return render_template('user_home.html', user=user)


# -------------------------
# LOGOUT
# -------------------------
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('home'))


# -------------------------
# PROFILE
# -------------------------
@app.route('/<int:user_id>-<slug>/profile', methods=['GET', 'POST'])
def profile(user_id, slug):
    if 'user_id' not in session:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))

    user = User.query.get(user_id)

    if request.method == "POST":
        action = request.form.get('action')

        if action == 'update_name':
            user.user_name = request.form.get('username')
            flash("Name updated successfully", "success")

        elif action == 'update_email':
            email_id = request.form.get('email')
            existing_user = User.query.filter_by(email_id=email_id).first()
            if existing_user and existing_user.user_id != user.user_id:
                flash("Email already exists, please use a different email", "warning")
            else:
                user.email_id = email_id
                flash("Email updated successfully", "success")

        elif action == 'update_password':
            old_pass = request.form.get('old_password')
            new_pass = request.form.get('new_password')
            if check_password_hash(user.pass_wd, old_pass):
                user.pass_wd = generate_password_hash(new_pass)
                flash("Password updated successfully", "success")
            else:
                flash("Old password is incorrect", "danger")

        db.session.commit()
        return redirect(url_for('profile', user_id=user.user_id, slug=slugify(user.user_name)))

    return render_template('profile.html', user=user)


# -------------------------
# ADMIN DASHBOARD
# -------------------------
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Users cannot Access this page. Go to user account", "warning")
        flash("If Admin, please log in first", "warning")
        return redirect(url_for('login'))

    parking_lots = ParkingLot.query.all()
    return render_template('admin_dashboard.html', parking_lots=parking_lots)


#--------------------------
# EDIT PROFILE
#--------------------------
@app.route('/admin/profile', methods=['GET', 'POST'])
def admin_profile():
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Access denied! Admins only.", "danger")
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])

    if request.method == "POST":
        action = request.form.get('action')

        if action == 'update_name':
            user.user_name = request.form.get('username')
            flash("Name updated successfully", "success")

        elif action == 'update_email':
            email_id = request.form.get('email')
            existing_user = User.query.filter_by(email_id=email_id).first()
            if existing_user and existing_user.user_id != user.user_id:
                flash("Email already exists, please use a different email", "warning")
            else:
                user.email_id = email_id
                flash("Email updated successfully", "success")

        elif action == 'update_password':
            old_pass = request.form.get('old_password')
            new_pass = request.form.get('new_password')
            if check_password_hash(user.pass_wd, old_pass):
                user.pass_wd = generate_password_hash(new_pass)
                flash("Password updated successfully", "success")
            else:
                flash("Old password is incorrect", "danger")

        db.session.commit()
        return redirect(url_for('/admin/profile'))

    return render_template('admin_profile.html', user=user)

# -------------------------
# ADD PARKING LOT
# -------------------------
@app.route('/admin/add_parking_lot', methods=['GET', 'POST'])
def add_parking():
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Access denied! Admins only.", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        city = request.form.get('city')
        pincode = request.form.get('pincode')
        capacity = int(request.form.get('capacity'))
        price_per_hr = float(request.form.get('price_per_hr'))

        new_lot = ParkingLot(name=name, address=address, city=city, pincode=pincode,
                              capacity=capacity, occupied=0, price_per_hr=price_per_hr)

        db.session.add(new_lot)
        db.session.commit()
        flash("Parking Lot added successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('add_parking_lot.html')


# -------------------------
# DELETE PARKING LOT
# -------------------------
@app.route('/admin/delete_parking_lot/<int:lot_id>')
def delete_parking(lot_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Access denied! Admins only.", "danger")
        return redirect(url_for('login'))

    lot = ParkingLot.query.get(lot_id)
    if not lot:
        flash("Parking Lot not found!", "danger")
        return redirect(url_for('admin_dashboard'))

    db.session.delete(lot)
    db.session.commit()
    flash("Parking Lot deleted successfully!", "success")
    return redirect(url_for('admin_dashboard'))


# -------------------------
# EDIT PARKING LOT
# -------------------------
@app.route('/admin/edit_parking_lot/<int:lot_id>', methods=['GET', 'POST'])
def edit_parking(lot_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Access denied! Admins only.", "danger")
        return redirect(url_for('login'))

    lot = ParkingLot.query.get(lot_id)
    if not lot:
        flash("Parking Lot not found!", "danger")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        lot.name = request.form.get('name')
        lot.address = request.form.get('address')
        lot.city = request.form.get('city')
        lot.pincode = request.form.get('pincode')
        lot.capacity = int(request.form.get('capacity'))
        lot.price_per_hr = float(request.form.get('price_per_hr'))

        db.session.commit()
        flash("Parking Lot updated successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_parking_lot.html', lot=lot)

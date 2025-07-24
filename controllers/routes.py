from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from models.dbmodel import *
from app import app
from werkzeug.security import generate_password_hash, check_password_hash
from slugify import slugify
from datetime import datetime, timedelta
from sqlalchemy import func
import json
from functools import wraps # Import wraps for decorators

app.permanent_session_lifetime = timedelta(minutes=10)

# -------------------------
# Decorators
# -------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first!", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash("Access denied! Admins only.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


#---------------------------------------PUBLIC ROUTES-------------------------------------
# -------------------------
# Public Home
# -------------------------
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'GET':
        return render_template('home2.html')
    else:
        flash("Please login to continue with booking", "warning")
        return redirect(url_for('login'))

# -------------------------
# ABOUT US Page
# -------------------------
@app.route('/about')
@app.route('/about')
def about():
    return render_template('about.html')

# -------------------------
# CONTACT US Page
# -------------------------
@app.route('/contact')
def contact():
    return render_template('contact.html')

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
# LOGOUT-both
# -------------------------
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('home'))



#---------------------------------------USER ROUTES---------------------------------------

# -------------------------
# USER HOME
# -------------------------
@app.route('/<int:user_id>-<slug>/home')
@login_required # Apply login_required decorator
def user_home(user_id, slug):
    # Check if the logged-in user matches the user_id in the URL
    if session.get('user_id') != user_id:
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for('login'))

    # Fetch distinct cities
    cities = [row[0] for row in db.session.query(ParkingLot.city).distinct().all()]

    # Current time
    now = datetime.now()

    # Get all bookings of this user
    current_bookings = UserBookings.query.filter_by(user_id=user_id).all()

    expired_ids = []

    # Handle expired bookings
    for booking in current_bookings:
        if booking.leaving_time < now:
            expired_ids.append(booking.id)
            # Move to history
            history = UserHistory(
                user_id=booking.user_id,
                spot_id=booking.spot_id,
                booking_time=booking.parking_time,
                leaving_time=booking.leaving_time,
                parking_cost=booking.parking_cost,
                vehicle_no=booking.vehicle_no
            )
            db.session.add(history)
            # Free spot
            if booking.spot:
                booking.spot.status = 'A'
                if booking.spot.lot.occupied_spots > 0:
                    booking.spot.lot.occupied_spots -= 1
            db.session.delete(booking)
    
    if expired_ids:
        db.session.commit()
        flash("Your last booking expired. Please evacuate the parking spot or book again.", "warning")

    # Fetch active bookings again (after cleanup)
    active_bookings = UserBookings.query.filter_by(user_id=user_id).all()

    # Recent history
    recent_history = UserHistory.query.filter_by(user_id=user_id).order_by(UserHistory.id.desc()).limit(5).all()

    return render_template('user_home1.html', user=user, cities=cities,
                           current_bookings=active_bookings, recent_history=recent_history)


# -------------------------
# PROFILE-USER
# -------------------------
@app.route('/<int:user_id>-<slug>/profile', methods=['GET', 'POST'])
@login_required # Apply login_required decorator
def profile(user_id, slug):
    # Check if the logged-in user matches the user_id in the URL
    if session.get('user_id') != user_id:
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for('login'))

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

        elif action == 'delete_account':
            # Delete user's history & bookings
            UserHistory.query.filter_by(user_id=user_id).delete()
            UserBookings.query.filter_by(user_id=user_id).delete()

            # Delete user
            db.session.delete(user)
            db.session.commit()

            session.clear()
            flash("Your account and all data have been deleted.", "success")
            return redirect(url_for('home'))

        db.session.commit()
        return redirect(url_for('profile', user_id=user.user_id, slug=slugify(user.user_name)))

    return render_template('profile.html', user=user)


#--------------------------
# USER HISTORY 
#--------------------------
@app.route('/<int:user_id>-<slug>/history')
@login_required # Apply login_required decorator
def user_history(user_id, slug):
    # Check if the logged-in user matches the user_id in the URL
    if session.get('user_id') != user_id:
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for('login'))

    # Fetch full history for this user
    user_history = UserHistory.query.filter_by(user_id=user_id).order_by(UserHistory.id.desc()).all()

    return render_template('user_history.html', user=user, user_history=user_history)


# ------------------------
# SEARCH PARKING-user
# ------------------------
@app.route('/<int:user_id>-<slug>/search-parking', methods=['GET', 'POST'])
@login_required # Apply login_required decorator
def search_parking(user_id, slug):
    # Check if the logged-in user matches the user_id in the URL
    if session.get('user_id') != user_id:
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))
    
    user = User.query.get(user_id)
    cities = [row[0] for row in db.session.query(ParkingLot.city).distinct().all()]

    if request.method == 'POST':
        city = request.form.get('city')
        pincode = request.form.get('pincode')

        query = ParkingLot.query
        if city:
            query = query.filter_by(city=city)
        if pincode:
            query = query.filter_by(pincode=pincode)

        parking_lots = query.all()
        return render_template('search_parking.html',user=user, parking_lots=parking_lots, cities=cities)

    return render_template('search_parking.html', user=user, parking_lots=None, cities=cities)



# ------------------------
# BOOK AND CONFIRM SPOT-user
# ------------------------
@app.route('/<int:user_id>-<slug>/book-spot/<int:lot_id>', methods=['GET', 'POST'])
@login_required # Apply login_required decorator
def book_spot(user_id, slug, lot_id):
    # Check if the logged-in user matches the user_id in the URL
    if session.get('user_id') != user_id:
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))
    
    user = User.query.get(user_id)
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        flash("Parking lot not found!", "danger")
        return redirect(url_for('search_parking'))

    # Check if spots available
    available_spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').all()
    if not available_spots:
        flash("No available spots in this parking lot!", "danger")
        return redirect(url_for('search_parking'))

    estimated_price = None
    vehicle_no = parking_time = leaving_time = None

    if request.method == 'POST':
        vehicle_no = request.form.get('vehicle_no')
        parking_time_str = request.form.get('parking_time')
        leaving_time_str = request.form.get('leaving_time')
        action = request.form.get('action')  # 'preview' or 'confirm'

        try:
            parking_time = datetime.fromisoformat(parking_time_str)
            leaving_time = datetime.fromisoformat(leaving_time_str)
        except ValueError:
            flash("Invalid date format!", "danger")
            return render_template('book_spot.html', lot=lot)

        now = datetime.now()
        if parking_time <= now:
            flash("Parking start time must be in the future!", "warning")
            return render_template('book_spot.html', user=user,lot=lot)

        if leaving_time <= parking_time:
            flash("Leaving time must be later than parking time!", "warning")
            return render_template('book_spot.html', user=user, lot=lot)

        # Calculate cost
        hours = (leaving_time - parking_time).total_seconds() / 3600
        estimated_price = round(hours * lot.price_per_hr, 2)

        if action == 'confirm':  #  Finalise booking
            spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()
            if not spot:
                flash("No available spots!", "danger")
                return redirect(url_for('search_parking'))

            booking = UserBookings(
                user_id=session['user_id'],
                spot_id=spot.spot_id,
                parking_time=parking_time,
                leaving_time=leaving_time,
                parking_cost=estimated_price,
                vehicle_no=vehicle_no
            )

            spot.status = 'O'
            lot.occupied_spots += 1
            db.session.add(booking)
            db.session.commit()

            flash(f"Booking confirmed! Total cost: ₹ {estimated_price}", "success")
            return redirect(url_for('user_home', user_id=session['user_id'], slug=slugify(session['username'])))

    return render_template('book_spot.html',user=user, lot=lot, estimated_price=estimated_price,
                           vehicle_no=vehicle_no, parking_time=parking_time, leaving_time=leaving_time)


#--------------------------
# RELEASE BOOKING-USER
#--------------------------
@app.route('/release_booking/<int:booking_id>', methods=['POST'])
@login_required # Apply login_required decorator
def release_booking(booking_id):
    booking = UserBookings.query.get(booking_id)
    # Ensure the booking belongs to the logged-in user
    if not booking or booking.user_id != session.get('user_id'):
        flash("Invalid booking or unauthorized access.", "danger")
        return redirect(url_for('user_home', user_id=session.get('user_id'), slug=slugify(session.get('username'))))

    # Move booking to history
    history = UserHistory(
        user_id=booking.user_id,
        spot_id=booking.spot_id,
        booking_time=booking.parking_time,
        leaving_time=booking.leaving_time,
        parking_cost=booking.parking_cost,
        vehicle_no=booking.vehicle_no
    )
    db.session.add(history)

    # Free the parking spot
    if booking.spot:
        booking.spot.status = 'A'
        if booking.spot.lot.occupied_spots > 0:
            booking.spot.lot.occupied_spots -= 1

    db.session.delete(booking)
    db.session.commit()
    flash("Booking released successfully!", "success")

    return redirect(url_for('user_home', user_id=session['user_id'], slug=slugify(session['username'])))


#-----------------------
# USER SUMMARY 
#-----------------------
@app.route('/<int:user_id>-<slug>/summary')
@login_required # Apply login_required decorator
def user_summary(user_id, slug):
    # Check if the logged-in user matches the user_id in the URL
    if session.get('user_id') != user_id:
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for('login'))

    # Group bookings by parking lot name from history
    data = (
        db.session.query(ParkingLot.primelocation_name, func.count(UserHistory.id))
        .join(ParkingSpot, ParkingSpot.lot_id == ParkingLot.lot_id)
        .join(UserHistory, UserHistory.spot_id == ParkingSpot.spot_id)
        .filter(UserHistory.user_id == user_id)
        .group_by(ParkingLot.primelocation_name)
        .order_by(func.count(UserHistory.id).desc())
        .limit(5)
        .all()
    )

    # Prepare chart data
    labels = [row[0] for row in data]
    counts = [row[1] for row in data]

    return render_template(
        'user_summary.html',
        user=user,
        labels=json.dumps(labels),
        counts=json.dumps(counts)
    )



#---------------------------------------ADMIN ROUTES---------------------------------------

# -------------------------
# ADMIN DASHBOARD
# -------------------------
@app.route('/admin/dashboard')
@admin_required # Apply admin_required decorator
def admin_dashboard():
    parking_lots = ParkingLot.query.all()
    return render_template('admin_dashboard.html', parking_lots=parking_lots)


#--------------------------
# EDIT PROFILE-admin
#--------------------------
@app.route('/admin/profile', methods=['GET', 'POST'])
@admin_required # Apply admin_required decorator
def admin_profile():
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
        return redirect(url_for('admin_profile'))

    return render_template('admin_profile.html', user=user)

# -------------------------
# ADD PARKING LOT-admin
# -------------------------
@app.route('/admin/add_parking_lot', methods=['GET', 'POST'])
@admin_required # Apply admin_required decorator
def add_parking():
    if request.method == 'POST':
        area_type = request.form.get('area_type')
        address = request.form.get('address')
        prime_loc = request.form.get('primelocation_name')
        price_per_hr = float(request.form.get('price_per_hr'))
        city = request.form.get('city')
        pincode = request.form.get('pincode')
        max_spots = int(request.form.get('capacity'))
        occupied_spots = 0  # Initially set to 0

        new_lot = ParkingLot(area_type=area_type, city=city, primelocation_name=prime_loc,
                             price_per_hr=price_per_hr, address=address, pincode=pincode, max_spots=max_spots,
                             occupied_spots=occupied_spots)

        db.session.add(new_lot)
        db.session.flush()  # Get lot_id before commit

        for _ in range(max_spots):
            db.session.add(ParkingSpot(lot_id=new_lot.lot_id, status='A'))
        db.session.commit()    

        flash("Parking Lot added successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('add_parking_lot.html')


# -------------------------
# DELETE PARKING LOT-admin
# -------------------------
@app.route('/admin/delete_parking_lot/<int:lot_id>')
@admin_required # Apply admin_required decorator
def delete_parking(lot_id):
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        flash("Parking Lot not found!", "danger")
        return redirect(url_for('admin_dashboard'))
    
    if lot.occupied_spots > 0:
        flash("Cannot delete Parking Lot with occupied spots!", "warning")
        return redirect(url_for('admin_dashboard'))

    db.session.delete(lot)
    db.session.commit()
    flash("Parking Lot deleted successfully!", "success")
    return redirect(url_for('admin_dashboard'))



# -------------------------
# EDIT PARKING LOT-ADMIN
# -------------------------
@app.route('/admin/edit_parking_lot/<int:lot_id>', methods=['GET', 'POST'])
@admin_required # Apply admin_required decorator
def edit_parking(lot_id):
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        flash("Parking Lot not found!", "danger")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        lot.area_type = request.form.get('area_type')
        lot.address = request.form.get('address')
        lot.primelocation_name = request.form.get('primelocation_name')
        lot.price_per_hr = float(request.form.get('price_per_hr'))
        lot.city = request.form.get('city')
        lot.pincode = request.form.get('pincode')
        lot.max_spots = int(request.form.get('capacity'))
        lot.occupied_spots = lot.occupied_spots  # admin cannot edit occupied spots updates only when user releases spot
        

        db.session.commit()
        flash("Parking Lot updated successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_parking_lot.html', lot=lot)

#---------------------------
# VIEW PARKING SPOTS-ADMIN
# Get spot details for Occupied Spot (AJAX)
#---------------------------

@app.route('/admin/parking_spots/<int:lot_id>')
@admin_required # Apply admin_required decorator
def parking_spots(lot_id):
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        flash("Parking Lot not found!", "danger")
        return redirect(url_for('admin_dashboard'))

    spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
    return render_template('parking_spots.html', lot=lot, spots=spots)


@app.route('/admin/spot-details/<int:spot_id>')
@admin_required # Apply admin_required decorator
def spot_details(spot_id):
    # For AJAX endpoints, return JSON response directly
    booking = UserBookings.query.filter_by(spot_id=spot_id).order_by(UserBookings.id.desc()).first()
    if not booking:
        return {"error": "No booking found"}, 404

    user = booking.user  # Access user details
    return {
        "user_name": user.user_name,
        "email": user.email_id,
        "vehicle_no": booking.vehicle_no,
        "parking_time": booking.parking_time.strftime("%d-%m-%Y %H:%M"),
        "leaving_time": booking.leaving_time.strftime("%d-%m-%Y %H:%M"),
        "parking_cost": str(booking.parking_cost)
    }

@app.route('/admin/delete_spot/<int:spot_id>', methods=['POST'])
@admin_required # Apply admin_required decorator
def delete_spot(spot_id):
    # For AJAX endpoints, return JSON response directly
    spot = ParkingSpot.query.get(spot_id)
    if not spot:
        return {"error": "Spot not found"}, 404

    if spot.status == 'O':  # Occupied
        return {"error": "Cannot delete occupied spot"}, 400

    lot = ParkingLot.query.get(spot.lot_id)
    db.session.delete(spot)

    # Update lot capacity
    if lot and lot.max_spots > 0:
        lot.max_spots -= 1

    db.session.commit()
    flash("Spot deleted successfully!", "success")
    return redirect(url_for('parking_spots', lot_id=lot.lot_id))


#-----------------------
# ADMIN SUMMARY 
#-----------------------
@app.route('/admin/summary')
@admin_required # Apply admin_required decorator
def admin_summary():
    # Most booked lots overall
    lot_data = (
        db.session.query(ParkingLot.primelocation_name, func.count(UserHistory.id))
        .join(ParkingSpot, ParkingSpot.lot_id == ParkingLot.lot_id)
        .join(UserHistory, UserHistory.spot_id == ParkingSpot.spot_id)
        .group_by(ParkingLot.primelocation_name)
        .order_by(func.count(UserHistory.id).desc())
        .limit(5)
        .all()
    )

    # Prepare data for Chart.js
    labels = [row[0] for row in lot_data]
    counts = [row[1] for row in lot_data]

    # Totals
    total_users = User.query.count()
    total_lots = ParkingLot.query.count()
    total_bookings = UserBookings.query.count()
    total_history = UserHistory.query.count()

    return render_template(
        'admin_summary.html',
        labels=json.dumps(labels),
        counts=json.dumps(counts),
        total_users=total_users,
        total_lots=total_lots,
        total_bookings=total_bookings,
        total_history=total_history
    )

# -------------------------
# ADMIN SEARCH
# -------------------------
@app.route('/admin/search', methods=['GET', 'POST'])
@admin_required # Apply admin_required decorator
def admin_search():
    # Initialize variables to store search results and the currently selected search type.
    user_result = None
    parking_lots_result = None
    search_type = request.form.get('search_type', '')

    if request.method == 'POST':
        if 'submit_user_search' in request.form:
            search_type = 'search_user'
            user_email_id = request.form.get('user_email_id')
            user_id = request.form.get('user_id')

            if not user_email_id and not user_id:
                flash("Please enter either User Email ID or User ID.", "warning")
            else:
                query = User.query
                if user_email_id:
                    query = query.filter_by(email_id=user_email_id)
                if user_id:
                    try:
                        user_id = int(user_id)
                        query = query.filter_by(user_id=user_id)
                    except ValueError:
                        flash("User ID must be a number.", "danger")
                        return render_template('admin_search.html', search_type=search_type)
                
                user_result = query.first()
                if not user_result:
                    flash("No user found with the provided details.", "info")

        elif 'submit_parking_lot_search' in request.form:
            search_type = 'search_parking_lot'
            city = request.form.get('city')
            pincode = request.form.get('pincode')

            if not city and not pincode:
                flash("Please enter either City or Pincode.", "warning")
            else:
                query = ParkingLot.query
                if city:
                    query = query.filter_by(city=city)
                if pincode:
                    query = query.filter_by(pincode=pincode)
                
                parking_lots_result = query.all()
                if not parking_lots_result:
                    flash("No parking lots found with the provided details.", "info")

    return render_template('admin_search.html', 
                           user_result=user_result, 
                           parking_lots_result=parking_lots_result,
                           search_type=search_type)

# -------------------------
# ADMIN: ALL USERS
# -------------------------
@app.route('/admin/users')
@admin_required # Only admins can view all users
def admin_users():
    users = User.query.all() # Fetch all users from the database
    return render_template('admin_allusers.html', users=users)


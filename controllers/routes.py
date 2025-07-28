from flask import render_template, request, redirect, url_for, flash, session
from models.dbmodel import *
from app import app
from werkzeug.security import generate_password_hash, check_password_hash
from slugify import slugify
from datetime import datetime, timedelta
from sqlalchemy import func
import json

from .decorators import login_required, admin_required, only_user, user_access_required
app.permanent_session_lifetime = timedelta(minutes=10)   #set session lifetime to 10 minutes 


# ---------------------------------------------PUBLIC ROUTES------------------------------------------------

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

    # Store user's session
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



# -----------------------------
# NEW HELPER FUNCTION:
# To update spot statuses
# -----------------------------

def update_spot_statuses_and_counts():
    """
    for when admin sees update occupied/available for everybody's bookings that had gone activated or expiered
    in current time"""

    now = datetime.now()
    
    messages_to_flash = []  

    # --- activating bookings  ---
    bookings_to_activate = UserBookings.query.filter(
        UserBookings.parking_time <= now,
        UserBookings.leaving_time > now,
        ParkingSpot.spot_id == UserBookings.spot_id,
        ParkingSpot.status == 'A'
    ).join(ParkingSpot).all()

    for booking in bookings_to_activate:
        if booking.spot:
            booking.spot.status = 'O'
        
    # ---release booking on expiry---
    bookings_to_expire = UserBookings.query.filter(
        UserBookings.leaving_time <= now 
    ).all()

    for booking in bookings_to_expire:
        # move expired booking to UserHistory
        history = UserHistory(
            user_id=booking.user_id,
            spot_id=booking.spot_id,
            booking_time=booking.parking_time,
            leaving_time=booking.leaving_time,
            parking_cost=booking.parking_cost,
            vehicle_no=booking.vehicle_no
        )
        db.session.add(history)
        
        # freeing spot if was occupied
        if booking.spot and booking.spot.status == 'O':
            if booking.spot:
                booking.spot.status = 'A'
        
        db.session.delete(booking)

    # commit all changes in one go
    if bookings_to_activate or bookings_to_expire:
        db.session.commit()
    
    return messages_to_flash # return counts for flash messages

def update_spot_statuses_for_user(user_id):
    """
    this is specific for user if under his session any of his booking got live or expires we will update spot 
    status for current user specifically only and then also give him a flash message the downside is here that if 
    status updates happened under admin session or search_parking route that uses helper to update all of users 
    booking based on booking time period this user will not get flash message"""

    now = datetime.now()
    
    messages_to_flash = []  

    # --- activating bookings for current user in session only---
    bookings_to_activate = UserBookings.query.filter(
        UserBookings.user_id==user_id,
        UserBookings.parking_time <= now,
        UserBookings.leaving_time > now,
        ParkingSpot.spot_id == UserBookings.spot_id,
        ParkingSpot.status == 'A'
    ).join(ParkingSpot).all()

    for booking in bookings_to_activate:
        if booking.spot:
            booking.spot.status = 'O'
    
    if len(bookings_to_activate) > 0:
        messages_to_flash.append(("info", f"{len(bookings_to_activate)} of your bookings are now active. Please proceed to your spot."))
    
    # ---release booking on expiry---
    bookings_to_expire = UserBookings.query.filter(
        UserBookings.user_id==user_id,
        UserBookings.leaving_time <= now 
    ).all()

    for booking in bookings_to_expire:
        # move expired booking to UserHistory
        history = UserHistory(
            user_id=booking.user_id,
            spot_id=booking.spot_id,
            booking_time=booking.parking_time,
            leaving_time=booking.leaving_time,
            parking_cost=booking.parking_cost,
            vehicle_no=booking.vehicle_no
        )
        db.session.add(history)
        
        # freeing spot if was occupied
        if booking.spot and booking.spot.status == 'O':
            booking.spot.status = 'A'
        
        db.session.delete(booking)
    
    if len(bookings_to_expire) > 0:
        messages_to_flash.append(("warning", f"{len(bookings_to_expire)} of your past bookings have expired and are moved to history. Please evacuate the parking spot if you haven't already."))

    # commit all changes in one go
    if bookings_to_activate or bookings_to_expire:
        db.session.commit()
    
    return messages_to_flash # return flash messages list


# ---------------------------------------------USER ROUTES------------------------------------------------

# -------------------------
# USER HOME 
# -------------------------
@app.route('/<int:user_id>-<slug>/home')
@login_required          
@user_access_required    
@only_user               
def user_home(user_id, slug, user): 
    cities = [row[0] for row in db.session.query(ParkingLot.city).distinct().all()]

    now = datetime.now()  

    # calling helper function if users spot freed/occupied right before this action
    status_messages = update_spot_statuses_for_user(user_id)
    for category, message in status_messages:
        flash(message, category)
    
    # fetch active bookings (after updates)
    active_bookings = UserBookings.query.filter_by(user_id=user.user_id).all()

    # recent history
    recent_history = UserHistory.query.filter_by(user_id=user.user_id).order_by(UserHistory.id.desc()).limit(5).all()

    return render_template('user_home1.html', user=user, cities=cities,
                           current_bookings=active_bookings, recent_history=recent_history, now=now)

# ... (release_booking, profile, user_history, search_parking, book_spot) ...

@app.route('/<int:user_id>-<slug>/release_booking/<int:booking_id>', methods=['POST'])
@login_required
@only_user
@user_access_required
def release_booking(user_id, slug, user, booking_id):
    booking = UserBookings.query.get(booking_id)
    
    # calling helper function if users spot freed/occupied right before this action different flashing logic here
    status_messages = update_spot_statuses_for_user(user_id)
    
    for category, message in status_messages:
        if "expired" in message:
            flash("Could not complete the action, your booking had already expired", category)
            return redirect(url_for('user_home', user_id=session['user_id'], slug=slugify(session['username'])))
        if "active" in message:
            flash("Could not cancel booking, your booking had turned active. Use release action to free spot", category)
            return redirect(url_for('user_home', user_id=session['user_id'], slug=slugify(session['username'])))
    
    # incase where booking is already gone through admin session statuse message is empty so will proceed to try to get this booking to history but since not exists in db crash
    booking = UserBookings.query.get(booking_id)
    if not booking: 
        flash("Booking not found or already processed (e.g., expired and moved to history).", "warning")
        return redirect(url_for('user_home', user_id=session['user_id'], slug=slugify(session['username'])))
    
    # determine if it's a future booking being cancelled or an active one being released
    now = datetime.now()
    is_future_booking = booking.parking_time > now

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

    # free the parking spot
    if booking.spot:
        booking.spot.status = 'A' #make spot Physically Available

    db.session.delete(booking)
    db.session.commit()
    
    if is_future_booking:
        flash("Future booking cancelled successfully!", "success")
    else:
        flash("Booking released successfully!", "success")

    return redirect(url_for('user_home', user_id=session['user_id'], slug=slugify(session['username'])))


# -------------------------
# PROFILE-USER (MODIFIED)
# -------------------------
@app.route('/<int:user_id>-<slug>/profile', methods=['GET', 'POST'])
@login_required
@user_access_required

@only_user # Ensure this is a non-admin user's profile
def profile(user_id, slug, user): # 'user' object is injected

    # calling helper function if users spot freed/occupied right before this action
    status_messages = update_spot_statuses_for_user(user_id)
    for category, message in status_messages:
        flash("Please check in home, "+ message, category)

    if request.method == "POST":
        action = request.form.get('action')

        if action == 'update_name':
            user.user_name = request.form.get('username')
            session['username'] = user.user_name #update session username too
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
            # check for any active or future bookings by this user
            # a user cannot delete if they have any active/future bookings
            # an active/future booking is one whose leaving_time is in the future
            active_bookings = UserBookings.query.filter(
                UserBookings.user_id == user.user_id,
                UserBookings.leaving_time > datetime.now()
            ).first()
            if active_bookings:
                flash("You have active or future bookings. Please release them before deleting your account.", "warning")
                return redirect(url_for('profile', user_id=user.user_id, slug=slugify(user.user_name)))
            
            # Free up any spots that were physically occupied by this user (if any)
            # This is important if the user's last booking expired but they didn't release it.
            occupied_spots_by_user = ParkingSpot.query.join(UserBookings).filter(
                UserBookings.user_id == user.user_id,
                ParkingSpot.status == 'O' # Only care about physically occupied spots cause others are already A
            ).all()

            for spot in occupied_spots_by_user:
                spot.status = 'A' # Make spots available

            # Delete user's history & bookings (explicitly, even if cascade delete is set up)
            UserBookings.query.filter_by(user_id=user.user_id).delete()
            UserHistory.query.filter_by(user_id=user.user_id).delete()
            
            db.session.delete(user)
            db.session.commit()

            session.clear()
            flash("Your account and all data have been deleted.", "success")
            return redirect(url_for('home'))

        db.session.commit() # Commit changes for update actions
        return redirect(url_for('profile', user_id=user.user_id, slug=slugify(user.user_name)))

    return render_template('profile.html', user=user)


#--------------------------
# USER HISTORY
#--------------------------
@app.route('/<int:user_id>-<slug>/history')
@login_required
@user_access_required
@only_user
def user_history(user_id, slug, user): 

    # calling helper function if users spot freed/occupied right before this action
    status_messages = update_spot_statuses_for_user(user_id)
    for category, message in status_messages:
        flash("Please check in home, "+ message, category)

    # Fetch full history for this user
    user_history = UserHistory.query.filter_by(user_id=user.user_id).order_by(UserHistory.id.desc()).all()

    return render_template('user_history.html', user=user, user_history=user_history)


# ------------------------
# SEARCH PARKING-USER
# ------------------------
@app.route('/<int:user_id>-<slug>/search-parking', methods=['GET', 'POST'])
@login_required
@user_access_required

@only_user
def search_parking(user_id, slug, user):
    cities = [row[0] for row in db.session.query(ParkingLot.city).distinct().all()]

    # calling helper function if users spot or anyothers spot freed/occupied  right before this action
    status_messages = update_spot_statuses_for_user(user_id)
    update_spot_statuses_and_counts()
    for category, message in status_messages:
        flash("Please check in home, "+ message, category)
    
    if request.method == 'POST':
        city = request.form.get('city')
        pincode = request.form.get('pincode')

        query = ParkingLot.query
        if city:
            query = query.filter_by(city=city)
        if pincode:
            query = query.filter_by(pincode=pincode)

        parking_lots = query.all()
        # for each lot, calculate total, physically occupied, and booked spots dynamically
        lots_with_stats = []
        for lot in parking_lots:
            total_spots = ParkingSpot.query.filter_by(lot_id=lot.lot_id).count()
            # count spots that are physically occupied (status 'O')
            occupied_physical_spots = ParkingSpot.query.filter_by(lot_id=lot.lot_id, status='O').count()
            
            # count spots that are currently booked (future or present)
            # this is the count of spots that are 'unavailable for new bookings'
            booked_spots_count = UserBookings.query.join(ParkingSpot).filter(
                ParkingSpot.lot_id == lot.lot_id,
                UserBookings.leaving_time > datetime.now() # booking is not yet expired
            ).count()

            lots_with_stats.append({
                'lot': lot,
                'total_spots': total_spots,
                'occupied_physical_spots': occupied_physical_spots, # New stat for physical occupancy
                'booked_spots_count': booked_spots_count # Number of spots currently unavailable for new bookings
            })

        return render_template('search_parking.html', user=user, parking_lots_with_stats=lots_with_stats, cities=cities)

    return render_template('search_parking.html', user=user, parking_lots_with_stats=None, cities=cities)


# ------------------------
# BOOK AND CONFIRM SPOT-USER
# ------------------------
@app.route('/<int:user_id>-<slug>/book-spot/<int:lot_id>', methods=['GET', 'POST'])
@login_required
@user_access_required

@only_user
def book_spot(user_id, slug, lot_id, user):
    lot = ParkingLot.query.get(lot_id)
    #no need for status_update_check here cause overlapping times already checked
    if not lot:
        flash("Parking lot not found!", "danger")
        return redirect(url_for('search_parking', user_id=user.user_id, slug=slugify(user.user_name)))

    estimated_price = None
    vehicle_no = parking_time = leaving_time = None
    is_preview_mode = False 
    conflicting_bookings_info = [] # this list will only be populated if "all" spots are conflicting
    is_any_spot_available_for_period = False # Intitially false cause if available we set it to true

    if request.method == 'POST':
        vehicle_no = request.form.get('vehicle_no')
        parking_time_str = request.form.get('parking_time')
        leaving_time_str = request.form.get('leaving_time')
        action = request.form.get('action')  # 'preview' or 'confirm'

        parking_time = datetime.fromisoformat(parking_time_str)
        leaving_time = datetime.fromisoformat(leaving_time_str)

        now = datetime.now()
        limit = now + timedelta(days=10) #booking period must be within next 10 days from now

        if parking_time <= now:
            flash("Parking start time must be in the future!", "warning")
            return render_template('book_spot.html', user=user, lot=lot, 
                                   vehicle_no=vehicle_no, parking_time=parking_time, leaving_time=leaving_time,
                                   is_preview_mode=is_preview_mode, conflicting_bookings_info=conflicting_bookings_info,
                                   is_any_spot_available_for_period=is_any_spot_available_for_period) 

        if leaving_time <= parking_time:
            flash("Leaving time must be later than parking time!", "warning")
            return render_template('book_spot.html', user=user, lot=lot, 
                                   vehicle_no=vehicle_no, parking_time=parking_time, leaving_time=leaving_time,
                                   is_preview_mode=is_preview_mode, conflicting_bookings_info=conflicting_bookings_info,
                                   is_any_spot_available_for_period=is_any_spot_available_for_period) 
        if leaving_time > limit:
            flash("The booking period must be under next 15 days from now!", "warning")
            return render_template('book_spot.html', user=user, lot=lot, 
                                   vehicle_no=vehicle_no, parking_time=parking_time, leaving_time=leaving_time,
                                   is_preview_mode=is_preview_mode, conflicting_bookings_info=conflicting_bookings_info,
                                   is_any_spot_available_for_period=is_any_spot_available_for_period) 
            

        # calculate cost
        hours = (leaving_time - parking_time).total_seconds() / 3600
        estimated_price = round(hours * lot.price_per_hr, 2)

        # --- check for overall availability for the time period ---
        all_spots_in_lot = ParkingSpot.query.filter_by(lot_id=lot_id).all()
        
        available_spot_ids_for_period = [] 
        # conflicting_bookings_info is already initialized at the top of the POST block

        for spot_candidate in all_spots_in_lot:
            overlapping_bookings_for_spot = UserBookings.query.filter(  # find overlapping booking for user's given time period
                UserBookings.spot_id == spot_candidate.spot_id,
                UserBookings.parking_time < leaving_time,  
                UserBookings.leaving_time > parking_time   
            ).all()

            if not overlapping_bookings_for_spot:                        #if no overlapping booking add this spot to available
                available_spot_ids_for_period.append(spot_candidate.spot_id)
            else:
                # only populate conflicting_bookings_info if this spot is actually unavailable.
                # we will only display this list if "all" spots are unavailable.
                for conflict in overlapping_bookings_for_spot:
                    conflicting_bookings_info.append({
                        'spot_id': spot_candidate.spot_id,
                        'parking_time': conflict.parking_time.strftime('%Y-%m-%d %H:%M'),
                        'leaving_time': conflict.leaving_time.strftime('%Y-%m-%d %H:%M')
                    })
        
        # will be false if available_spot_ids_for_period is empty i.e when no spot_canditate was available in timeperiod
        is_any_spot_available_for_period = bool(available_spot_ids_for_period)
        
        if not is_any_spot_available_for_period: # if (not false) evaluats to true 
            flash("No spots are available for the selected time period in this parking lot. Please adjust your times.", "danger")
            is_preview_mode = True 
            return render_template('book_spot.html', user=user, lot=lot, estimated_price=estimated_price,
                                   vehicle_no=vehicle_no, parking_time=parking_time, leaving_time=leaving_time,
                                   is_preview_mode=is_preview_mode, conflicting_bookings_info=conflicting_bookings_info,
                                   is_any_spot_available_for_period=is_any_spot_available_for_period) # <-- Pass new var

        if action == 'confirm':  # finalise booking
            selected_spot_id = available_spot_ids_for_period[0] 
            spot = ParkingSpot.query.get(selected_spot_id) 

            if not spot:    #in case spot deleted by admin while a user was midway confirming
                flash("The selected spot is no longer available. Please try again or choose different times.", "danger")
                return redirect(url_for('book_spot', user_id=user.user_id, slug=slugify(user.user_name), lot_id=lot_id))

            recheck_overlapping = UserBookings.query.filter(
                UserBookings.spot_id == spot.spot_id,
                UserBookings.parking_time < leaving_time,
                UserBookings.leaving_time > parking_time
            ).first()

            if recheck_overlapping:
                flash("The selected spot became unavailable just now. Please try again or choose different times.", "danger")
                return redirect(url_for('book_spot', user_id=user.user_id, slug=slugify(user.user_name), lot_id=lot_id))

            booking = UserBookings(
                user_id=user.user_id,
                spot_id=spot.spot_id,
                parking_time=parking_time,
                leaving_time=leaving_time,
                parking_cost=estimated_price,
                vehicle_no=vehicle_no
            )

            db.session.add(booking)
            db.session.commit()

            flash(f"Booking confirmed! Spot {spot.spot_id} is booked for you. Total cost: ₹ {estimated_price}", "success")
            return redirect(url_for('user_home', user_id=user.user_id, slug=slugify(user.user_name)))
        
        elif action == 'preview': 
            is_preview_mode = True 
            
    return render_template('book_spot.html',user=user, lot=lot, estimated_price=estimated_price,
                           vehicle_no=vehicle_no, parking_time=parking_time, leaving_time=leaving_time,
                           is_preview_mode=is_preview_mode, conflicting_bookings_info=conflicting_bookings_info,
                           is_any_spot_available_for_period=is_any_spot_available_for_period)
#-----------------------
# USER SUMMARY 
#-----------------------
@app.route('/<int:user_id>-<slug>/summary')
@login_required
@user_access_required

@only_user
def user_summary(user_id, slug, user):

    # calling helper function if users spot freed/occupied right before this action
    status_messages = update_spot_statuses_and_counts()
    for category, message in status_messages:
        flash("Please check in home, "+ message, category)
    
    # Group bookings by parking lot name from history
    data = (
        db.session.query(ParkingLot.primelocation_name, func.count(UserHistory.id))
        .join(ParkingSpot, ParkingSpot.lot_id == ParkingLot.lot_id)
        .join(UserHistory, UserHistory.spot_id == ParkingSpot.spot_id)
        .filter(UserHistory.user_id == user.user_id)
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
@admin_required
def admin_dashboard():
    # --- call the new helper function to update statuses ---
    update_spot_statuses_and_counts() # we don't flash messages of user to admin here (has a drawback)
    
    parking_lots = ParkingLot.query.all()
    
    lots_with_stats = []
    for lot in parking_lots:
        total_spots = ParkingSpot.query.filter_by(lot_id=lot.lot_id).count()
        occupied_physical_spots = ParkingSpot.query.filter_by(lot_id=lot.lot_id, status='O').count()
        
        lots_with_stats.append({
            'lot': lot,
            'total_spots': total_spots,
            'occupied_physical_spots': occupied_physical_spots
        })

    return render_template('admin_dashboard.html', lots_with_stats=lots_with_stats)

#--------------------------
# EDIT PROFILE-ADMIN
#--------------------------
@app.route('/admin/profile', methods=['GET', 'POST'])
@admin_required
def admin_profile():
    user = User.query.get(session['user_id'])

    if request.method == "POST":
        action = request.form.get('action')

        if action == 'update_name':
            user.user_name = request.form.get('username')
            session['username'] = user.user_name
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
# ADD PARKING LOT-ADMIN
# -------------------------
@app.route('/admin/add_parking_lot', methods=['GET', 'POST'])
@admin_required
def add_parking():
    if request.method == 'POST':
        area_type = request.form.get('area_type')
        address = request.form.get('address')
        prime_loc = request.form.get('primelocation_name')
        price_per_hr = float(request.form.get('price_per_hr'))
        city = request.form.get('city')
        pincode = request.form.get('pincode')
        capacity = int(request.form.get('capacity')) 

        if capacity < 0:
            flash("Capacity cannot be negative.", "danger")
            return render_template('add_parking_lot.html')

        new_lot = ParkingLot(area_type=area_type, city=city, primelocation_name=prime_loc,
                             price_per_hr=price_per_hr, address=address, pincode=pincode)

        db.session.add(new_lot)
        db.session.flush() # Get lot_id before commit

        # --- loop to add spots based on capacity ---
        for _ in range(capacity):
            db.session.add(ParkingSpot(lot_id=new_lot.lot_id, status='A')) 

        db.session.commit()    

        flash(f"Parking Lot added successfully with {capacity} spots!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('add_parking_lot.html')


# -------------------------
# DELETE PARKING LOT-ADMIN
# -------------------------
@app.route('/admin/delete_parking_lot/<int:lot_id>')
@admin_required
def delete_parking(lot_id):
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        flash("Parking Lot not found!", "danger")
        return redirect(url_for('admin_dashboard'))
    
    # check for any active (future or current) bookings associated with spots in this lot
    active_bookings_in_lot = UserBookings.query.join(ParkingSpot).filter(
        ParkingSpot.lot_id == lot_id,
        UserBookings.leaving_time > datetime.now() 
    ).first()

    if active_bookings_in_lot:
        flash("Cannot delete Parking Lot with active (future or current) bookings! Please ensure all spots are free.", "warning")
        return redirect(url_for('admin_dashboard'))

    # delete all associated parking spots first (cascade="all, delete-orphan" on relationship handles this)
    # parkingSpot.query.filter_by(lot_id=lot_id).delete()   #this is handled by cascade on lot.spots relationship
    db.session.delete(lot)
    db.session.commit()
    flash("Parking Lot deleted successfully!", "success")
    return redirect(url_for('admin_dashboard'))


# -------------------------
# EDIT PARKING LOT-ADMIN
# -------------------------
@app.route('/admin/edit_parking_lot/<int:lot_id>', methods=['GET', 'POST'])
@admin_required
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
        # removed: max_spots and occupied_spots from form processing
        
        db.session.commit()
        flash("Parking Lot updated successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_parking_lot.html', lot=lot)

# ---------------------------
# VIEW PARKING SPOTS-ADMIN (MODIFIED)
#---------------------------
@app.route('/admin/parking_spots/<int:lot_id>')
@admin_required
def parking_spots(lot_id):
    # call the new helper function to update statuses ---
    update_spot_statuses_and_counts() 
    
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        flash("Parking Lot not found!", "danger")
        return redirect(url_for('admin_dashboard'))

    all_spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
    
    spots_for_display = []
    now = datetime.now()

    for spot in all_spots:
        display_status = spot.status  # display status for spot color not text at start same as spot.status
        
        # check for any future bookings
        future_bookings = UserBookings.query.filter(
            UserBookings.spot_id == spot.spot_id,
            UserBookings.parking_time > now 
        ).first()

        if spot.status == 'O':
            display_status = 'O'
        elif spot.status == 'A' and future_bookings:
            display_status = 'F' # F for available but Booked for future color
        else:
            display_status = 'A'

        spots_for_display.append({
            'spot_id': spot.spot_id,
            'status': spot.status,  # actual status shown will be A or O only
            'display_status': display_status # Status for coloring the grid A, O, F
        })

    total_spots_count = len(all_spots)
    occupied_physical_spots_count = sum(1 for spot in all_spots if spot.status == 'O')

    return render_template('parking_spots.html', lot=lot, spots=spots_for_display, 
                           total_spots_count=total_spots_count,
                           occupied_physical_spots_count=occupied_physical_spots_count)

# ---------------------------
# FETCH DETAIL OF SPOT - ADMIN
# ---------------------------
@app.route('/admin/spot-details/<int:spot_id>')   
@admin_required
def spot_details(spot_id):

    # in case users spot status got updated right before this action
    update_spot_statuses_and_counts()

    spot = ParkingSpot.query.get(spot_id)
    if not spot:
        return {"error": "Spot not found"}, 404

    now = datetime.now()

    current_booking = UserBookings.query.filter(
        UserBookings.spot_id == spot_id,
        UserBookings.parking_time <= now,
        UserBookings.leaving_time > now
    ).first()

    future_bookings = UserBookings.query.filter(
        UserBookings.spot_id == spot_id,
        UserBookings.parking_time > now # starts in the future
    ).order_by(UserBookings.parking_time.asc()).all()

    response_data = {
        'spot_id': spot.spot_id, 
        'spot_status': spot.status, 
        'current_occupied': False, # Default to False
        'current_booking_details': None, # Default to None
        'future_bookings_details': [], # Default to empty list
        'is_deletable': False # Default to False we set True if conditions met
    }

    # determine if the spot is deletable
    # a spot is deletable ONLY if it has no current or future bookings.
    is_deletable = not current_booking and not future_bookings
    response_data['is_deletable'] = is_deletable 

    if current_booking:
        user = current_booking.user
        response_data['current_occupied'] = True
        response_data['current_booking_details'] = {
            "user_name": user.user_name,
            "email": user.email_id,
            "vehicle_no": current_booking.vehicle_no,
            "parking_time": current_booking.parking_time.strftime("%d-%m-%Y %H:%M"),
            "leaving_time": current_booking.leaving_time.strftime("%d-%m-%Y %H:%M"),
            "parking_cost": str(current_booking.parking_cost)
        }

    if future_bookings:
        for fb in future_bookings:
            response_data['future_bookings_details'].append({
                "user_name": fb.user.user_name, # Access user via relationship
                "vehicle_no": fb.vehicle_no,
                "parking_time": fb.parking_time.strftime("%d-%m-%Y %H:%M"),
                "leaving_time": fb.leaving_time.strftime("%d-%m-%Y %H:%M")
            })
    
    # returning the structured response_data
    return response_data, 200


# ---------------------------
# ADD SPOT TO PARKING LOT- INSIDE parking_lot MANAGE PAGE
# ---------------------------
@app.route('/admin/add_spot/<int:lot_id>', methods=['POST'])
@admin_required
def add_spot(lot_id):
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        flash("Parking Lot not found!", "danger")
        return redirect(url_for('admin_dashboard'))
    
    new_spot = ParkingSpot(lot_id=lot.lot_id, status='A')
    db.session.add(new_spot)
    db.session.commit()
    flash(f"New spot added to {lot.primelocation_name}!", "success")
    return redirect(url_for('parking_spots', lot_id=lot.lot_id))

# ---------------------------
# DELETE SPOT IN PARKING LOT- INSIDE parking_lot MANAGE PAGE
# ---------------------------
@app.route('/admin/delete_spot/<int:spot_id>', methods=['POST'])
@admin_required
def delete_spot(spot_id):
    spot = ParkingSpot.query.get(spot_id)
    if not spot:
        return {"error": "Spot not found"}, 404

    # check if there are any active bookings (current or future) for this spot
    active_booking_for_spot = UserBookings.query.filter(
        UserBookings.spot_id == spot_id,
        UserBookings.leaving_time > datetime.now() # Booking is not yet expired
    ).first()

    if active_booking_for_spot:
        flash(f"Cannot delete spot {spot_id} as it has an active booking. Please ensure the booking is released first.", "danger")
        return redirect(url_for('parking_spots', lot_id=spot.lot_id))
            
    lot = ParkingLot.query.get(spot.lot_id) 
    db.session.delete(spot)
    db.session.commit()
    flash("Spot deleted successfully!", "success")
    return redirect(url_for('parking_spots', lot_id=lot.lot_id))


#-----------------------
# ADMIN SUMMARY
#-----------------------
@app.route('/admin/summary')
@admin_required
def admin_summary():
    # most booked lots from booking history only
    lot_data = (
        db.session.query(
            ParkingLot.primelocation_name, 
            func.count(UserHistory.id) # count only from userhistory
        )
        .join(ParkingSpot, ParkingSpot.lot_id == ParkingLot.lot_id)
        .join(UserHistory, UserHistory.spot_id == ParkingSpot.spot_id)
        .group_by(ParkingLot.primelocation_name)
        .order_by(func.count(UserHistory.id).desc())
        .limit(5)
        .all()
    )

    # prepare data for Chart.js
    labels = [row[0] for row in lot_data]
    counts = [row[1] for row in lot_data]

    # totals counts for display
    total_users = User.query.count()
    total_lots = ParkingLot.query.count()
    
    # total bookings, currently booked either occupied or future
    total_bookings = UserBookings.query.count() 
    
    # Total history records
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
@admin_required
def admin_search():
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
                
                parking_lots = query.all()
                # calc stats for search results
                lots_with_stats = []
                for lot in parking_lots:
                    total_spots = ParkingSpot.query.filter_by(lot_id=lot.lot_id).count()
                    occupied_physical_spots = ParkingSpot.query.filter_by(lot_id=lot.lot_id, status='O').count()
                    lots_with_stats.append({
                        'lot': lot,
                        'total_spots': total_spots,
                        'occupied_physical_spots': occupied_physical_spots
                    })
                parking_lots_result = lots_with_stats # Assign the list with stats

                if not parking_lots_result:
                    flash("No parking lots found with the provided details.", "info")

    return render_template('admin_search.html', 
                           user_result=user_result, 
                           parking_lots_result=parking_lots_result, # now contains stats
                           search_type=search_type)

# -------------------------
# ADMIN: ALL USERS
# -------------------------
@app.route('/admin/users')
@admin_required # 
def admin_users():
    users = User.query.all() # fetch all users from the database
    return render_template('admin_allusers.html', users=users)
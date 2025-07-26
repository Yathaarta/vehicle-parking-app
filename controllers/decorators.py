from functools import wraps
from flask import flash, redirect, url_for, abort, session, current_app
from models.dbmodel import User 
from slugify import slugify 


# --------------------------- removing redundant checks with decorators-------------------------------------

#for accesing routes which require to be logged in
def login_required(f):           
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first!", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


 #for accessing routes only for admins 
def admin_required(f):         
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            flash("Access denied! Admins only.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


#for accessing routes only for users
def only_user(f):               
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('is_admin'):
            flash("Access denied! Users only.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


#for checking if user_id present in url, 1
#for checking if a user with that user_id exists in db, 2
#for checking if user_id in url is that of currently logged in user in session or not, 3
def user_access_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id_from_url = kwargs.get('user_id') 
        #1
        if user_id_from_url is None:    
            current_app.logger.error(
                "user_access_required decorator applied to a route "
                "without 'user_id' in its URL arguments."
            )
            abort(500, description="Internal error: User ID missing from URL.")
        #2
        user = User.query.get(user_id_from_url)  
        if not user:
            flash("User not found!", "danger")
            return redirect(url_for('login'))
        #3
        current_session_user_id = session.get('user_id')
        if current_session_user_id != user.user_id:
            flash(f"Session changed! Please login again", "warning")
            return redirect(url_for('login'))
            
        # if all checks pass, inject the user object
        kwargs['user'] = user 
        return f(*args, **kwargs)
    return wrapper



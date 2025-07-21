from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from models.dbmodel import *
from app import app
from werkzeug.security import generate_password_hash, check_password_hash
@app.route('/')
def home():
    return render_template('home2.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method=='GET':
        return render_template('login.html')
    else:
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter(User.email_id == email).first()

        if not user:
            flash("User does not exist, Please register", "warning")
            return redirect(url_for('register'))

        if not check_password_hash(user.pass_wd, password):
            flash("Incorrect Password", "warning")
            return redirect(url_for('login'))

        flash("Login Successful", "success")
        return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    else:
        username= request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        cnf_password=request.form.get('confirm_password')
        existing_user = User.query.filter(User.email_id == email).first()

        if password!=cnf_password:
            flash("Both passwords must match", "warning")
            return redirect(url_for('register'))
        
        if existing_user:
            flash("A User with this email id already exists!", "warning")
            return redirect(url_for('register'))
       
        passhash = generate_password_hash(password)
        new_user = User(email_id=email, pass_wd=passhash, user_name=username)
        db.session.add(new_user)
        db.session.commit()

        flash("User registered successfully, Please Login to continue", "success")
        return redirect(url_for('login'))
    








from flask import Blueprint, render_template, request, flash, redirect, url_for, session, current_app
from passlib.hash import pbkdf2_sha256
import pyotp
import requests
import uuid
from datetime import datetime
from bson.objectid import ObjectId
from Carely.mongodb_database.connection import client
from Carely.app.utils import send_email, login_required

# Create the Blueprint
auth_bp = Blueprint('auth', __name__)

# Initialize Collections
company_collection = client.Carely.Customer
admin_collection = client.Carely.Admin


@auth_bp.route('/login')
def login():
    return render_template('login.html', RECAPTCHA_SITE_KEY=current_app.config['RECAPTCHA_SITE_KEY'])


@auth_bp.route('/user/login', methods=['POST'])
def user_login():
    if request.method == 'POST':
        # Verify reCAPTCHA
        recaptcha_response = request.form.get('g-recaptcha-response')
        data = {
            'secret': current_app.config['RECAPTCHA_SECRET_KEY'],
            'response': recaptcha_response
        }

        try:
            response = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
            result = response.json()

            if not result.get('success'):
                flash('Invalid reCAPTCHA. Please try again.', 'error')
                return redirect(url_for('auth.login'))
        except requests.exceptions.RequestException:
            flash('Error connecting to reCAPTCHA service.', 'error')
            return redirect(url_for('auth.login'))

        email = request.form.get('email')
        password = request.form.get('password')

        user = company_collection.find_one({"email": email})

        if user and pbkdf2_sha256.verify(password, user['password']):
            # Generate a valid base32 secret key for TOTP
            totp_secret = pyotp.random_base32()
            totp = pyotp.TOTP(totp_secret)
            otp = totp.now()

            session['totp_secret'] = totp_secret
            session['verify'] = True
            session['email'] = email

            send_email(email, 'Log In Verification Code', f'Your Verification Code is {otp}')

            return redirect(url_for('auth.two_factor_authentication_login'))
        else:
            flash('Invalid email or password.', 'error')
            return redirect(url_for('auth.login'))

    return render_template('login.html')


@auth_bp.route('/user/signup/', methods=['GET', 'POST'])
def user_signup():
    if request.method == 'POST':
        # Verify reCAPTCHA
        recaptcha_response = request.form.get('g-recaptcha-response')
        data = {
            'secret': current_app.config['RECAPTCHA_SECRET_KEY'],
            'response': recaptcha_response
        }

        try:
            response = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
            result = response.json()

            if not result.get('success'):
                flash('Invalid reCAPTCHA. Please try again.', 'error')
                return redirect(url_for('auth.user_signup'))
        except requests.exceptions.RequestException:
            flash('Error verifying reCAPTCHA.', 'error')
            return redirect(url_for('auth.user_signup'))

        try:
            user = {
                "_id": uuid.uuid4().hex[:24],
                "name": request.form.get('name'),
                "email": request.form.get('email'),
                "phone_no": request.form.get('phone_no'),
                "password": request.form.get('password'),
            }

            user['password'] = pbkdf2_sha256.hash(user['password'])

            if company_collection.find_one({"$or": [{"email": user['email']}, {"name": user['name']}]}):
                flash("Information filled is already in use.", "error")
                return redirect(url_for('auth.user_signup'))
            else:
                company_collection.insert_one(user)
                flash("User signed up successfully. Please log in.", "success")
                return redirect(url_for('auth.login'))
        except Exception as e:
            flash(f"Error occurred: {str(e)}", "error")
            return redirect(url_for('auth.user_signup'))

    return render_template('signup.html', RECAPTCHA_SITE_KEY=current_app.config['RECAPTCHA_SITE_KEY'])


@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = company_collection.find_one({"email": email})

        if user:
            totp_secret = pyotp.random_base32()
            totp = pyotp.TOTP(totp_secret)
            otp = totp.now()

            send_email(user['email'], 'Change Password Verification Code', f'Your Verification Code is {otp}')

            session['reset_email'] = email
            session['totp_secret'] = totp_secret

            return redirect(url_for('auth.verify_otp'))
        else:
            flash('Email not found.', 'error')
            return render_template('forgot_pass.html')

    return render_template('forgot_pass.html')


@auth_bp.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'reset_email' not in session:
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        otp = request.form.get('otp')
        email = session['reset_email']
        totp_secret = session.get('totp_secret')

        user = company_collection.find_one({"email": email})

        if user and totp_secret:
            totp = pyotp.TOTP(totp_secret)
            if totp.verify(otp, valid_window=1):
                session.pop('totp_secret', None)
                return redirect(url_for('auth.change_password'))
            else:
                flash('Invalid OTP.', 'error')
        else:
            flash('Session expired. Please try again.', 'error')
            return redirect(url_for('auth.forgot_password'))

    return render_template('verify_otp.html')


@auth_bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'reset_email' not in session:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        email = session['reset_email']

        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
        else:
            hashed_password = pbkdf2_sha256.hash(new_password)
            company_collection.update_one({'email': email}, {'$set': {'password': hashed_password}})
            flash('Password reset successful. Please log in with your new password.', 'success')
            session.pop('reset_email', None)
            return redirect(url_for('auth.login'))

    return render_template('change_password.html')


@auth_bp.route('/verify_2_fa_login', methods=['GET', 'POST'])
def two_factor_authentication_login():
    if 'verify' not in session:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        otp = request.form.get('otp')
        totp_secret = session.get('totp_secret')
        email = session.get('email')

        if not totp_secret or not email:
            flash('Session expired or invalid. Please log in again.', 'error')
            return redirect(url_for('auth.login'))

        totp = pyotp.TOTP(totp_secret)
        if totp.verify(otp, valid_window=1):
            session['logged_in'] = True
            session['user'] = session['email']

            user = company_collection.find_one({"email": email})
            session['user_id'] = user['_id']

            current_time = datetime.now()
            customer_id = ObjectId(user['_id'])

            customer_login = {
                "_id": uuid.uuid4().hex,
                "customer_id": customer_id,
                "login_date": current_time,
                "logout_date": None,
            }

            try:
                admin_collection.insert_one(customer_login)
                session.pop('verify', None)
                session.pop('totp_secret', None)
                return redirect(url_for('main.homepage'))
            except Exception as e:
                flash(f'Error inserting login record: {str(e)}', 'error')
        else:
            flash('Invalid OTP. Please try again.', 'error')

    return render_template('2_fa.html')


@auth_bp.route('/sign/out')
def sign_out():
    session.clear()
    return redirect('/')


@auth_bp.route('/send_otp', methods=['GET', 'POST'])
@login_required
def send_email_verification():
    email = session['email']
    totp_secret = pyotp.random_base32()
    totp = pyotp.TOTP(totp_secret)
    otp = totp.now()

    # For debugging
    print(f"DEBUG OTP: {otp}")

    session['totp_secret'] = totp_secret
    send_email(email, 'Email Confirmation Verification Code', f'Your Verification Code is {otp}')
    return redirect(url_for('auth.verify_user'))


@auth_bp.route('/verify_user', methods=['GET', 'POST'])
@login_required
def verify_user():
    if request.method == 'POST':
        otp = request.form.get('otp')
        email = session['email']
        totp_secret = session.get('totp_secret')

        user = company_collection.find_one({"email": email})

        if user and totp_secret:
            totp = pyotp.TOTP(totp_secret)
            if totp.verify(otp, valid_window=1):
                session.pop('totp_secret', None)
                session['reset_email'] = email
                return redirect(url_for('auth.change_password'))
            else:
                flash('Invalid OTP.', 'error')
        else:
            flash('Session expired. Please try resending the OTP.', 'error')

    return render_template('verify_user.html')
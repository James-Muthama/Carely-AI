import smtplib
from email.mime.text import MIMEText
from functools import wraps
from flask import session, redirect, current_app

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            return redirect('/')
    return wrap

def send_email(to_address, subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = current_app.config['EMAIL_ADDRESS']
        msg['To'] = to_address

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(current_app.config['EMAIL_ADDRESS'],
                         current_app.config['EMAIL_PASSWORD'])
            server.sendmail(current_app.config['EMAIL_ADDRESS'], to_address, msg.as_string())
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False
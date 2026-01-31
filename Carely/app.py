import os
import smtplib
import uuid
from io import BytesIO
import requests
from email.mime.text import MIMEText
from dotenv import load_dotenv, find_dotenv
from flask import flash, redirect, request, url_for, session, render_template, Flask, send_file, jsonify
from werkzeug.utils import secure_filename
from mongodb_database.connection import client
from passlib.hash import pbkdf2_sha256
import pyotp
from datetime import datetime
from bson.objectid import ObjectId
from functools import wraps
from bson import Binary

from customer_facing_agent.Customer_Agent import CustomerSupportAgent

# Load environment variables from .env file
load_dotenv(find_dotenv())


# Global MCP client instance (you might want to make this a dependency)
mcp_client = None

# FastMCP 2.0 server configuration
FASTMCP_SERVER_BASE_URL = "http://localhost:8000"
FASTMCP_HEALTH_URL = f"{FASTMCP_SERVER_BASE_URL}/health"
FASTMCP_OAUTH_URL = f"{FASTMCP_SERVER_BASE_URL}/oauth2callback"

# Create Flask app 'template_folder' specifies the folder where the HTML templates are stored. 'static_folder'
# specifies the folder where static files (CSS, JS, images) are stored.'static_url_path' sets the URL path that
# serves the static files.
app = Flask(__name__, template_folder="templates", static_folder='static', static_url_path='/')

#session secret key
app.secret_key = os.environ.get("app.secret_key")

# Define allowed IP address
allowed_ip = os.environ.get("allowed_ip")

# Declaration of collections
company_collection = client.Carely.Customer
admin_collection = client.Carely.Admin

# Model API Keys
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Email configuration
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# reCAPTCHA keys
RECAPTCHA_SITE_KEY = os.environ.get("RECAPTCHA_SITE_KEY")
RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY")

#Decorators for checking logged in to access homepage
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            return redirect('/')

    return wrap

# Configuration
UPLOAD_FOLDER = 'uploads'
# Define the allowed extensions for images
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def send_email(to_address, subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_address

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, to_address, msg.as_string())

        return True  # Email sent successfully
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False  # Failed to send email

@app.route('/')
def home():
    session.clear()
    return render_template('index.html')

# Route for displaying login page
@app.route('/login')
def login():
    return render_template('login.html', RECAPTCHA_SITE_KEY=RECAPTCHA_SITE_KEY)


# Route for handling user login
@app.route('/user/login', methods=['POST'])
def user_login():
    if request.method == 'POST':
        # Verify reCAPTCHA
        recaptcha_response = request.form.get('g-recaptcha-response')
        data = {
            'secret': RECAPTCHA_SECRET_KEY,
            'response': recaptcha_response
        }
        response = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
        result = response.json()

        if not result.get('success'):
            flash('Invalid reCAPTCHA. Please try again.', 'error')
            return redirect(url_for('login'))

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

            return redirect(url_for('two_factor_authentication_login'))
        else:
            flash('Invalid email or password.', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

# Route for handling the user signup form submission
@app.route('/user/signup/', methods=['GET', 'POST'])
def user_signup():
    if request.method == 'POST':
        # Verify reCAPTCHA
        recaptcha_response = request.form.get('g-recaptcha-response')
        data = {
            'secret': RECAPTCHA_SECRET_KEY,
            'response': recaptcha_response
        }
        response = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
        result = response.json()

        if not result.get('success'):
            flash('Invalid reCAPTCHA. Please try again.', 'error')
            return redirect(url_for('user_signup'))

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
                return redirect(url_for('user_signup'))
            else:
                company_collection.insert_one(user)
                flash("User signed up successfully. Please log in.", "success")
                return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error occurred: {str(e)}", "error")
            return redirect(url_for('user_signup'))

    return render_template('signup.html', RECAPTCHA_SITE_KEY=RECAPTCHA_SITE_KEY)


@app.route('/forgot_password', methods=['GET', 'POST'])
# function that takes user emil and sends otp code to email
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = company_collection.find_one({"email": email})

        if user:
            # Generate a valid base32 secret key for TOTP
            totp_secret = pyotp.random_base32()

            totp = pyotp.TOTP(totp_secret)
            otp = totp.now()
            send_email(user['email'], 'Change Password Verification Code', f'Your Verification Code is {otp}')

            # Store the TOTP secret in session
            session['reset_email'] = email
            session['totp_secret'] = totp_secret

            return redirect(url_for('verify_otp'))
        else:
            flash('Email not found.', 'error')
            return render_template('forgot_pass.html')
    elif request.method == 'GET':
        return render_template('forgot_pass.html')

    return render_template('forgot_pass.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
# function that takes in user OTP code and verifies the OTP code
def verify_otp():
    if 'reset_email' not in session:
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        otp = request.form.get('otp')
        email = session['reset_email']
        totp_secret = session['totp_secret']
        user = company_collection.find_one({"email": email})

        if user:
            totp = pyotp.TOTP(totp_secret)
            if totp.verify(otp, valid_window=1):
                session.pop('totp_secret', None)
                return redirect(url_for('change_password'))
            else:
                flash('Invalid OTP.', 'error')

    return render_template('verify_otp.html')

@app.route('/change_password', methods=['GET', 'POST'])
# function that runs once the OTP code is valid to allow user to change to
def change_password():
    if 'reset_email' not in session:
        return redirect(url_for('home'))

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
            return redirect(url_for('login'))

    return render_template('change_password.html')

# Checking 2-factor authentication code
@app.route('/verify_2_fa_login', methods=['GET', 'POST'])
def two_factor_authentication_login():
    if 'verify' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        otp = request.form.get('otp')
        totp_secret = session.get('totp_secret')
        email = session.get('email')  # Change session['user'] to session['email']

        if not totp_secret or not email:
            flash('Session expired or invalid. Please log in again.', 'error')
            return redirect(url_for('login'))

        totp = pyotp.TOTP(totp_secret)
        if totp.verify(otp, valid_window=1):
            # Authentication successful, log the user in
            session['logged_in'] = True
            session['user'] = session['email']  # Update session['user'] to user['email']

            user = company_collection.find_one({"email": email})
            session['user_id'] = user['_id']

            # Generate current time as a datetime object
            current_time = datetime.now()  # Fixed: removed extra .datetime
            customer_id = ObjectId(user['_id'])  # Convert to ObjectId

            # Insert into MongoDB
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
                return redirect(url_for('homepage'))
            except Exception as e:
                flash(f'Error inserting login record: {str(e)}', 'error')

        else:
            flash('Invalid OTP. Please try again.', 'error')

    return render_template('2_fa.html')

#admin route
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'GET':
        if request.remote_addr != allowed_ip:
            return redirect(url_for('login'))
        else:
            # Generate a valid base32 secret key for TOTP
            totp_secret = pyotp.random_base32()

            totp = pyotp.TOTP(totp_secret)
            otp = totp.now()

            session['totp_secret'] = totp_secret
            session['admin_verify'] = True

            send_email('james.muthama@strathmore.edu', 'Log In Verification Code', f'Your Verification Code is {otp}')
            return redirect(url_for('verify_admin'))


@app.route('/verify_admin', methods=['GET', 'POST'])
# function that takes in user OTP code and verifies the OTP code
def verify_admin():
    if 'admin_verify' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        otp = request.form.get('otp')
        totp_secret = session['totp_secret']

        totp = pyotp.TOTP(totp_secret)
        if totp.verify(otp, valid_window=1):
            session.pop('admin_verify', None)
            session.pop('totp_secret', None)
            customers = list(company_collection.find({}))  # Fetch all documents in the collection

            admins = list(admin_collection.find({}))  # Fetch all documents in the collection

            return render_template('admin.html', admins=admins, customers=customers)
        else:
            flash('Invalid OTP.', 'error')

    return render_template('verify_admin.html')


#logging out the user
@app.route('/sign/out')
def sign_out():
    session.clear()
    return redirect('/')


# Route for the homepage after successful signup or login
@app.route('/homepage/')
@login_required
def homepage():
    email = session['email']
    user = company_collection.find_one({"email": email})
    session['user'] = user['name']

    return render_template('homepage.html')


@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')


@app.route('/profile_image')
@login_required
def profile_image():
    email = session['email']
    profile_data = company_collection.find_one({'email': email})

    if profile_data and 'profile_image' in profile_data:
        image_data = profile_data['profile_image']
        return send_file(BytesIO(image_data), mimetype='image/jpeg')
    else:
        # Return a default image or a placeholder
        return redirect(url_for('static', filename='images/default_profile_photo.jpg'))


@app.route('/send_otp', methods=['GET', 'POST'])
# function that takes in user OTP code and verifies the OTP code
@login_required
def send_email_verification():
    email = session['email']

    # Generate a valid base32 secret key for TOTP
    totp_secret = pyotp.random_base32()

    totp = pyotp.TOTP(totp_secret)
    otp = totp.now()
    print(otp)

    session['totp_secret'] = totp_secret

    send_email(email, 'Email Confirmation Verification Code', f'Your Verification Code is {otp}')
    return redirect(url_for('verify_user'))


@app.route('/verify_user', methods=['GET', 'POST'])
# function that takes in user OTP code and verifies the OTP code
@login_required
def verify_user():
    if request.method == 'POST':
        otp = request.form.get('otp')
        email = session['email']
        totp_secret = session['totp_secret']
        user = company_collection.find_one({"email": email})

        if user:
            totp = pyotp.TOTP(totp_secret)
            if totp.verify(otp, valid_window=1):
                session.pop('totp_secret', None)
                session['reset_email'] = email
                return redirect(url_for('change_password'))
            else:
                flash('Invalid OTP.', 'error')

    else:
        flash('Check Email for OTP Code', 'error')
        return render_template('verify_user.html')

# Route for uploading an image
@app.route('/upload_image/', methods=['GET', 'POST'])
@login_required
def upload_image():
    if request.method == 'POST':
        if 'image' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        image_file = request.files['image']

        if image_file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)

        if image_file and allowed_image_file(image_file.filename):
            # Secure the filename
            filename = secure_filename(image_file.filename)

            # Read the file content
            image_content = image_file.read()

            # Get user ID from session
            email = session['email']

            # Store the image in the database as binary data
            company_collection.update_one({'email': email}, {'$set': {'profile_image': Binary(image_content)}})

            flash('Image uploaded successfully', 'success')

            return redirect(url_for('profile'))

        else:
            flash('Allowed file types are png, jpg, jpeg, gif', 'error')
            return redirect(request.url)

    # Handle GET request to show the upload form
    return render_template('upload_image.html')

@app.route('/customer_agent')
@login_required
def customer_agent():
    return render_template('customer_agent.html')


def get_or_create_rag_system():
    """Get RAG system from session or create new one with persistence"""
    company_id = session.get('user_id')  # Use user_id as company_id

    if not company_id:
        print("No company ID found in session")
        return None

    # Create a unique key for this company's RAG system
    rag_key = f'RAG_SYSTEM_{company_id}'

    if rag_key not in app.config:
        try:
            print(f"Initializing persistent RAG system for company: {company_id}")
            rag_system = CustomerSupportAgent(
                groq_api_key=GROQ_API_KEY,
                mongodb_client=client,
                company_id=company_id
            )

            # Store the RAG system in app context
            app.config[rag_key] = rag_system

            # Mark as initialized in session
            session['rag_system_initialized'] = True

            return rag_system

        except Exception as e:
            print(f"Error initializing persistent RAG system: {str(e)}")
            return None
    else:
        print(f"Retrieved existing RAG system for company: {company_id}")
        return app.config.get(rag_key)


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    """
    Handle PDF file upload and process it through the persistent RAG system
    """
    if request.method == 'POST':
        try:
            # Check if file was uploaded
            if 'file' not in request.files:
                flash('No file selected', 'error')
                return redirect(request.url)

            file = request.files['file']

            # Check if file was actually selected
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(request.url)

            # Validate file type
            if not allowed_file(file.filename):
                flash('Only PDF files are allowed', 'error')
                return redirect(request.url)

            # Secure the filename
            filename = secure_filename(file.filename)

            # Create unique filename to avoid conflicts
            import uuid
            unique_filename = f"{uuid.uuid4()}_{filename}"
            filepath = os.path.join(UPLOAD_FOLDER, unique_filename)

            # Save the uploaded file
            file.save(filepath)
            flash(f'File {filename} uploaded successfully', 'success')

            # Initialize or get persistent RAG system
            rag_system = get_or_create_rag_system()

            if rag_system is None:
                flash('Error initializing RAG system', 'error')
                os.remove(filepath)  # Clean up uploaded file
                return redirect(request.url)

            # Process the PDF through persistent RAG system
            print(f"Processing PDF through persistent RAG system: {filepath}")
            success = rag_system.upload_file(filepath)

            if success:
                # Mark RAG system as ready
                session['rag_system_ready'] = True
                session['uploaded_filename'] = filename
                session['processed_file_path'] = filepath

                flash(f'Document {filename} processed successfully! You can now ask questions about it.', 'success')

                # Clean up the uploaded file after processing (Chroma has persisted the data)
                try:
                    os.remove(filepath)
                    print("Temporary file cleaned up")
                except:
                    pass

                # Redirect to chat/question interface
                return redirect(url_for('chat_interface'))

            else:
                flash('Error processing the PDF file. Please try again.', 'error')
                os.remove(filepath)  # Clean up uploaded file
                return redirect(request.url)

        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            print(f"Upload error: {str(e)}")

            # Clean up file if it exists
            if 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)

            return redirect(request.url)

    # GET request - show upload form with company's existing documents
    rag_system = get_or_create_rag_system()
    existing_docs = []
    if rag_system:
        existing_docs = rag_system.get_company_documents()
        # Check if RAG system is ready (has processed documents)
        session['rag_system_ready'] = len(existing_docs) > 0

    return render_template('upload_pdf.html',
                           rag_ready=session.get('rag_system_ready', False),
                           uploaded_file=session.get('uploaded_filename'),
                           existing_documents=existing_docs)


@app.route('/ask_question', methods=['POST'])
@login_required
def ask_question():
    """
    Handle questions sent to the persistent RAG system
    """
    try:
        # Get RAG system for this company
        rag_system = get_or_create_rag_system()

        if rag_system is None:
            return jsonify({
                'error': 'RAG system not available',
                'status': 'system_error'
            }), 500

        # Check if company has any processed documents
        company_docs = rag_system.get_company_documents()
        if not company_docs:
            return jsonify({
                'error': 'Please upload a PDF document first',
                'status': 'no_document'
            }), 400

        # Get question from request
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({
                'error': 'No question provided',
                'status': 'invalid_request'
            }), 400

        question = data['question'].strip()
        if not question:
            return jsonify({
                'error': 'Question cannot be empty',
                'status': 'invalid_request'
            }), 400

        # Get answer from persistent RAG system
        answer = rag_system.ask_question(question)

        # Optionally get relevant documents for transparency
        relevant_docs = rag_system.get_relevant_documents(question, k=3)

        return jsonify({
            'answer': answer,
            'question': question,
            'relevant_documents': [
                {
                    'content': doc['content'][:200] + '...' if len(doc['content']) > 200 else doc['content'],
                    'score': doc['relevance_score']
                }
                for doc in relevant_docs
            ],
            'status': 'success'
        })

    except Exception as e:
        print(f"Question processing error: {str(e)}")
        return jsonify({
            'error': f'Error processing question: {str(e)}',
            'status': 'processing_error'
        }), 500


@app.route('/chat_interface')
@login_required
def chat_interface():
    """
    Display the chat interface for asking questions with persistent data
    """
    rag_system = get_or_create_rag_system()

    if rag_system is None:
        flash('Error loading RAG system', 'error')
        return redirect(url_for('upload_file'))

    # Get company's processed documents
    company_docs = rag_system.get_company_documents()

    if not company_docs:
        flash('Please upload a PDF document first', 'warning')
        return redirect(url_for('upload_file'))

    return render_template('chat.html',
                           uploaded_file=session.get('uploaded_filename'),
                           existing_documents=company_docs)


@app.route('/clear_conversation', methods=['POST'])
@login_required
def clear_conversation():
    """
    Clear the conversation history (persistent)
    """
    try:
        rag_system = get_or_create_rag_system()
        if rag_system:
            rag_system.clear_conversation_history()
            return jsonify({'status': 'success', 'message': 'Conversation history cleared'})
        else:
            return jsonify({'status': 'error', 'message': 'RAG system not found'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/reset_rag', methods=['POST'])
@login_required
def reset_rag():
    """
    Reset the RAG system (clear everything including persistent data)
    """
    try:
        company_id = session.get('user_id')
        rag_key = f'RAG_SYSTEM_{company_id}'

        # Get RAG system and delete all data
        rag_system = app.config.get(rag_key)
        if rag_system:
            rag_system.delete_company_data()

        # Clear session data
        session.pop('rag_system_initialized', None)
        session.pofp('rag_system_ready', None)
        session.pop('uploaded_filename', None)
        session.pop('processed_file_path', None)

        # Clear RAG system from app config
        app.config.pop(rag_key, None)

        return jsonify({'status': 'success', 'message': 'RAG system reset successfully'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/rag_status')
@login_required
def rag_status():
    """
    Check the status of the persistent RAG system
    """
    rag_system = get_or_create_rag_system()
    health_status = rag_system.health_check() if rag_system else {}

    return jsonify({
        'company_id': session.get('user_id'),
        'initialized': session.get('rag_system_initialized', False),
        'ready': session.get('rag_system_ready', False),
        'uploaded_file': session.get('uploaded_filename', None),
        'system_available': rag_system is not None,
        'llm_provider': 'groq',
        'health': health_status
    })


@app.route('/company_documents')
@login_required
def company_documents():
    """
    Get list of processed documents for the company
    """
    try:
        rag_system = get_or_create_rag_system()
        if rag_system:
            docs = rag_system.get_company_documents()
            return jsonify({
                'status': 'success',
                'documents': docs
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'RAG system not available'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/delete_document', methods=['POST'])
@login_required
def delete_document():
    """
    Delete a specific document and all its associated data
    """
    try:
        # Get RAG system for this company
        rag_system = get_or_create_rag_system()

        if rag_system is None:
            return jsonify({
                'status': 'error',
                'message': 'RAG system not available'
            }), 500

        # Get document file name from request
        data = request.get_json()
        if not data or 'file_name' not in data:
            return jsonify({
                'status': 'error',
                'message': 'File name not provided'
            }), 400

        file_name = data['file_name'].strip()
        if not file_name:
            return jsonify({
                'status': 'error',
                'message': 'File name cannot be empty'
            }), 400

        # Delete the document using RAG system
        result = rag_system.delete_document(file_name)

        if result['success']:
            # Update session if this was the only/current document
            remaining_docs = rag_system.get_company_documents()

            if not remaining_docs:
                # No documents left, update session
                session['rag_system_ready'] = False
                session.pop('uploaded_filename', None)
                session.pop('processed_file_path', None)

            return jsonify({
                'status': 'success',
                'message': result['message'],
                'deleted_items': result['deleted_items'],
                'remaining_documents': len(remaining_docs),
                'rag_system_ready': len(remaining_docs) > 0
            })
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 404

    except Exception as e:
        print(f"Document deletion error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error deleting document: {str(e)}'
        }), 500


@app.route('/delete_document_confirm/<file_name>', methods=['DELETE'])
@login_required
def delete_document_confirm(file_name):
    """
    Alternative endpoint for document deletion with file_name in URL
    """
    try:
        # Get RAG system for this company
        rag_system = get_or_create_rag_system()

        if rag_system is None:
            return jsonify({
                'status': 'error',
                'message': 'RAG system not available'
            }), 500

        # URL decode the file name
        from urllib.parse import unquote
        file_name = unquote(file_name)

        # Delete the document using RAG system
        result = rag_system.delete_document(file_name)

        if result['success']:
            # Update session if needed
            remaining_docs = rag_system.get_company_documents()

            if not remaining_docs:
                session['rag_system_ready'] = False
                session.pop('uploaded_filename', None)
                session.pop('processed_file_path', None)

            return jsonify({
                'status': 'success',
                'message': result['message'],
                'deleted_items': result['deleted_items'],
                'remaining_documents': len(remaining_docs)
            })
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 404

    except Exception as e:
        print(f"Document deletion error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error deleting document: {str(e)}'
        }), 500


@app.route('/integration')
def integration():
    """Display Google Workspace MCP Client dashboard"""
    try:
        return render_template('integration_hub.html')
    except Exception as e:
        return f"Dashboard error: {str(e)}", 500


@app.route('/business_agent', methods=['GET'])
def business_agent():
    """Display the Business Agent Chat Interface and allow interactions with the Agent"""
    return render_template('business_agent.html')

@app.route('/logout')
def logout():
    """Logout user and clear all session data"""
    try:
        session.clear()
        session.modified = True
        flash('Logged out successfully', 'info')
        return redirect(url_for('home'))
    except Exception as e:
        return f"Logout error: {str(e)}", 500

if __name__ == "__main__":
    app.run(port=5001, debug=True)
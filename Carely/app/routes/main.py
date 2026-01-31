from flask import Blueprint, render_template, session, redirect, url_for, send_file, request, flash
from io import BytesIO
from werkzeug.utils import secure_filename
from bson import Binary
from Carely.mongodb_database.connection import client
from Carely.app.utils import login_required, allowed_image_file

# Create the Blueprint
main_bp = Blueprint('main', __name__)

# Initialize Collection
company_collection = client.Carely.Customer

@main_bp.route('/')
def home():
    session.clear()
    return render_template('index.html')

@main_bp.route('/homepage/')
@login_required
def homepage():
    email = session.get('email')
    if email:
        user = company_collection.find_one({"email": email})
        if user:
            session['user'] = user['name']
    return render_template('homepage.html')

@main_bp.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@main_bp.route('/profile_image')
@login_required
def profile_image():
    email = session.get('email')
    profile_data = company_collection.find_one({'email': email})

    if profile_data and 'profile_image' in profile_data:
        image_data = profile_data['profile_image']
        return send_file(BytesIO(image_data), mimetype='image/jpeg')
    else:
        # Return a default image or a placeholder
        return redirect(url_for('static', filename='images/default_profile_photo.jpg'))

@main_bp.route('/upload_image/', methods=['GET', 'POST'])
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

            # Get user email from session
            email = session['email']

            # Store the image in the database as binary data
            company_collection.update_one({'email': email}, {'$set': {'profile_image': Binary(image_content)}})

            flash('Image uploaded successfully', 'success')

            return redirect(url_for('main.profile'))

        else:
            flash('Allowed file types are png, jpg, jpeg, gif', 'error')
            return redirect(request.url)

    # Handle GET request to show the upload form
    return render_template('upload_image.html')

@main_bp.route('/integration')
def integration():
    """Display Google Workspace MCP Client dashboard"""
    try:
        return render_template('integration_hub.html')
    except Exception as e:
        return f"Dashboard error: {str(e)}", 500

@main_bp.route('/logout')
def logout():
    """Logout user and clear all session data"""
    try:
        session.clear()
        session.modified = True
        flash('Logged out successfully', 'info')
        return redirect(url_for('main.home'))
    except Exception as e:
        return f"Logout error: {str(e)}", 500
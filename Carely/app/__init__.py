import os
from flask import Flask
from Carely.app.config import Config

def create_app():
    """
    Application Factory Pattern to initialize the Flask App
    """
    # 1. Initialize the Flask application
    app = Flask(__name__)

    # 2. Load configuration from config.py
    app.config.from_object(Config)

    # 3. Ensure the upload folder exists (critical for PDF uploads)
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    except OSError:
        pass

    # 4. Import Blueprints
    # Imports are done here to avoid circular import errors
    from Carely.app.routes.auth import auth_bp
    from Carely.app.routes.main import main_bp
    from Carely.app.routes.rag_agent import rag_bp
    from Carely.app.routes.business_agent import business_bp
    from Carely.app.routes.whatsapp_integration import whatsapp_bp

    # 5. Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(rag_bp)
    app.register_blueprint(business_bp)
    app.register_blueprint(whatsapp_bp)

    return app
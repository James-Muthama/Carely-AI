from app import create_app

# Initialize the Flask application using the factory pattern
app = create_app()

if __name__ == "__main__":
    # Run the application on port 5001 to match your original configuration
    app.run(port=5001, debug=True)
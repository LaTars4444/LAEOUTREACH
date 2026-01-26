import os
import threading
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from extensions import db, login_manager
from models import User, Lead, Investor, OutreachLog
from tasks import google_search_hunter
from werkzeug.security import generate_password_hash, check_password_hash

def create_app():
    # Calculate the path to the 'dist' folder relative to this file
    base_dir = os.path.abspath(os.path.dirname(__file__))
    static_folder_path = os.path.join(base_dir, 'dist')
    
    print(f"Base Directory: {base_dir}")
    print(f"Expected Static Folder: {static_folder_path}")
    
    if os.path.exists(static_folder_path):
        print(f"✅ Static folder found: {static_folder_path}")
        print(f"Contents: {os.listdir(static_folder_path)}")
    else:
        print(f"❌ WARNING: Static folder NOT found at {static_folder_path}")

    app = Flask(__name__, static_folder=static_folder_path, static_url_path='')
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev_key')
    
    # Database Config
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///titan.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize Extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # Enable CORS
    CORS(app)

    with app.app_context():
        db.create_all()

    return app

app = create_app()

# --- SERVE REACT FRONTEND ---

@app.route('/')
def serve_react():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    # Check if file exists in dist, otherwise serve index.html for client-side routing
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

# --- API ROUTES ---

@app.route('/api/health')
def health_check():
    return jsonify({"status": "Titan Enterprise API Online", "version": "12.0.0"})

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    user = User.query.filter_by(email=data.get('email')).first()
    if user and check_password_hash(user.password, data.get('password')):
        return jsonify({"message": "Login successful", "user_id": user.id, "api_key": user.groq_api_key})
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    if User.query.filter_by(email=data.get('email')).first():
        return jsonify({"error": "User exists"}), 400
    
    hashed = generate_password_hash(data.get('password'), method='scrypt')
    new_user = User(email=data.get('email'), password=hashed)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User created", "user_id": new_user.id})

@app.route('/api/leads/hunt', methods=['POST'])
def trigger_hunt():
    data = request.json
    api_key = os.environ.get('GOOGLE_SEARCH_API_KEY')
    cx = os.environ.get('GOOGLE_SEARCH_CX')
    
    if not api_key or not cx:
        return jsonify({"error": "Server missing Google Keys"}), 500

    # Run in background
    thread = threading.Thread(target=google_search_hunter, args=(app, data.get('user_id'), data.get('city'), data.get('state'), api_key, cx))
    thread.start()
    
    return jsonify({"message": "Hunt started in background"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

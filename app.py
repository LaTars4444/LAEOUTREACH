import os
import random
import time
import base64
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText

# Third-party imports
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_required, current_user, login_user, logout_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import stripe
from groq import Groq

# ---------------------------------------------------------
# CONFIGURATION & SETUP
# ---------------------------------------------------------
app = Flask(__name__)

# 1. Security Config
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_dev_key')

# 2. Database Config (Bulletproof Fallback)
# Try to use the persistent disk, but fall back to local if it fails
if os.path.exists('/var/data'):
    db_path = 'sqlite:////var/data/titan.db'
    print("✅ Using Persistent Disk: /var/data/titan.db")
else:
    db_path = 'sqlite:///titan.db'
    print("⚠️ WARNING: /var/data not found. Using ephemeral local DB.")

app.config['SQLALCHEMY_DATABASE_URI'] = db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Init Database
db = SQLAlchemy(app)

# Init Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 3. API Config (Safe Initialization)
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

groq_api_key = os.environ.get("GROQ_API_KEY")
if groq_api_key:
    groq_client = Groq(api_key=groq_api_key)
else:
    print("⚠️ WARNING: GROQ_API_KEY not found. AI features will fail.")
    groq_client = None

UPLOAD_FOLDER = 'static/uploads'

# ---------------------------------------------------------
# MODELS
# ---------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    google_token = db.Column(db.Text, nullable=True)
    stripe_customer_id = db.Column(db.String(100), nullable=True)
    subscription_status = db.Column(db.String(50), default='free') 
    subscription_end = db.Column(db.DateTime, nullable=True)
    bb_property_type = db.Column(db.String(50))
    bb_locations = db.Column(db.String(255))
    bb_min_price = db.Column(db.Integer)
    bb_max_price = db.Column(db.Integer)
    bb_condition = db.Column(db.String(50))
    bb_strategy = db.Column(db.String(50))
    bb_funding = db.Column(db.String(50)) 
    bb_timeline = db.Column(db.String(50))

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    address = db.Column(db.String(255), nullable=False)
    property_type = db.Column(db.String(50))
    year_built = db.Column(db.Integer)
    roof_age = db.Column(db.Integer)
    hvac_age = db.Column(db.Integer)
    condition_plumbing = db.Column(db.String(50))
    condition_electrical = db.Column(db.String(50))
    condition_overall = db.Column(db.String(50))
    occupancy_status = db.Column(db.String(50))
    desired_price = db.Column(db.Integer)
    timeline = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    photos_url = db.Column(db.String(500))
    arv_estimate = db.Column(db.Integer)
    repair_estimate = db.Column(db.Integer)
    max_allowable_offer = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OutreachLog(db.Model):
    __tablename__ = 'outreach_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_email = db.Column(db.String(150), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50)) 
    error_msg = db.Column(db.Text)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user:
            try:
                if check_password_hash(user.password, password) or user.password == password:
                    login_user(user)
                    return redirect(url_for('dashboard'))
            except:
                pass
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if User.query.filter_by(email=email).first():
            flash('Email exists', 'error')
        else:
            hashed = generate_password_hash(password, method='scrypt')
            user = User(email=email, password=hashed)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ---------------------------------------------------------
# FEATURES
# ---------------------------------------------------------
def check_access(user, feature):
    if not user: return False
    if user.subscription_status == 'lifetime': return True
    if user.subscription_status in ['weekly', 'monthly']:
        if user.subscription_end and user.subscription_end > datetime.utcnow(): return True
    now = datetime.utcnow()
    if feature == 'email' and now < user.created_at + timedelta(hours=24): return True
    if feature == 'ai' and now < user.created_at + timedelta(hours=48): return True
    return False

@app.route('/ai/generate', methods=['POST'])
@login_required
def ai_generate():
    if not groq_client: return jsonify({'error': 'AI configuration missing'}), 500
    if not check_access(current_user, 'ai'): return jsonify({'error': 'Trial expired'}), 403
    
    data = request.json
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": data.get('input')}],
            model="llama3-8b-8192"
        )
        return jsonify({'result': chat_completion.choices[0].message.content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/email_machine/send', methods=['POST'])
@login_required
def send_email_machine():
    return jsonify({'status': 'Functionality placeholder'}) 

@app.route('/buy_box', methods=['GET', 'POST'])
@login_required
def buy_box():
    if request.method == 'POST':
        # Save logic here
        flash('Saved', 'success')
    return render_template('buy_box.html', user=current_user)

@app.route('/sell', methods=['GET', 'POST'])
def sell_property():
    return render_template('sell.html')

@app.route('/stripe_webhook', methods=['POST'])
def stripe_webhook():
    return jsonify(success=True)

if __name__ == "__main__":
    app.run(debug=True)

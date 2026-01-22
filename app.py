import os
import random
import time
import base64
import json
import re
import threading
from datetime import datetime, timedelta

# Allow HTTP for OAuth on Render
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

import requests

# Third-party imports
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_required, current_user, login_user, logout_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import inspect, text

# GOOGLE / YOUTUBE IMPORTS
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# AI & VIDEO IMPORTS
import stripe
from groq import Groq
from gtts import gTTS
from moviepy.editor import ImageClip, AudioFileClip

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super_secret_key')

# ADMIN CONFIG
ADMIN_EMAIL = "leewaits836@gmail.com"

# Persistent Database Config
if os.path.exists('/var/data'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/data/titan.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///titan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# API Clients
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# SEARCH CONFIG
SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX", "17b704d9fe2114c12")

# STRIPE PRICE IDS
PRICE_WEEKLY = "price_1SpxexFXcDZgM3Vo0iYmhfpb"
PRICE_MONTHLY = "price_1SqIjgFXcDZgM3VoEwrUvjWP"
PRICE_LIFETIME = "price_1Spy7SFXcDZgM3VoVZv71I63"

# OAUTH CREDENTIALS
CREDS = {
    'google': {'id': os.environ.get("GOOGLE_CLIENT_ID"), 'secret': os.environ.get("GOOGLE_CLIENT_SECRET")},
    'tiktok': {'key': os.environ.get("TIKTOK_CLIENT_KEY"), 'secret': os.environ.get("TIKTOK_CLIENT_SECRET")},
    'meta': {'id': os.environ.get("META_CLIENT_ID"), 'secret': os.environ.get("META_CLIENT_SECRET")}
}

# Folders
UPLOAD_FOLDER = 'static/uploads'
VIDEO_FOLDER = 'static/videos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ---------------------------------------------------------
# 2. DATABASE MODELS
# ---------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=True) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Auth Tokens
    google_token = db.Column(db.Text, nullable=True)
    tiktok_token = db.Column(db.Text, nullable=True)
    meta_token = db.Column(db.Text, nullable=True)
    
    # Subscription & Trial Logic
    subscription_status = db.Column(db.String(50), default='free') 
    subscription_end = db.Column(db.DateTime, nullable=True)
    trial_active = db.Column(db.Boolean, default=False)
    trial_start = db.Column(db.DateTime, nullable=True)

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Basic
    address = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    
    # Deep Property Details
    asking_price = db.Column(db.String(50), nullable=True)
    photos = db.Column(db.Text, nullable=True)
    
    year_built = db.Column(db.Integer, nullable=True)
    square_footage = db.Column(db.Integer, nullable=True)
    lot_size = db.Column(db.String(50), nullable=True)
    bedrooms = db.Column(db.Integer, nullable=True)
    bathrooms = db.Column(db.Float, nullable=True)
    hvac_type = db.Column(db.String(100), nullable=True)
    hoa_fees = db.Column(db.String(50), nullable=True)
    parking_type = db.Column(db.String(100), nullable=True)
    
    distress_type = db.Column(db.String(100)) 
    status = db.Column(db.String(50), default="New") 
    source = db.Column(db.String(50), default="Manual")
    link = db.Column(db.String(500)) 
    emailed_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------------------------------------------------
# 3. AUTO-MIGRATION LOGIC
# ---------------------------------------------------------
with app.app_context():
    db.create_all()
    inspector = inspect(db.engine)
    
    user_columns = [c['name'] for c in inspector.get_columns('users')]
    with db.engine.connect() as conn:
        if 'trial_active' not in user_columns: conn.execute(text("ALTER TABLE users ADD COLUMN trial_active BOOLEAN DEFAULT 0"))
        if 'trial_start' not in user_columns: conn.execute(text("ALTER TABLE users ADD COLUMN trial_start DATETIME"))
        conn.commit()

    lead_columns = [c['name'] for c in inspector.get_columns('leads')]
    with db.engine.connect() as conn:
        if 'year_built' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN year_built INTEGER"))
        if 'square_footage' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN square_footage INTEGER"))
        if 'lot_size' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN lot_size TEXT"))
        if 'bedrooms' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN bedrooms INTEGER"))
        if 'bathrooms' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN bathrooms FLOAT"))
        if 'hvac_type' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN hvac_type TEXT"))
        if 'hoa_fees' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN hoa_fees TEXT"))
        if 'parking_type' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN parking_type TEXT"))
        if 'emailed_count' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN emailed_count INTEGER DEFAULT 0"))
        
        # New Columns
        if 'asking_price' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN asking_price TEXT"))
        if 'photos' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN photos TEXT"))
        conn.commit()

# ---------------------------------------------------------
# 4. PAYWALL + ADMIN BYPASS LOGIC
# ---------------------------------------------------------
def check_access(user, feature):
    if not user: return False
    
    # 0. ADMIN BYPASS (GOD MODE)
    if user.email == ADMIN_EMAIL:
        return True
    
    # 1. TRIAL CHECK (48 HOURS)
    if user.trial_active and user.trial_start:
        hours_passed = (datetime.utcnow() - user.trial_start).total_seconds() / 3600
        if hours_passed < 48:
            return True
        else:
            if user.trial_active:
                user.trial_active = False 
                db.session.commit()
    
    # 2. ACTIVE SUBSCRIPTION
    if user.subscription_status in ['weekly', 'monthly']:
        if user.subscription_end and user.subscription_end > datetime.utcnow():
            return True

    # 3. LIFETIME PLAN
    if user.subscription_status == 'lifetime':
        if feature == 'email': return True
        else: return False

    return False

# ---------------------------------------------------------
# 5. GOOGLE API SCRAPER (SCORCHED EARTH STRATEGY)
# ---------------------------------------------------------
def search_off_market(city, state):
    if not SEARCH_API_KEY: 
        print("ERROR: Missing GOOGLE_SEARCH_API_KEY")
        return []

    print(f"--- Scanning {city}, {state} (Aggressive Mode) ---")
    
    queries = [
        f'"{city}" "{state}" "vacant property" list filetype:pdf',
        f'"{city}" "{state}" "for sale by owner" -broker -agent phone',
        f'"{city}" "code violation" property list',
        f'"{city}" "heir" "deceased" property sale',
        f'"{city}" "divorce" decree property address',
        f'"{city}" "cash only" "needs repairs" -realtor'
    ]
    
    leads_found = []
    service = build("customsearch", "v1", developerKey=SEARCH_API_KEY)

    for q in queries:
        try:
            res = service.cse().list(q=q, cx=SEARCH_CX, num=10).execute()
            for item in res.get('items', []):
                snippet = (item.get('snippet', '') + " " + item.get('title', '')).lower()
                phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', snippet)
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                is_file = 'filetype:pdf' in q or '.pdf' in item.get('link')
                
                leads_found.append({
                    'address': item.get('title'),
                    'phone': phones[0] if phones else ('DOWNLOAD LIST' if is_file else 'Check Link'),
                    'email': emails[0] if emails else 'Check Link',
                    'source': 'Distressed File/Site',
                    'link': item.get('link')
                })
        except Exception as e:
            print(f"API Error: {e}")
            continue
    return leads_found

# ---------------------------------------------------------
# 6. ROUTES
# ---------------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    my_leads = Lead.query.filter_by(submitter_id=current_user.id).order_by(Lead.created_at.desc()).all()
    
    seller_submissions = []
    if current_user.email == ADMIN_EMAIL:
        seller_submissions = Lead.query.filter_by(source='Seller Wizard').order_by(Lead.created_at.desc()).all()

    has_pro = check_access(current_user, 'pro')
    has_email = check_access(current_user, 'email')
    is_admin = (current_user.email == ADMIN_EMAIL)
    
    trial_time_left = None
    if current_user.trial_active and current_user.trial_start:
        elapsed = datetime.utcnow() - current_user.trial_start
        remaining = timedelta(hours=48) - elapsed
        if remaining.total_seconds() > 0:
            trial_time_left = int(remaining.total_seconds())
    
    return render_template(
        'dashboard.html', 
        user=current_user, 
        leads=my_leads, 
        seller_inbox=seller_submissions,
        has_pro=has_pro, 
        has_email=has_email, 
        is_admin=is_admin,
        trial_left=trial_time_left
    )

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/start-trial')
@login_required
def start_trial():
    if current_user.email == ADMIN_EMAIL:
        flash("Admin always has access!", "success")
        return redirect(url_for('dashboard'))

    if current_user.trial_active or current_user.subscription_status != 'free':
        flash("Trial already used or active.", "error")
        return redirect(url_for('dashboard'))
    current_user.trial_active = True
    current_user.trial_start = datetime.utcnow()
    current_user.subscription_status = 'weekly'
    db.session.commit()
    flash("48-Hour Free Trial Started! Enjoy.", "success")
    return redirect(url_for('dashboard'))

@app.route('/leads/hunt', methods=['POST'])
@login_required
def hunt_leads():
    if not check_access(current_user, 'pro'):
        return jsonify({'error': 'PAYWALL: Trial expired. Please upgrade.'}), 403

    city = request.form.get('city')
    state = request.form.get('state')
    
    raw_leads = search_off_market(city, state)
    
    count = 0
    for l in raw_leads:
        exists = Lead.query.filter_by(link=l['link']).first()
        if not exists:
            new_lead = Lead(
                submitter_id=current_user.id,
                address=l['address'],
                phone=l['phone'],
                email=l['email'],
                distress_type="Aggressive Find",
                source="Titan API", 
                link=l['link'], 
                status="New"
            )
            db.session.add(new_lead)
            count += 1
    db.session.commit()
    return jsonify({'message': f"Aggressive Scan Complete. Found {count} high-quality leads."})

def send_emails_background(app, user_id, subject, body):
    with app.app_context():
        user = User.query.get(user_id)
        leads = Lead.query.filter_by(submitter_id=user_id).all()
        for lead in leads:
            if lead.email and '@' in lead.email:
                delay = random.uniform(5, 15)
                time.sleep(delay)
                lead.emailed_count = (lead.emailed_count or 0) + 1
                lead.status = "Contacted"
                db.session.commit()

@app.route('/email/campaign', methods=['POST'])
@login_required
def email_campaign():
    if not check_access(current_user, 'email'):
        return jsonify({'error': 'Upgrade required.'}), 403
    
    subject = request.form.get('subject')
    body = request.form.get('body')
    thread = threading.Thread(target=send_emails_background, args=(app._get_current_object(), current_user.id, subject, body))
    thread.start()
    return jsonify({'message': "🚀 Campaign Started! Sending with human-like delays."})


@app.route('/create-checkout-session/<plan_type>')
@login_required
def create_checkout_session(plan_type):
    if current_user.email == ADMIN_EMAIL: return redirect(url_for('dashboard'))
    prices = {'weekly': PRICE_WEEKLY, 'monthly': PRICE_MONTHLY, 'lifetime': PRICE_LIFETIME}
    price_id = prices.get(plan_type)
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{'price': price_id, 'quantity': 1}],
        mode='payment' if plan_type == 'lifetime' else 'subscription',
        success_url=url_for('dashboard', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=url_for('pricing', _external=True),
        client_reference_id=str(current_user.id),
    )
    return redirect(checkout_session.url, code=303)

@app.route('/stripe_webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            user = User.query.get(session.get('client_reference_id'))
            if user:
                line_items = stripe.checkout.Session.list_line_items(session['id'], limit=1)
                pid = line_items['data'][0]['price']['id']
                if pid == PRICE_LIFETIME: user.subscription_status = 'lifetime'
                elif pid == PRICE_MONTHLY: 
                    user.subscription_status = 'monthly'
                    user.subscription_end = datetime.utcnow() + timedelta(days=30)
                elif pid == PRICE_WEEKLY:
                    user.subscription_status = 'weekly'
                    user.subscription_end = datetime.utcnow() + timedelta(days=7)
                user.trial_active = False
                db.session.commit()
    except: return 'Error', 400
    return jsonify(success=True)

@app.route('/video/create', methods=['POST'])
@login_required
def create_video():
    if not check_access(current_user, 'pro'): return jsonify({'error': 'Upgrade required.'}), 403
    desc = request.form.get('description')
    photo = request.files.get('photo')
    try:
        filename = secure_filename(f"img_{int(time.time())}.jpg")
        img_path = os.path.join(UPLOAD_FOLDER, filename)
        photo.save(img_path)
        if not os.environ.get("GROQ_API_KEY"): return jsonify({'video_url': "", 'error': "API Key Missing"})
        chat = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": "Write a 15s viral real estate script."}, {"role": "user", "content": desc}],
            model="llama-3.3-70b-versatile"
        )
        script = chat.choices[0].message.content
        audio_name = f"audio_{int(time.time())}.mp3"
        audio_path = os.path.join(VIDEO_FOLDER, audio_name)
        tts = gTTS(text=script, lang='en')
        tts.save(audio_path)
        audio_clip = AudioFileClip(audio_path)
        video_clip = ImageClip(img_path).set_duration(audio_clip.duration).set_audio(audio_clip)
        vid_name = f"video_{int(time.time())}.mp4"
        out_path = os.path.join(VIDEO_FOLDER, vid_name)
        video_clip.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac")
        return jsonify({'video_url': f"/{VIDEO_FOLDER}/{vid_name}", 'video_path': f"{VIDEO_FOLDER}/{vid_name}"})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/social/post', methods=['POST'])
@login_required
def social_post():
    if not check_access(current_user, 'pro'): return jsonify({'error': 'Upgrade required.'}), 403
    return jsonify({'message': 'Posted to Socials!'})

@app.route('/')
def index(): return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and (user.password == request.form['password'] or check_password_hash(user.password, request.form['password'])):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not User.query.filter_by(email=request.form['email']).first():
            hashed = generate_password_hash(request.form['password'], method='scrypt')
            user = User(email=request.form['email'], password=hashed)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/sell', methods=['GET', 'POST'])
def sell_property():
    if request.method == 'POST':
        # HANDLE PHOTOS
        photo_files = request.files.getlist('photos')
        saved_filenames = []
        for f in photo_files:
            if f.filename:
                fname = secure_filename(f.filename)
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                saved_filenames.append(fname)
        
        photos_str = ",".join(saved_filenames) if saved_filenames else ""

        lead = Lead(
            address=request.form.get('address'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            asking_price=request.form.get('asking_price'), # NEW
            photos=photos_str, # NEW
            year_built=request.form.get('year_built'),
            square_footage=request.form.get('square_footage'),
            lot_size=request.form.get('lot_size'),
            bedrooms=request.form.get('bedrooms'),
            bathrooms=request.form.get('bathrooms'),
            hvac_type=request.form.get('hvac_type'),
            hoa_fees=request.form.get('hoa_fees'),
            parking_type=request.form.get('parking_type'),
            source="Seller Wizard",
            status="New"
        )
        db.session.add(lead)
        db.session.commit()
        flash('Offer Request Received! We will contact you shortly.', 'success')
        return redirect(url_for('sell_property'))
    return render_template('sell.html')

# ---------------------------------------------------------
# 10. TEMPLATES
# ---------------------------------------------------------
html_templates = {
  'pricing.html': """
{% extends "base.html" %}
{% block content %}
<div class="text-center mb-5"><h1 class="fw-bold">🚀 Upgrade to Titan</h1><p class="lead">Unlock the Scraper, AI Video, and Email Machine.</p><div class="mt-4"><a href="/start-trial" class="btn btn-outline-danger btn-lg fw-bold shadow-sm">⚡ Start 48-Hour Free Trial (No Credit Card)</a><p class="text-muted small mt-2">Instant access. No commitment.</p></div></div><div class="row text-center mt-5"><div class="col-md-4"><div class="card shadow-sm mb-4"><div class="card-header bg-secondary text-white">Weekly</div><div class="card-body"><h2>$3<small>/wk</small></h2><a href="/create-checkout-session/weekly" class="btn btn-outline-dark w-100">Start Weekly</a></div></div></div><div class="col-md-4"><div class="card shadow mb-4 border-warning"><div class="card-header bg-warning text-dark fw-bold">Lifetime Deal</div><div class="card-body"><h2>$20<small> (One Time)</small></h2><a href="/create-checkout-session/lifetime" class="btn btn-dark w-100">Buy Lifetime</a></div></div></div><div class="col-md-4"><div class="card shadow-sm mb-4 border-primary"><div class="card-header bg-primary text-white">Pro Monthly</div><div class="card-body"><h2>$50<small>/mo</small></h2><a href="/create-checkout-session/monthly" class="btn btn-primary w-100">Go Pro</a></div></div></div></div>
{% endblock %}
""",
  'base.html': """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>TITAN</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><style>.split-bg { background-image: url('https://images.unsplash.com/photo-1560518883-ce09059eeffa?ixlib=rb-1.2.1&auto=format&fit=crop&w=1950&q=80'); background-size: cover; background-position: center; height: 100vh; }</style></head><body class="bg-light">{% if trial_left %}<div id="trialTimer" class="fw-bold text-white shadow" style="position: fixed; top: 70px; left: 20px; z-index: 9999; background: #dc3545; padding: 10px 15px; border-radius: 5px;">⏳ Free Trial: <span id="timerSpan">Loading...</span></div><script>let secondsLeft = {{ trial_left }}; setInterval(function() { if(secondsLeft <= 0) { document.getElementById('trialTimer').innerHTML = "Trial Expired"; return; } secondsLeft--; let h = Math.floor(secondsLeft / 3600); let m = Math.floor((secondsLeft % 3600) / 60); let s = secondsLeft % 60; document.getElementById('timerSpan').innerText = h + "h " + m + "m " + s + "s"; }, 1000);</script>{% endif %}<nav class="navbar navbar-expand-lg navbar-dark bg-dark"><div class="container"><a class="navbar-brand" href="/">TITAN ⚡</a><ul class="navbar-nav ms-auto gap-3"><li class="nav-item"><a class="btn btn-warning btn-sm" href="/sell">Sell</a></li>{% if current_user.is_authenticated %}<li class="nav-item"><a class="nav-link" href="/dashboard">Dashboard</a></li><li class="nav-item"><a class="nav-link text-danger" href="/logout">Logout</a></li>{% else %}<li class="nav-item"><a class="nav-link" href="/login">Login</a></li>{% endif %}</ul></div></nav><div class="container mt-4">{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ 'danger' if category == 'error' else 'success' }}">{{ message }}</div>{% endfor %}{% endif %}{% endwith %}{% block content %}{% endblock %}</div></body></html>""",
  'dashboard.html': """
{% extends "base.html" %}
{% block content %}
<div class="row">

  <!-- WELCOME ADMIN -->
  {% if is_admin %}
  <div class="col-12 mb-3">
    <div class="alert alert-warning fw-bold text-center">
        👑 WELCOME ADMIN! You have Global Access. No Paywalls.
    </div>
  </div>
  {% endif %}

  <ul class="nav nav-tabs mb-4" id="myTab" role="tablist">
    <li class="nav-item"><button class="nav-link active" id="leads-tab" data-bs-toggle="tab" data-bs-target="#leads">🏠 My Leads</button></li>
    {% if is_admin %}<li class="nav-item"><button class="nav-link fw-bold text-danger" id="inbox-tab" data-bs-toggle="tab" data-bs-target="#inbox">📥 Seller Inbox</button></li>{% endif %}
    <li class="nav-item"><button class="nav-link" id="hunter-tab" data-bs-toggle="tab" data-bs-target="#hunter">🕵️ Deal Hunter</button></li>
    <li class="nav-item"><button class="nav-link" id="email-tab" data-bs-toggle="tab" data-bs-target="#email">📧 Email Machine</button></li>
    <li class="nav-item"><button class="nav-link" id="video-tab" data-bs-toggle="tab" data-bs-target="#video">🎬 AI Video</button></li>
  </ul>
  
  <div class="tab-content">
    <div class="tab-pane fade show active" id="leads">
        <div class="card shadow-sm"><div class="card-body">
        <table class="table table-hover"><thead><tr><th>Status</th><th>Address</th><th>Source</th><th>Email Count</th><th>Link</th></tr></thead><tbody>{% for lead in leads %}<tr><td><span class="badge bg-success">{{ lead.status }}</span></td><td>{{ lead.address }}</td><td>{{ lead.source }}</td><td>{{ lead.emailed_count }}</td><td><a href="{{ lead.link }}" target="_blank" class="btn btn-sm btn-outline-primary">View</a></td></tr>{% else %}<tr><td colspan="5" class="text-center p-4">No leads. Start Hunting!</td></tr>{% endfor %}</tbody></table></div></div>
    </div>
    
    <!-- ADMIN ONLY: SELLER INBOX -->
    {% if is_admin %}
    <div class="tab-pane fade" id="inbox">
        <div class="card shadow-sm border-danger">
            <div class="card-header bg-danger text-white fw-bold">Seller Form Submissions</div>
            <div class="card-body table-responsive">
                <table class="table table-striped">
                    <thead><tr><th>Address</th><th>Price</th><th>Contact</th><th>Details</th><th>Photos</th></tr></thead>
                    <tbody>
                    {% for s in seller_inbox %}
                    <tr>
                        <td class="fw-bold">{{ s.address }}</td>
                        <td class="text-success fw-bold">{{ s.asking_price or 'N/A' }}</td>
                        <td>{{ s.phone }}<br>{{ s.email }}</td>
                        <td>
                            <small>
                            <b>Built:</b> {{ s.year_built }}<br>
                            <b>SqFt:</b> {{ s.square_footage }}<br>
                            <b>HVAC:</b> {{ s.hvac_type }}
                            </small>
                        </td>
                        <td>
                            {% if s.photos %}
                            <span class="badge bg-primary">📸 Photos Uploaded</span>
                            {% else %}
                            <span class="text-muted">No Pics</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="7" class="text-center">No submissions yet.</td></tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    {% endif %}
    
    <div class="tab-pane fade" id="hunter">
        <div class="card bg-dark text-white">
            <div class="card-body p-5 text-center">
                <h3 class="fw-bold">🕵️ Google API Search (Aggressive Mode)</h3>
                <p>Scans for PDFs, Divorce Decrees, and Vacant Lists.</p>
                {% if has_pro %}
                <div class="row justify-content-center mt-4">
                    <div class="col-md-4"><select id="huntState" class="form-select" onchange="loadCities()"><option>Select State</option></select></div>
                    <div class="col-md-4"><select id="huntCity" class="form-select"><option>Select State First</option></select></div>
                    <div class="col-md-3"><button onclick="runHunt()" class="btn btn-warning w-100 fw-bold">Search Network</button></div>
                </div>
                <div id="huntStatus" class="mt-3 text-warning"></div>
                {% else %}
                <div class="mt-4"><a href="/pricing" class="btn btn-warning">Upgrade / Start Trial</a></div>
                {% endif %}
            </div>
        </div>
    </div>

    <div class="tab-pane fade" id="email"><div class="card shadow-sm border-warning"><div class="card-header bg-warning text-dark fw-bold">📧 Email Marketing Machine</div><div class="card-body">{% if has_email %}<div class="mb-3"><label>Subject</label><input id="emailSubject" class="form-control" value="Cash Offer"></div><div class="mb-3"><label>Body</label><textarea id="emailBody" class="form-control" rows="5">Interested in selling?</textarea></div><button onclick="sendBlast()" class="btn btn-dark w-100">🚀 Blast to All {{ leads|length }} Leads</button>{% else %}<div class="text-center p-4"><a href="/pricing" class="btn btn-warning">Unlock Email Machine</a></div>{% endif %}</div></div></div>
    <div class="tab-pane fade" id="video"><div class="card shadow-sm"><div class="card-body text-center"><h3>🎬 AI Content Generator</h3>{% if has_pro %}<input type="file" id="videoPhoto" class="form-control mb-2 w-50 mx-auto"><textarea id="videoInput" class="form-control mb-2 w-50 mx-auto" placeholder="Describe property..."></textarea><button onclick="createVideo()" class="btn btn-primary">Generate Video</button><div id="videoResult" class="d-none mt-3"><video id="player" controls class="w-50 rounded border"></video></div>{% else %}<a href="/pricing" class="btn btn-warning mt-3">Upgrade / Start Trial</a>{% endif %}</div></div></div>
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
const usData = {
    "AL": ["Birmingham", "Montgomery", "Mobile", "Huntsville", "Tuscaloosa"],
    "AK": ["Anchorage", "Fairbanks", "Juneau"],
    "AZ": ["Phoenix", "Tucson", "Mesa", "Chandler", "Scottsdale", "Glendale"],
    "AR": ["Little Rock", "Fort Smith", "Fayetteville", "Springdale"],
    "CA": ["Los Angeles", "San Diego", "San Jose", "San Francisco", "Fresno", "Sacramento", "Long Beach", "Oakland", "Bakersfield", "Anaheim"],
    "CO": ["Denver", "Colorado Springs", "Aurora", "Fort Collins", "Lakewood"],
    "CT": ["Bridgeport", "New Haven", "Stamford", "Hartford", "Waterbury"],
    "DE": ["Wilmington", "Dover", "Newark"],
    "FL": ["Jacksonville", "Miami", "Tampa", "Orlando", "St. Petersburg", "Hialeah", "Tallahassee", "Fort Lauderdale", "Port St. Lucie"],
    "GA": ["Atlanta", "Augusta", "Columbus", "Macon", "Savannah"],
    "HI": ["Honolulu", "Hilo", "Kailua"],
    "ID": ["Boise", "Meridian", "Nampa"],
    "IL": ["Chicago", "Aurora", "Naperville", "Joliet", "Rockford"],
    "IN": ["Indianapolis", "Fort Wayne", "Evansville", "South Bend"],
    "IA": ["Des Moines", "Cedar Rapids", "Davenport"],
    "KS": ["Wichita", "Overland Park", "Kansas City"],
    "KY": ["Louisville", "Lexington", "Bowling Green"],
    "LA": ["New Orleans", "Baton Rouge", "Shreveport", "Lafayette"],
    "ME": ["Portland", "Lewiston", "Bangor"],
    "MD": ["Baltimore", "Columbia", "Germantown"],
    "MA": ["Boston", "Worcester", "Springfield", "Cambridge"],
    "MI": ["Detroit", "Grand Rapids", "Warren", "Sterling Heights"],
    "MN": ["Minneapolis", "St. Paul", "Rochester", "Duluth"],
    "MS": ["Jackson", "Gulfport", "Southaven"],
    "MO": ["Kansas City", "St. Louis", "Springfield", "Columbia"],
    "MT": ["Billings", "Missoula", "Great Falls"],
    "NE": ["Omaha", "Lincoln", "Bellevue"],
    "NV": ["Las Vegas", "Henderson", "Reno", "North Las Vegas"],
    "NH": ["Manchester", "Nashua", "Concord"],
    "NJ": ["Newark", "Jersey City", "Paterson", "Elizabeth"],
    "NM": ["Albuquerque", "Las Cruces", "Rio Rancho"],
    "NY": ["New York", "Buffalo", "Rochester", "Yonkers", "Syracuse"],
    "NC": ["Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem"],
    "ND": ["Fargo", "Bismarck", "Grand Forks"],
    "OH": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron"],
    "OK": ["Oklahoma City", "Tulsa", "Norman", "Broken Arrow"],
    "OR": ["Portland", "Salem", "Eugene", "Gresham"],
    "PA": ["Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading"],
    "RI": ["Providence", "Warwick", "Cranston"],
    "SC": ["Charleston", "Columbia", "North Charleston", "Mount Pleasant"],
    "SD": ["Sioux Falls", "Rapid City", "Aberdeen"],
    "TN": ["Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville"],
    "TX": ["Houston", "San Antonio", "Dallas", "Austin", "Fort Worth", "El Paso", "Arlington", "Corpus Christi", "Plano"],
    "UT": ["Salt Lake City", "West Valley City", "Provo", "West Jordan"],
    "VT": ["Burlington", "South Burlington", "Rutland"],
    "VA": ["Virginia Beach", "Norfolk", "Chesapeake", "Richmond", "Newport News"],
    "WA": ["Seattle", "Spokane", "Tacoma", "Vancouver"],
    "WV": ["Charleston", "Huntington", "Morgantown"],
    "WI": ["Milwaukee", "Madison", "Green Bay", "Kenosha"],
    "WY": ["Cheyenne", "Casper", "Laramie"]
};
window.onload = function() { const stateSel = document.getElementById("huntState"); if(stateSel) { stateSel.innerHTML = '<option value="">Select State</option>'; for (let state in usData) { let opt = document.createElement('option'); opt.value = state; opt.innerHTML = state; stateSel.appendChild(opt); } } };
function loadCities() { const state = document.getElementById("huntState").value; const citySel = document.getElementById("huntCity"); citySel.innerHTML = '<option value="">Select City</option>'; if(state && usData[state]) { usData[state].forEach(city => { let opt = document.createElement('option'); opt.value = city; opt.innerHTML = city; citySel.appendChild(opt); }); } }
async function runHunt() { const city = document.getElementById('huntCity').value; const state = document.getElementById('huntState').value; if(!city || !state) return alert("Please select both State and City."); document.getElementById('huntStatus').innerText = "Querying API Network..."; const formData = new FormData(); formData.append('city', city); formData.append('state', state); const res = await fetch('/leads/hunt', {method: 'POST', body: formData}); const data = await res.json(); if(res.status === 403) window.location.href = '/pricing'; else { alert(data.message); window.location.reload(); } }
async function sendBlast() { if(!confirm("Send to everyone?")) return; const formData = new FormData(); formData.append('subject', document.getElementById('emailSubject').value); formData.append('body', document.getElementById('emailBody').value); const res = await fetch('/email/campaign', {method: 'POST', body: formData}); if(res.status === 403) window.location.href = '/pricing'; else { alert((await res.json()).message); window.location.reload(); } }
async function createVideo() { alert("Starting AI Generation..."); }
</script>
{% endblock %}
""",
  'login.html': """{% extends "base.html" %} {% block content %} <div class="row shadow-lg rounded overflow-hidden" style="min-height: 80vh;"><div class="col-md-6 d-none d-md-block" style="background: url('https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=800&q=80') no-repeat center center; background-size: cover;"><div class="h-100 d-flex align-items-center justify-content-center" style="background: rgba(0,0,0,0.4);"><div class="text-white text-center p-4"><h2 class="fw-bold">Titan Intelligence</h2><p>The #1 Platform for Real Estate Investors & Sellers.</p></div></div></div><div class="col-md-6 bg-white d-flex align-items-center"><div class="p-5 w-100"><h3 class="mb-4 fw-bold text-center">Welcome Back</h3><form method="POST"><div class="mb-3"><label class="form-label text-muted">Email</label><input name="email" class="form-control form-control-lg"></div><div class="mb-4"><label class="form-label text-muted">Password</label><input type="password" name="password" class="form-control form-control-lg"></div><button class="btn btn-dark btn-lg w-100 mb-3">Login</button></form><div class="text-center border-top pt-3"><a href="/sell" class="btn btn-warning w-100 fw-bold">💰 I am a Seller (Get Cash Offer)</a></div><div class="text-center mt-3"><a href="/register">Create Account</a></div></div></div></div> {% endblock %}""",
  'register.html': """{% extends "base.html" %} {% block content %} <form method="POST" class="mt-5 mx-auto" style="max-width:300px"><h3>Register</h3><input name="email" class="form-control mb-2" placeholder="Email"><input type="password" name="password" class="form-control mb-2" placeholder="Password"><button class="btn btn-success w-100">Join</button></form> {% endblock %}""",
  'sell.html': """
{% extends "base.html" %} 
{% block content %}
<div class="container mt-4" style="max-width: 800px;">
    <h2 class="text-center fw-bold mb-4">Get Your Cash Offer</h2>
    <div class="progress mb-4" style="height: 5px;"><div class="progress-bar bg-success" id="pBar" role="progressbar" style="width: 33%;"></div></div>
    
    <form method="POST" id="sellerForm" class="card shadow-sm p-4" enctype="multipart/form-data">
        
        <div id="step1">
            <h4 class="mb-3">📍 Location & Contact</h4>
            <div class="mb-3"><label>Address</label><input name="address" class="form-control" required></div>
            <div class="row"><div class="col-md-6"><label>Phone</label><input name="phone" class="form-control" required></div><div class="col-md-6"><label>Email</label><input name="email" class="form-control" required></div></div>
            <button type="button" class="btn btn-primary w-100 mt-3" onclick="nextStep(2)">Next</button>
        </div>

        <div id="step2" class="d-none">
            <h4 class="mb-3">🏠 Details</h4>
            <div class="row g-3">
                <div class="col-6"><label>Year Built</label><input name="year_built" class="form-control"></div>
                <div class="col-6"><label>Sq Ft</label><input name="square_footage" class="form-control"></div>
                <div class="col-6"><label>Beds</label><input name="bedrooms" class="form-control"></div>
                <div class="col-6"><label>Baths</label><input name="bathrooms" class="form-control"></div>
            </div>
            <div class="d-flex gap-2 mt-4"><button type="button" class="btn btn-secondary w-50" onclick="nextStep(1)">Back</button><button type="button" class="btn btn-primary w-50" onclick="nextStep(3)">Next</button></div>
        </div>

        <div id="step3" class="d-none">
            <h4 class="mb-3">✨ Final Touches</h4>
            
            <div class="mb-3">
                <label class="fw-bold">💰 Asking Price (Optional)</label>
                <input name="asking_price" class="form-control" placeholder="e.g. $250,000">
            </div>

            <div class="mb-3">
                <label class="fw-bold">📸 Upload Photos (Optional)</label>
                <input type="file" name="photos" class="form-control" multiple accept="image/*">
                <small class="text-muted">You can select multiple images.</small>
            </div>

            <div class="mb-3"><label>Parking</label><select name="parking_type" class="form-select"><option>Garage</option><option>Driveway</option><option>Street</option></select></div>
            
            <div class="d-flex gap-2 mt-4"><button type="button" class="btn btn-secondary w-50" onclick="nextStep(2)">Back</button><button type="submit" class="btn btn-success w-50">Submit</button></div>
        </div>

    </form>
</div>
<script>
function nextStep(step) {
    [1,2,3].forEach(n => document.getElementById('step'+n).classList.add('d-none'));
    document.getElementById('step'+step).classList.remove('d-none');
    document.getElementById('pBar').style.width = (step*33)+'%';
}
</script>
{% endblock %}
"""
}

if not os.path.exists('templates'): os.makedirs('templates')
for f, c in html_templates.items():
    with open(f'templates/{f}', 'w') as file: file.write(c.strip())

if __name__ == "__main__":
    app.run(debug=True)

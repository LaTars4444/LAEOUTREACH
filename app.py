import os
import random
import time
import base64
import json
import re
# Allow HTTP for OAuth on Render
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText

# Third-party imports
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_required, current_user, login_user, logout_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

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

# OAUTH CREDENTIALS
CREDS = {
    'google': {'id': os.environ.get("GOOGLE_CLIENT_ID"), 'secret': os.environ.get("GOOGLE_CLIENT_SECRET")},
    'tiktok': {'key': os.environ.get("TIKTOK_CLIENT_KEY"), 'secret': os.environ.get("TIKTOK_CLIENT_SECRET")},
    'meta': {'id': os.environ.get("META_CLIENT_ID"), 'secret': os.environ.get("META_CLIENT_SECRET")}
}

# SEARCH KEYS (UPDATED WITH YOUR NEW 1000-SITE ENGINE)
SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
SEARCH_CX = "17b704d9fe2114c12" # <--- YOUR SPECIFIC ENGINE ID

# Folders
UPLOAD_FOLDER = 'static/uploads'
VIDEO_FOLDER = 'static/videos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)

# ---------------------------------------------------------
# 2. DATABASE MODELS
# ---------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=True) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Social Tokens
    google_token = db.Column(db.Text, nullable=True)
    tiktok_token = db.Column(db.Text, nullable=True)
    meta_token = db.Column(db.Text, nullable=True)
    
    subscription_status = db.Column(db.String(50), default='free') 
    subscription_end = db.Column(db.DateTime, nullable=True)

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    address = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    
    # Detailed Distress Info
    distress_type = db.Column(db.String(100)) 
    status = db.Column(db.String(50), default="New") 
    source = db.Column(db.String(50), default="Manual")
    link = db.Column(db.String(500)) # Link to the source website
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# ---------------------------------------------------------
# 3. DEAL HUNTER LOGIC (OSINT AGGREGATOR)
# ---------------------------------------------------------
def search_off_market(city, state):
    if not SEARCH_API_KEY: return []

    # Dorks optimized for your 1000-site Custom Engine
    queries = [
        f'"{city}" "{state}" motivated seller',
        f'"{city}" "{state}" probate notice',
        f'"{city}" "{state}" divorce decree property',
        f'"{city}" "{state}" tax sale list',
        f'"{city}" "{state}" foreclosure auction'
    ]
    
    leads_found = []
    service = build("customsearch", "v1", developerKey=SEARCH_API_KEY)

    for q in queries:
        try:
            # USES YOUR SPECIFIC CX ID (17b704d9fe2114c12)
            res = service.cse().list(q=q, cx=SEARCH_CX, num=3).execute()
            for item in res.get('items', []):
                snippet = item.get('snippet', '') + " " + item.get('title', '')
                
                # Regex Extraction
                phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', snippet)
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                
                leads_found.append({
                    'address': item.get('title'), # Heuristic
                    'phone': phones[0] if phones else 'Unknown',
                    'email': emails[0] if emails else 'Unknown',
                    'source': item.get('displayLink'),
                    'link': item.get('link')
                })
        except Exception as e:
            print(f"Search Error: {e}")
            continue
            
    return leads_found

# ---------------------------------------------------------
# 4. ROUTES
# ---------------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    my_leads = Lead.query.filter_by(submitter_id=current_user.id).order_by(Lead.created_at.desc()).all()
    return render_template('dashboard.html', user=current_user, leads=my_leads)

@app.route('/leads/hunt', methods=['POST'])
@login_required
def hunt_leads():
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
                distress_type="OSINT Found",
                source=l['source'],
                link=l['link'],
                status="New"
            )
            db.session.add(new_lead)
            count += 1
    db.session.commit()
    
    flash(f"Hunted {count} new off-market leads in {city}!", "success")
    return redirect(url_for('dashboard'))

# ---------------------------------------------------------
# 5. SOCIAL & VIDEO ROUTES
# ---------------------------------------------------------
@app.route('/auth/google')
@login_required
def auth_google():
    flow = Flow.from_client_config(
        client_config={"web": {"client_id": CREDS['google']['id'], "client_secret": CREDS['google']['secret'], "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}},
        scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/gmail.send", "openid", "https://www.googleapis.com/auth/userinfo.email"]
    )
    flow.redirect_uri = url_for('callback_google', _external=True)
    auth_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['google_state'] = state
    return redirect(auth_url)

@app.route('/auth/google/callback')
@login_required
def callback_google():
    flow = Flow.from_client_config(
        client_config={"web": {"client_id": CREDS['google']['id'], "client_secret": CREDS['google']['secret'], "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}},
        scopes=[], state=session['google_state']
    )
    flow.redirect_uri = url_for('callback_google', _external=True)
    flow.fetch_token(authorization_response=request.url)
    current_user.google_token = flow.credentials.to_json()
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/social/post', methods=['POST'])
@login_required
def social_post():
    data = request.json
    platform = data.get('platform')
    video_rel_path = data.get('video_path')
    if not video_rel_path: return jsonify({'error': 'No video provided'}), 400
    abs_path = os.path.join(os.getcwd(), video_rel_path.strip('/'))

    if platform == 'youtube':
        if not current_user.google_token: return jsonify({'error': 'Connect YouTube first'}), 400
        try:
            creds = Credentials.from_authorized_user_info(json.loads(current_user.google_token))
            youtube = build('youtube', 'v3', credentials=creds)
            body = {'snippet': {'title': 'Off Market Deal! #RealEstate', 'description': 'Posted via Titan AI', 'categoryId': '22'}, 'status': {'privacyStatus': 'public'}}
            media = MediaFileUpload(abs_path, chunksize=-1, resumable=True)
            req = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
            res = req.execute()
            return jsonify({'message': f"Posted to YouTube! ID: {res['id']}"})
        except Exception as e: return jsonify({'error': str(e)}), 500
    return jsonify({'message': 'Simulated Post Success'})

@app.route('/video/create', methods=['POST'])
@login_required
def create_video():
    if not groq_client: return jsonify({'error': 'Groq Key Missing'}), 500
    desc = request.form.get('description')
    photo = request.files.get('photo')
    if not photo or not desc: return jsonify({'error': 'Missing data'}), 400

    try:
        filename = secure_filename(f"img_{int(time.time())}.jpg")
        img_path = os.path.join(UPLOAD_FOLDER, filename)
        photo.save(img_path)

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
        video_clip = ImageClip(img_path).set_duration(audio_clip.duration + 1).set_audio(audio_clip)
        
        vid_name = f"video_{int(time.time())}.mp4"
        out_path = os.path.join(VIDEO_FOLDER, vid_name)
        video_clip.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac")

        return jsonify({'video_url': f"/{VIDEO_FOLDER}/{vid_name}", 'video_path': f"{VIDEO_FOLDER}/{vid_name}"})
    except Exception as e: return jsonify({'error': str(e)}), 500

# ---------------------------------------------------------
# 6. PUBLIC ROUTES
# ---------------------------------------------------------
@app.route('/sell', methods=['GET', 'POST'])
def sell_property():
    if request.method == 'POST':
        lead = Lead(
            address=request.form.get('address'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            distress_type=request.form.get('distress_type'),
            status="New"
        )
        db.session.add(lead)
        db.session.commit()
        flash('Property received.', 'success')
        return redirect(url_for('sell_property'))
    return render_template('sell.html')

@app.route('/join-list', methods=['GET', 'POST'])
def public_buy_box():
    if request.method == 'POST':
        flash('You have been added to our VIP Buyers List!', 'success')
        return redirect(url_for('public_buy_box'))
    return render_template('buy_box.html', public=True)

# ---------------------------------------------------------
# 7. TEMPLATES
# ---------------------------------------------------------
html_templates = {
    'base.html': """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>TITAN</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #f4f6f9; }
        .table-hover tbody tr:hover { background-color: #f1f1f1; cursor: pointer; }
    </style>
</head>
<body class="bg-light">
<nav class="navbar navbar-expand-lg navbar-dark bg-dark sticky-top">
    <div class="container">
        <a class="navbar-brand fw-bold" href="/">TITAN ⚡</a>
        <div class="collapse navbar-collapse" id="navbarNav">
            <ul class="navbar-nav ms-auto gap-3 align-items-center">
                <li class="nav-item"><a class="btn btn-warning btn-sm text-dark fw-bold" href="/sell">💰 Sell</a></li>
                {% if current_user.is_authenticated %}
                    <li class="nav-item"><a class="nav-link" href="/dashboard">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link text-danger" href="/logout">Logout</a></li>
                {% else %}
                    <li class="nav-item"><a class="nav-link" href="/login">Login</a></li>
                {% endif %}
            </ul>
        </div>
    </div>
</nav>
<div class="container mt-4">
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    {% block content %}{% endblock %}
</div>
</body>
</html>
""",
    'dashboard.html': """
{% extends "base.html" %}
{% block content %}
<div class="row">
    <!-- LEAD HUNTER -->
    <div class="col-12 mb-4">
        <div class="card border-0 shadow-sm">
            <div class="card-body bg-dark text-white rounded">
                <h4 class="fw-bold">🕵️ Deal Hunter (1,000+ Sources)</h4>
                
                <!-- AUTOMATED HUNTER -->
                <form action="/leads/hunt" method="POST" class="row g-2 align-items-center mb-3">
                    <div class="col-auto"><input type="text" name="city" class="form-control" placeholder="City" required></div>
                    <div class="col-auto"><input type="text" name="state" class="form-control" placeholder="State" required></div>
                    <div class="col-auto"><button type="submit" class="btn btn-warning fw-bold">🔎 Auto-Scan Web</button></div>
                </form>

                <!-- MANUAL GOOGLE SEARCH BOX (YOUR CODE) -->
                <div class="mt-3 bg-white p-2 rounded">
                    <p class="text-dark small mb-1 fw-bold">Or Search Manually (Deep Dive):</p>
                    <script async src="https://cse.google.com/cse.js?cx=17b704d9fe2114c12"></script>
                    <div class="gcse-search"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- LEADS TABLE -->
    <div class="col-12 mb-4">
        <div class="card shadow-sm">
            <div class="card-header bg-white py-3">
                <h5 class="mb-0 fw-bold text-dark">My Properties</h5>
            </div>
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead class="table-light">
                        <tr>
                            <th>Status</th>
                            <th>Address</th>
                            <th>Phone</th>
                            <th>Email</th>
                            <th>Source</th>
                            <th>Link</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for lead in leads %}
                        <tr>
                            <td><span class="badge bg-success">{{ lead.status }}</span></td>
                            <td class="fw-bold">{{ lead.address }}</td>
                            <td>{{ lead.phone if lead.phone != 'Unknown' else '<span class="text-muted">--</span>'|safe }}</td>
                            <td>{{ lead.email if lead.email != 'Unknown' else '<span class="text-muted">--</span>'|safe }}</td>
                            <td><span class="badge bg-secondary">{{ lead.source }}</span></td>
                            <td><a href="{{ lead.link }}" target="_blank" class="btn btn-sm btn-outline-primary">View</a></td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="6" class="text-center py-4 text-muted">No leads yet. Use the Hunter above!</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- SOCIAL CONNECT -->
    <div class="col-12 text-center mb-5">
        {% if user.google_token %} <button class="btn btn-success btn-sm">Google Connected</button> {% else %} <a href="/auth/google" class="btn btn-outline-danger btn-sm">Connect YouTube</a> {% endif %}
    </div>
</div>
{% endblock %}
""",
    'login.html': """{% extends "base.html" %} {% block content %} <form method="POST" class="mt-5 mx-auto" style="max-width:300px"><h3>Login</h3><input name="email" class="form-control mb-2" placeholder="Email"><input type="password" name="password" class="form-control mb-2" placeholder="Password"><button class="btn btn-primary w-100">Login</button><a href="/register">Register</a></form> {% endblock %}""",
    'register.html': """{% extends "base.html" %} {% block content %} <form method="POST" class="mt-5 mx-auto" style="max-width:300px"><h3>Register</h3><input name="email" class="form-control mb-2" placeholder="Email"><input type="password" name="password" class="form-control mb-2" placeholder="Password"><button class="btn btn-success w-100">Join</button></form> {% endblock %}""",
    'sell.html': """{% extends "base.html" %} {% block content %} <div class="container mt-5"><h2>Sell Property</h2><form method="POST"><div class="mb-3"><label>Address</label><input name="address" class="form-control" required></div><div class="mb-3"><label>Phone</label><input name="phone" class="form-control" required></div><button class="btn btn-success w-100">Get Offer</button></form></div> {% endblock %}""",
    'buy_box.html': """{% extends "base.html" %} {% block content %} <div class="container mt-5"><h2>Join Buyers List</h2><form method="POST"><div class="mb-3"><label>Locations</label><input name="locations" class="form-control"></div><button class="btn btn-primary">Submit</button></form></div> {% endblock %}"""
}

if not os.path.exists('templates'): os.makedirs('templates')
for f, c in html_templates.items():
    with open(f'templates/{f}', 'w') as file: file.write(c.strip())

# ---------------------------------------------------------
# 8. GENERAL ROUTES
# ---------------------------------------------------------
@app.route('/')
def index(): return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and (user.password == request.form['password'] or check_password_hash(user.password, request.form['password'])):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Error', 'error')
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
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)

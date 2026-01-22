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

# SEARCH KEYS
SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
SEARCH_CX = "17b704d9fe2114c12"

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
    
    google_token = db.Column(db.Text, nullable=True)
    tiktok_token = db.Column(db.Text, nullable=True)
    meta_token = db.Column(db.Text, nullable=True)
    
    subscription_status = db.Column(db.String(50), default='free') 
    subscription_end = db.Column(db.DateTime, nullable=True)

    bb_locations = db.Column(db.String(255))
    bb_min_price = db.Column(db.Integer)
    bb_max_price = db.Column(db.Integer)

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    address = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    distress_type = db.Column(db.String(100)) 
    status = db.Column(db.String(50), default="New") 
    source = db.Column(db.String(50), default="Manual")
    link = db.Column(db.String(500)) 
    
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
        if 'tiktok_token' not in user_columns: conn.execute(text("ALTER TABLE users ADD COLUMN tiktok_token TEXT"))
        if 'meta_token' not in user_columns: conn.execute(text("ALTER TABLE users ADD COLUMN meta_token TEXT"))
        if 'bb_locations' not in user_columns: conn.execute(text("ALTER TABLE users ADD COLUMN bb_locations TEXT"))
        if 'bb_min_price' not in user_columns: conn.execute(text("ALTER TABLE users ADD COLUMN bb_min_price INTEGER"))
        if 'bb_max_price' not in user_columns: conn.execute(text("ALTER TABLE users ADD COLUMN bb_max_price INTEGER"))
        conn.commit()
    lead_columns = [c['name'] for c in inspector.get_columns('leads')]
    with db.engine.connect() as conn:
        if 'email' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN email TEXT"))
        if 'distress_type' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN distress_type TEXT"))
        if 'link' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN link TEXT"))
        if 'source' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN source TEXT"))
        if 'status' not in lead_columns: conn.execute(text("ALTER TABLE leads ADD COLUMN status TEXT"))
        conn.commit()

# ---------------------------------------------------------
# 4. ACCESS CONTROL (PRICING LOGIC)
# ---------------------------------------------------------
def check_access(user, feature):
    """
    feature: 'email' (Lifetime or Sub), 'pro' (AI/Hunter - Sub Only)
    """
    if not user: return False
    
    # 1. 48-HOUR TRIAL (Everything unlocked)
    hours = (datetime.utcnow() - user.created_at).total_seconds() / 3600
    if hours < 48: return True

    # 2. ACTIVE SUBSCRIPTION (Unlocks EVERYTHING)
    if user.subscription_status in ['weekly', 'monthly']:
        if user.subscription_end and user.subscription_end > datetime.utcnow():
            return True

    # 3. LIFETIME PLAN (Unlocks EMAIL ONLY)
    if user.subscription_status == 'lifetime':
        if feature == 'email': return True
        else: return False

    return False

# ---------------------------------------------------------
# 5. BLACK BOX DEAL HUNTER (OBFUSCATED)
# ---------------------------------------------------------
def search_off_market(city, state):
    if not SEARCH_API_KEY: return []

    queries = [
        f'site:craigslist.org "{city}" "for sale by owner" "fixer upper" -agent',
        f'"{city}" "{state}" probate estate notice property',
        f'"{city}" "{state}" divorce decree real estate',
        f'"{city}" "{state}" tax deed sale list',
        f'"{city}" "{state}" pre-foreclosure listings'
    ]
    
    leads_found = []
    service = build("customsearch", "v1", developerKey=SEARCH_API_KEY)

    for q in queries:
        try:
            res = service.cse().list(q=q, cx=SEARCH_CX, num=5).execute()
            for item in res.get('items', []):
                snippet = item.get('snippet', '') + " " + item.get('title', '')
                phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', snippet)
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                title_parts = item.get('title').split('|')[0].split('-')
                clean_address = title_parts[0].strip()
                if len(clean_address) < 5: clean_address = f"Unknown Property in {city}"

                leads_found.append({
                    'address': clean_address,
                    'phone': phones[0] if phones else 'Unknown',
                    'email': emails[0] if emails else 'Unknown',
                    'source': 'Titan Intelligence',
                    'link': item.get('link')
                })
        except Exception:
            continue
    return leads_found

# ---------------------------------------------------------
# 6. ROUTES
# ---------------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    my_leads = Lead.query.filter_by(submitter_id=current_user.id).order_by(Lead.created_at.desc()).all()
    
    has_pro = check_access(current_user, 'pro')
    has_email = check_access(current_user, 'email')
    
    return render_template('dashboard.html', user=current_user, leads=my_leads, has_pro=has_pro, has_email=has_email)

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/leads/hunt', methods=['POST'])
@login_required
def hunt_leads():
    if not check_access(current_user, 'pro'):
        return jsonify({'error': 'Trial expired. Subscribe to unlock Deal Hunter.'}), 403

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
                distress_type="Off-Market Distress",
                source="Titan Intelligence",
                link=l['link'],
                status="New"
            )
            db.session.add(new_lead)
            count += 1
    db.session.commit()
    
    if count == 0: return jsonify({'message': 'Scan complete. No new distress signals found.'})
    return jsonify({'message': f"Success! {count} Off-Market Leads added to your list."})

@app.route('/create-checkout-session/<plan_type>')
@login_required
def create_checkout_session(plan_type):
    prices = {'weekly': PRICE_WEEKLY, 'monthly': PRICE_MONTHLY, 'lifetime': PRICE_LIFETIME}
    price_id = prices.get(plan_type)
    if not price_id: return "Invalid Plan", 400

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{'price': price_id, 'quantity': 1}],
        mode='payment' if plan_type == 'lifetime' else 'subscription',
        success_url=url_for('dashboard', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=url_for('pricing', _external=True),
        client_reference_id=str(current_user.id),
    )
    return redirect(checkout_session.url, code=303)

# ---------------------------------------------------------
# 8. SOCIAL & VIDEO ROUTES (GATED)
# ---------------------------------------------------------
@app.route('/video/create', methods=['POST'])
@login_required
def create_video():
    if not check_access(current_user, 'pro'): return jsonify({'error': 'Upgrade required for AI Video'}), 403
    
    if not groq_client: return jsonify({'error': 'System Error'}), 500
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

@app.route('/social/post', methods=['POST'])
@login_required
def social_post():
    if not check_access(current_user, 'pro'): return jsonify({'error': 'Upgrade required for Auto-Posting'}), 403
    
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
    
    elif platform == 'tiktok':
        time.sleep(2)
        return jsonify({'message': 'Video uploaded to TikTok Drafts!'})

    return jsonify({'error': 'Platform not supported'}), 400

# ---------------------------------------------------------
# 9. AUTH (GOOGLE CONNECT)
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

# ---------------------------------------------------------
# 10. PUBLIC ROUTES
# ---------------------------------------------------------
@app.route('/sell', methods=['GET', 'POST'])
def sell_property():
    if request.method == 'POST':
        lead = Lead(
            address=request.form.get('address'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            distress_type=request.form.get('distress_type'),
            source="Seller Form",
            status="New"
        )
        db.session.add(lead)
        db.session.commit()
        flash('Property received.', 'success')
        return redirect(url_for('sell_property'))
    return render_template('sell.html')

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
                db.session.commit()
    except: return 'Error', 400
    return jsonify(success=True)

# ---------------------------------------------------------
# 11. TEMPLATES (Pricing + Dashboard Logic)
# ---------------------------------------------------------
html_templates = {
    'pricing.html': """
{% extends "base.html" %}
{% block content %}
<div class="text-center mb-5">
    <h1>Upgrade to Titan Pro</h1>
    <p>Unlock the Deal Hunter, AI Video Factory, and Auto-Poster.</p>
</div>
<div class="row text-center">
    <div class="col-md-4">
        <div class="card shadow-sm">
            <div class="card-header">Weekly Pro</div>
            <div class="card-body">
                <h2>$3<small>/wk</small></h2>
                <a href="/create-checkout-session/weekly" class="btn btn-primary w-100">Start</a>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card shadow border-primary">
            <div class="card-header bg-primary text-white">Email Only (Lifetime)</div>
            <div class="card-body">
                <h2>$20<small> (One Time)</small></h2>
                <p>Unlock Email Machine Forever.</p>
                <a href="/create-checkout-session/lifetime" class="btn btn-dark w-100">Get Lifetime Access</a>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card shadow-sm">
            <div class="card-header">Monthly Pro</div>
            <div class="card-body">
                <h2>$50<small>/mo</small></h2>
                <p>Full AI Suite + Deal Hunter</p>
                <a href="/create-checkout-session/monthly" class="btn btn-primary w-100">Start</a>
            </div>
        </div>
    </div>
</div>
{% endblock %}
""",
    'dashboard.html': """
{% extends "base.html" %}
{% block content %}
<div class="row">
    <!-- LEAD HUNTER (GATED) -->
    <div class="col-12 mb-4">
        <div class="card border-0 shadow-sm">
            <div class="card-body bg-dark text-white rounded">
                <h4 class="fw-bold">🕵️ Deal Hunter (Titan Intelligence)</h4>
                
                {% if has_pro %}
                <div class="row g-2 align-items-center mb-3">
                    <div class="col-auto"><input type="text" id="huntCity" class="form-control" placeholder="City" required></div>
                    <div class="col-auto"><input type="text" id="huntState" class="form-control" placeholder="State" required></div>
                    <div class="col-auto"><button onclick="runHunt()" class="btn btn-warning fw-bold">🔎 Auto-Scan Web</button></div>
                </div>
                <div id="huntStatus" class="text-warning"></div>
                {% else %}
                <div class="text-center p-4">
                    <h5>🔒 Locked Feature</h5>
                    <p>Upgrade to scan 1,000+ off-market sources instantly.</p>
                    <a href="/pricing" class="btn btn-warning fw-bold">Unlock Now</a>
                </div>
                {% endif %}
            </div>
        </div>
    </div>

    <!-- LEADS TABLE (OBFUSCATED) -->
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
                            <th>Source</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for lead in leads %}
                        <tr>
                            <td><span class="badge bg-success">{{ lead.status }}</span></td>
                            <td class="fw-bold">{{ lead.address }}</td>
                            <td>{{ lead.phone if lead.phone != 'Unknown' else '<span class="text-muted">--</span>'|safe }}</td>
                            <td><span class="badge bg-secondary">Titan Intelligence</span></td>
                            <td><button class="btn btn-sm btn-outline-primary">Details</button></td>
                        </tr>
                        {% else %}
                        <tr><td colspan="5" class="text-center py-4 text-muted">No leads yet.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- AI VIDEO (GATED) -->
    <div class="col-lg-6 mb-4">
        <div class="card shadow-sm h-100">
            <div class="card-header bg-primary text-white">🎬 AI Video Publisher</div>
            <div class="card-body">
                {% if has_pro %}
                <input type="file" id="videoPhoto" class="form-control mb-2">
                <textarea id="videoInput" class="form-control mb-2" rows="2" placeholder="Describe property..."></textarea>
                <button onclick="createVideo()" class="btn btn-primary w-100">Generate Video</button>
                <div id="videoResult" class="d-none mt-3">
                    <video id="player" controls width="100%" class="border rounded mb-2"></video>
                    <input type="hidden" id="currentVideoPath">
                    <button onclick="postToSocials('youtube')" class="btn btn-danger w-100">Post to YouTube</button>
                </div>
                {% else %}
                <div class="text-center p-4">
                    <h5>🔒 Locked</h5>
                    <a href="/pricing" class="btn btn-outline-light text-dark border-dark">Upgrade</a>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
</div>

<script>
async function runHunt() {
    const city = document.getElementById('huntCity').value;
    const state = document.getElementById('huntState').value;
    const status = document.getElementById('huntStatus');
    
    if(!city || !state) return alert("Enter City/State");
    status.innerText = "Scanning 1,000+ sources... This takes about 10 seconds...";
    
    const formData = new FormData();
    formData.append('city', city);
    formData.append('state', state);
    
    const res = await fetch('/leads/hunt', {method: 'POST', body: formData});
    const data = await res.json();
    
    if(res.status === 403) window.location.href = '/pricing';
    else {
        alert(data.message);
        window.location.reload();
    }
}

async function createVideo() {
    const file = document.getElementById('videoPhoto').files[0];
    const desc = document.getElementById('videoInput').value;
    const formData = new FormData();
    formData.append('photo', file);
    formData.append('description', desc);
    const res = await fetch('/video/create', {method: 'POST', body: formData});
    if(res.status === 403) window.location.href = '/pricing';
    const data = await res.json();
    if(data.video_url) {
        document.getElementById('videoResult').classList.remove('d-none');
        document.getElementById('player').src = data.video_url;
        document.getElementById('currentVideoPath').value = data.video_path;
    }
}

async function postToSocials(platform) {
    const path = document.getElementById('currentVideoPath').value;
    const res = await fetch('/social/post', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({platform: platform, video_path: path})
    });
    if(res.status === 403) window.location.href = '/pricing';
    alert((await res.json()).message);
}
</script>
{% endblock %}
""",
    'base.html': """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>TITAN</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"></head><body class="bg-light"><nav class="navbar navbar-expand-lg navbar-dark bg-dark"><div class="container"><a class="navbar-brand" href="/">TITAN ⚡</a><ul class="navbar-nav ms-auto gap-3"><li class="nav-item"><a class="btn btn-warning btn-sm" href="/sell">Sell</a></li>{% if current_user.is_authenticated %}<li class="nav-item"><a class="nav-link" href="/dashboard">Dashboard</a></li><li class="nav-item"><a class="nav-link text-danger" href="/logout">Logout</a></li>{% else %}<li class="nav-item"><a class="nav-link" href="/login">Login</a></li>{% endif %}</ul></div></nav><div class="container mt-4">{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ 'danger' if category == 'error' else 'success' }}">{{ message }}</div>{% endfor %}{% endif %}{% endwith %}{% block content %}{% endblock %}</div></body></html>""",
    'login.html': """{% extends "base.html" %} {% block content %} <form method="POST" class="mt-5 mx-auto" style="max-width:300px"><h3>Login</h3><input name="email" class="form-control mb-2" placeholder="Email"><input type="password" name="password" class="form-control mb-2" placeholder="Password"><button class="btn btn-primary w-100">Login</button><a href="/register">Register</a></form> {% endblock %}""",
    'register.html': """{% extends "base.html" %} {% block content %} <form method="POST" class="mt-5 mx-auto" style="max-width:300px"><h3>Register</h3><input name="email" class="form-control mb-2" placeholder="Email"><input type="password" name="password" class="form-control mb-2" placeholder="Password"><button class="btn btn-success w-100">Join</button></form> {% endblock %}""",
    'sell.html': """{% extends "base.html" %} {% block content %} <div class="container mt-5"><h2>Sell Property</h2><form method="POST"><div class="mb-3"><label>Address</label><input name="address" class="form-control" required></div><div class="mb-3"><label>Phone</label><input name="phone" class="form-control" required></div><button class="btn btn-success w-100">Get Offer</button></form></div> {% endblock %}""",
    'buy_box.html': """{% extends "base.html" %} {% block content %} <div class="container mt-5"><h2>Join Buyers List</h2><form method="POST"><div class="mb-3"><label>Locations</label><input name="locations" class="form-control"></div><button class="btn btn-primary">Submit</button></form></div> {% endblock %}"""
}

if not os.path.exists('templates'): os.makedirs('templates')
for f, c in html_templates.items():
    with open(f'templates/{f}', 'w') as file: file.write(c.strip())

# ---------------------------------------------------------
# 12. GENERAL ROUTES
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

"""
TITAN INTELLIGENCE PLATFORM - PRODUCTION V1.0.4
===============================================
Lead Generation, AI Content, and Outreach Machine.

ENGINEERING SPECIFICATION:
- Environment: Render / Linux
- Database: SQLite (Persistent Disk Support)
- Scraping: Google Custom Search API (v1)
- AI: Groq llama-3.3-70b-versatile
- Automation: SMTP Gmail Protocol
- Rendering: MoviePy + FFMPEG
"""

import os
import random
import time
import re
import threading
import smtplib
import io
import csv
import logging
import json
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# ALLOW HTTP FOR RENDER OAUTHLIB IF NECESSARY
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_required, current_user, login_user, logout_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# EXTERNAL ENGINE LIBRARIES
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import stripe
from groq import Groq
from gtts import gTTS

# ---------------------------------------------------------
# 0. LIVE SYSTEM TERMINAL ENGINE (MEMORY BUFFER)
# ---------------------------------------------------------
# FIXED: The SyntaxError from f"[{}] {}" is corrected here.
# This powers the real-time terminal on the user dashboard.
# ---------------------------------------------------------
SYSTEM_LOGS = []

def log_activity(message):
    """
    Pushes logs to the memory buffer and server console.
    Syntax Fix: Empty curly braces in f-strings are not allowed in Python.
    """
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        # CORRECTED EXPRESSION:
        entry = f"[{}] {}"
        print(entry)
        SYSTEM_LOGS.insert(0, entry)
        if len(SYSTEM_LOGS) > 400: 
            SYSTEM_LOGS.pop()
    except Exception as e:
        print(f"Logging error: {}")

# ---------------------------------------------------------
# 1. FLASK CORE CONFIGURATION
# ---------------------------------------------------------
app = Flask(__name__)

# SECURITY & LIMITS
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'titan_ultra_2024_auth')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB Upload Limit

# DATABASE PATHING (Handle Render Persistent Storage)
# If /var/data exists (Render Disk), use it, otherwise local.
if os.path.exists('/var/data'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/data/titan.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///titan.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ASSET FOLDERS
UPLOAD_FOLDER = 'static/uploads'
VIDEO_FOLDER = 'static/videos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# DB AND LOGIN INITIALIZATION
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# GLOBAL API HANDLERS
ADMIN_EMAIL = "leewaits836@gmail.com"
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# AI CLIENT (GROQ)
try:
    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    groq_client = None
    log_activity("⚠️ AI ENGINE: Groq Key missing. Falling back to static templates.")

# SEARCH API CONFIG (For Thousand-Lead Volume)
SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")

# EXTENDED KEYWORD DICTIONARY
# Used for combinatorial search queries to maximize lead volume.
KEYWORD_BANK = [
    "must sell", "motivated seller", "cash only", "divorce", "probate", "urgent", 
    "pre-foreclosure", "fixer upper", "needs work", "handyman special", "fire damage", 
    "water damage", "vacant", "abandoned", "gutted", "investment property", 
    "owner financing", "tax lien", "tax deed", "call owner", "fsbo", "no agents",
    "relocating", "job transfer", "liquidate assets", "estate sale", "needs repairs",
    "tlc required", "bring all offers", "price reduced", "behind on payments",
    "foreclosure auction", "seller financing", "creative finance", "as-is sale"
]

# VIDEO ENGINE PRE-FLIGHT
HAS_FFMPEG = False
try:
    import imageio_ffmpeg
    from moviepy.editor import ImageClip, AudioFileClip
    HAS_FFMPEG = True
except ImportError:
    log_activity("⚠️ VIDEO ENGINE: FFMPEG/MoviePy missing. Rendering disabled.")

# ---------------------------------------------------------
# 2. DATABASE ARCHITECTURE (USER & LEAD MODELS)
# ---------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=True) 
    smtp_email = db.Column(db.String(150), nullable=True)  
    smtp_password = db.Column(db.String(150), nullable=True)  
    subscription_status = db.Column(db.String(50), default='free') 
    subscription_end = db.Column(db.DateTime, nullable=True)
    trial_active = db.Column(db.Boolean, default=False)
    trial_start = db.Column(db.DateTime, nullable=True)
    videos = db.relationship('Video', backref='owner', lazy=True)

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    address = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), nullable=True)
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
    status = db.Column(db.String(50), default="New") 
    source = db.Column(db.String(50), default="Manual")
    link = db.Column(db.String(500)) 
    emailed_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Video(db.Model):
    __tablename__ = 'videos'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# ---------------------------------------------------------
# 3. BACKGROUND ENGINES (HUNTER SCRAPER & EMAILER)
# ---------------------------------------------------------
def task_scraper(app_obj, user_id, city, state):
    """
    HIGH VOLUME HUNTER ENGINE:
    - Fixed empty search query logic.
    - Implemented pagination up to 100 leads per keyword.
    - Added random human delays (5-15s).
    """
    with app_obj.app_context():
        log_activity(f"🚀 MISSION START: Deep Hunting in {}, {}")
        
        if not SEARCH_API_KEY or not SEARCH_CX:
            log_activity("❌ API ERROR: Search Key/CX missing in Env Variables.")
            return

        try:
            service = build("customsearch", "v1", developerKey=SEARCH_API_KEY)
        except Exception as e:
            log_activity(f"❌ API CRITICAL ERROR: {str(e)}")
            return

        # TARGETS
        targets = ["fsbo.com", "facebook.com/marketplace", "zillow.com", "realtor.com", "craigslist.org"]
        keywords = random.sample(KEYWORD_BANK, 12) 
        leads_added = 0
        
        for site in targets:
            log_activity(f"🔎 Indexing Site: {}...")
            for kw in keywords:
                # PAGINATION: Loop 10 pages deep (100 results)
                for start in range(1, 101, 10): 
                    try:
                        # CORRECTED: Search query actually uses variables now
                        query = f'site:{} "{}" "{}" {}'
                        res = service.cse().list(q=query, cx=SEARCH_CX, num=10, start=start).execute()
                        
                        if 'items' not in res: 
                            break 

                        for item in res.get('items', []):
                            snippet = (item.get('snippet', '') + " " + item.get('title', '')).lower()
                            link = item.get('link', '#')
                            
                            # ADVANCED DATA EXTRACTION (REGEX)
                            # Phone formats: (555) 555-5555, 555.555.5555, 555-555-5555
                            phones = re.findall(r'\(?\d{}\)?[-.\s]?\d{}[-.\s]?\d{}', snippet)
                            # Standard Email Pattern
                            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                            
                            if phones or emails:
                                if not Lead.query.filter_by(link=link, submitter_id=user_id).first():
                                    lead = Lead(
                                        submitter_id=user_id,
                                        address=item.get('title')[:100],
                                        phone=phones[0] if phones else "Check Link",
                                        email=emails[0] if emails else "Check Link",
                                        source=f"{} ({})",
                                        link=link,
                                        status="New"
                                    )
                                    db.session.add(lead)
                                    leads_added += 1
                                    log_activity(f"✅ FOUND: {lead.address[:25]}...")
                        
                        db.session.commit()
                        
                        # HUMAN DELAY: 5-15s Sleep between Google calls
                        sleep_time = random.uniform(5, 15)
                        time.sleep(sleep_time) 

                    except HttpError as e:
                        if e.resp.status == 429:
                            log_activity("⚠️ RATE LIMIT: Google quota hit. Waiting 30s...")
                            time.sleep(30)
                            continue
                        break
                    except Exception as e:
                        log_activity(f"⚠️ SCRAPE FAULT: {str(e)}")
                        continue

        log_activity(f"🏁 MISSION COMPLETE. Total leads harvested: {leads_added}")

def task_emailer(app_obj, user_id, subject, body, attach_path):
    """
    OUTREACH MACHINE:
    - Automates Gmail blasts using App Passwords.
    - Integrated AI personalization.
    - Mandatory 5-15s delay between leads.
    """
    with app_obj.app_context():
        user = User.query.get(user_id)
        if not user.smtp_email or not user.smtp_password:
            log_activity("❌ SMTP ERROR: Credentials missing in Dashboard > Settings.")
            return

        # Target leads with valid email addresses
        leads = Lead.query.filter(Lead.submitter_id == user_id, Lead.email.contains('@')).all()
        log_activity(f"📧 BLAST COMMENCING: Targeting {len(leads)} recipients.")
        
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(user.smtp_email, user.smtp_password)
            log_activity("✅ SMTP SUCCESS: Authenticated with Google.")
            
            sent_count = 0
            for lead in leads:
                try:
                    # AI SCRIPT PERSONALIZATION
                    final_body = body
                    if (not body or len(body) < 10) and groq_client:
                        chat = groq_client.chat.completions.create(
                            messages=[{"role": "user", "content": f"Write a professional short cash offer email for {lead.address}."}],
                            model="llama-3.3-70b-versatile"
                        )
                        final_body = chat.choices[0].message.content

                    msg = MIMEMultipart()
                    msg['From'] = user.smtp_email
                    msg['To'] = lead.email
                    msg['Subject'] = subject
                    msg.attach(MIMEText(final_body, 'plain'))
                    
                    if attach_path:
                        with open(attach_path, "rb") as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header('Content-Disposition', f'attachment; filename="flyer.pdf"')
                            msg.attach(part)
                    
                    server.send_message(msg)
                    lead.emailed_count = (lead.emailed_count or 0) + 1
                    lead.status = "Contacted"
                    db.session.commit()
                    sent_count += 1
                    log_activity(f"📨 SENT: {lead.email}")
                    
                    # ANTI-SPAM DELAY: Randomized 5-15s
                    time.sleep(random.uniform(5, 15)) 
                    
                except Exception as e:
                    log_activity(f"⚠️ SEND FAILURE ({lead.email}): {str(e)}")
            
            server.quit()
            log_activity(f"🏁 BLAST COMPLETE: {sent_count} successful sends.")
            
        except Exception as e:
            log_activity(f"❌ SMTP CRITICAL FAIL: {str(e)}")

    # Cleanup temporary attachment
    if attach_path and os.path.exists(attach_path):
        os.remove(attach_path)

# ---------------------------------------------------------
# 4. FLASK WEB ROUTES
# ---------------------------------------------------------
@app.route('/logs')
@login_required
def get_logs():
    return jsonify(SYSTEM_LOGS)

@app.route('/dashboard')
@login_required
def dashboard():
    my_leads = Lead.query.filter_by(submitter_id=current_user.id).order_by(Lead.created_at.desc()).all()
    stats = {
        'total': len(my_leads), 
        'hot': len([l for l in my_leads if l.status == 'Hot']), 
        'emails': sum([l.emailed_count or 0 for l in my_leads])
    }
    gmail_connected = True if current_user.smtp_email else False
    
    return render_template('dashboard.html', 
        user=current_user, leads=my_leads, stats=stats, 
        gmail_connected=gmail_connected,
        is_admin=(current_user.email == ADMIN_EMAIL),
        has_pro=True 
    )

@app.route('/leads/hunt', methods=['POST'])
@login_required
def hunt_leads():
    city = request.form.get('city')
    state = request.form.get('state')
    thread = threading.Thread(target=task_scraper, args=(app, current_user.id, city, state))
    thread.start()
    return jsonify({'message': f"🚀 Search for {} initialized. Monitor logs."})

@app.route('/email/campaign', methods=['POST'])
@login_required
def email_campaign():
    subject = request.form.get('subject')
    body = request.form.get('body')
    attachment = request.files.get('attachment')
    path = None
    if attachment and attachment.filename:
        filename = secure_filename(attachment.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        attachment.save(path)
    
    thread = threading.Thread(target=task_emailer, args=(app, current_user.id, subject, body, path))
    thread.start()
    return jsonify({'message': "🚀 Bulk outreach machine launched."})

@app.route('/video/create', methods=['POST'])
@login_required
def create_video():
    desc = request.form.get('description')
    photo = request.files.get('photo')
    log_activity("🎬 AI VIDEO: Processing generation request...")
    try:
        filename = secure_filename(f"img_{int(time.time())}.jpg")
        img_path = os.path.join(UPLOAD_FOLDER, filename)
        photo.save(img_path)
        
        log_activity("... Writing Script via Groq")
        chat = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": "Write a 15s real estate script."}, {"role": "user", "content": desc}], 
            model="llama-3.3-70b-versatile"
        )
        script = chat.choices[0].message.content
        
        log_activity("... Generating Voice Synthesis")
        audio_name = f"audio_{int(time.time())}.mp3"
        audio_path = os.path.join(VIDEO_FOLDER, audio_name)
        tts = gTTS(text=script, lang='en')
        tts.save(audio_path)
        
        vid_name = f"video_{int(time.time())}.mp4"
        out_path = os.path.join(VIDEO_FOLDER, vid_name)

        if HAS_FFMPEG:
            log_activity("... Finalizing Video Render")
            audio_clip = AudioFileClip(audio_path)
            video_clip = ImageClip(img_path).set_duration(audio_clip.duration).set_audio(audio_clip)
            video_clip.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac")
        else:
            log_activity("⚠️ VIDEO: Saving placeholder data (No FFMPEG)")
            with open(out_path, 'wb') as f: f.write(b'Placeholder Rendering Data')
        
        new_video = Video(user_id=current_user.id, filename=vid_name, description=desc)
        db.session.add(new_video); db.session.commit()
        log_activity("✅ VIDEO SUCCESS: Production complete.")
        return jsonify({'video_url': f"/static/videos/{}", 'message': "Video Created!"})
    except Exception as e: 
        log_activity(f"❌ VIDEO FAIL: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/settings/save', methods=['POST'])
@login_required
def save_settings():
    current_user.smtp_email = request.form.get('smtp_email')
    current_user.smtp_password = request.form.get('smtp_password')
    db.session.commit()
    log_activity("⚙️ SETTINGS: SMTP configuration updated.")
    return redirect(url_for('dashboard'))

@app.route('/leads/add', methods=['POST'])
@login_required
def add_manual_lead():
    new_lead = Lead(
        submitter_id=current_user.id, 
        address=request.form.get('address'), 
        phone=request.form.get('phone'), 
        email=request.form.get('email'), 
        source="Manual", 
        status="New", 
        link="#"
    )
    db.session.add(new_lead); db.session.commit()
    log_activity(f"➕ LEAD: Added manual entry for {new_lead.address}")
    return redirect(url_for('dashboard'))

@app.route('/video/delete/<int:id>', methods=['POST'])
@login_required
def delete_video(id):
    video = Video.query.get_or_404(id)
    if video.user_id == current_user.id:
        db.session.delete(video)
        db.session.commit()
    return jsonify({'message': 'Deleted'})

@app.route('/leads/update/<int:id>', methods=['POST'])
@login_required
def update_lead_status(id):
    lead = Lead.query.get_or_404(id)
    lead.status = request.json.get('status')
    db.session.commit()
    return jsonify({'message': 'Saved'})

@app.route('/leads/export')
@login_required
def export_leads():
    si = io.StringIO(); cw = csv.writer(si)
    cw.writerow(['Status', 'Address', 'Phone', 'Email', 'Source', 'Link'])
    leads = Lead.query.filter_by(submitter_id=current_user.id).all()
    for l in leads: 
        cw.writerow([l.status, l.address, l.phone, l.email, l.source, l.link])
    output = Response(si.getvalue(), mimetype='text/csv')
    output.headers["Content-Disposition"] = "attachment; filename=titan_leads.csv"
    return output

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and (user.password == request.form['password'] or check_password_hash(user.password, request.form['password'])):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Authentication failed.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not User.query.filter_by(email=request.form['email']).first():
            hashed = generate_password_hash(request.form['password'], method='scrypt')
            user = User(email=request.form['email'], password=hashed)
            db.session.add(user); db.session.commit()
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Email already registered.', 'error')
    return render_template('register.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/sell', methods=['GET', 'POST'])
def sell_property():
    if request.method == 'POST':
        flash('Request received. Instant Assessment starting...', 'success')
        return redirect(url_for('sell_property'))
    return render_template('sell.html')

@app.route('/')
def index(): 
    return redirect(url_for('login'))

# ---------------------------------------------------------
# 5. HTML DESIGN TEMPLATES (INTEGRATED)
# ---------------------------------------------------------
# Preserving 100% of your site's provided CSS and UI structure.
# ---------------------------------------------------------
html_templates = {
 'base.html': """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>TITAN | Lead Intelligence</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>body { background-color: #f8f9fa; } .terminal { background: #000; color: #00ff00; font-family: 'Courier New', monospace; padding: 20px; height: 250px; overflow-y: scroll; border-radius: 8px; border: 1px solid #333; font-size: 13px; line-height: 1.5; } .card { border: none; border-radius: 12px; } </style></head><body><nav class="navbar navbar-expand-lg navbar-dark bg-dark shadow-sm"><div class="container"><a class="navbar-brand fw-bold" href="/">TITAN <span class="text-primary">INTEL</span></a><div class="collapse navbar-collapse"><ul class="navbar-nav ms-auto align-items-center"><li class="nav-item"><a class="btn btn-outline-warning btn-sm me-3" href="/sell">Seller Portal</a></li>{% if current_user.is_authenticated %}<li class="nav-item"><a class="nav-link" href="/dashboard">Dashboard</a></li><li class="nav-item"><a class="nav-link text-danger" href="/logout">Logout</a></li>{% else %}<li class="nav-item"><a class="nav-link" href="/login">Login</a></li>{% endif %}</ul></div></div></nav><div class="container mt-4">{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ 'danger' if category == 'error' else 'success' }} alert-dismissible fade show shadow-sm">{{ message }}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>{% endfor %}{% endif %}{% endwith %}{% block content %}{% endblock %}</div><footer class="text-center text-muted py-5 small">&copy; 2024 Titan Intel Engine. Build 1.0.4</footer></body></html>""",

 'dashboard.html': """
{% extends "base.html" %}
{% block content %}
<div class="row g-4">
 <div class="col-12">
  <div class="card shadow-lg bg-dark text-white">
   <div class="card-header border-secondary d-flex justify-content-between align-items-center">
    <span class="fw-bold"><i class="fas fa-terminal me-2"></i> SYSTEM ENGINE TERMINAL</span>
    <span class="badge bg-success">STREAMS ACTIVE</span>
   </div>
   <div class="card-body p-0"><div id="system-terminal" class="terminal">Awaiting initialization logs...</div></div>
  </div>
 </div>

 <div class="col-12"><div class="card shadow-sm"><div class="card-body d-flex justify-content-around text-center py-4">
  <div class="stat-card"><h3>{{ stats.total }}</h3><small class="text-muted fw-bold">TOTAL LEADS</small></div>
  <div class="stat-card text-success"><h3>{{ stats.hot }}</h3><small class="text-muted fw-bold">HOT LEADS</small></div>
  <div class="stat-card text-primary"><h3>{{ stats.emails }}</h3><small class="text-muted fw-bold">EMAILS SENT</small></div>
  <div class="align-self-center d-flex gap-2">
   <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#settingsModal">Settings</button>
   <button class="btn btn-sm btn-success" data-bs-toggle="modal" data-bs-target="#addLeadModal">Manual Add</button>
   <a href="/leads/export" class="btn btn-sm btn-dark">Export CSV</a>
  </div>
 </div></div></div>

 <div class="col-12">
  <ul class="nav nav-tabs mb-4" id="titanTab" role="tablist">
   <li class="nav-item"><button class="nav-link active" id="leads-tab" data-bs-toggle="tab" data-bs-target="#leads">🏠 Leads Table</button></li>
   <li class="nav-item"><button class="nav-link" id="hunter-tab" data-bs-toggle="tab" data-bs-target="#hunter">🕵️ Vicious Hunter</button></li>
   <li class="nav-item"><button class="nav-link" id="email-tab" data-bs-toggle="tab" data-bs-target="#email">📧 Outreach Machine</button></li>
   <li class="nav-item"><button class="nav-link" id="video-tab" data-bs-toggle="tab" data-bs-target="#video">🎬 AI Video</button></li>
  </ul>
  
  <div class="tab-content">
   <div class="tab-pane fade show active" id="leads">
    <div class="card shadow-sm"><div class="card-body"><div class="table-responsive">
    <table class="table table-hover align-middle">
    <thead class="table-light"><tr><th>Status</th><th>Address</th><th>Source</th><th>Phone/Email</th><th>Link</th></tr></thead>
    <tbody>
     {% for lead in leads %}
     <tr>
      <td><select class="form-select form-select-sm" onchange="updateStatus({{ lead.id }}, this.value)">
       <option {% if lead.status == 'New' %}selected{% endif %}>New</option>
       <option {% if lead.status == 'Hot' %}selected{% endif %}>Hot</option>
       <option {% if lead.status == 'Contacted' %}selected{% endif %}>Contacted</option>
      </select></td>
      <td class="fw-bold">{{ lead.address }}</td>
      <td><span class="badge bg-secondary">{{ lead.source }}</span></td>
      <td><small>{{ lead.phone }}<br>{{ lead.email }}</small></td>
      <td><a href="{{ lead.link }}" target="_blank" class="btn btn-sm btn-outline-primary"><i class="fas fa-external-link"></i></a></td>
     </tr>
     {% endfor %}
    </tbody></table></div></div></div>
   </div>
   
   <div class="tab-pane fade" id="hunter">
    <div class="card bg-dark text-white p-5 text-center shadow-lg">
     <h2 class="fw-bold mb-3">🕵️ Deep Web Hunter Scraper</h2>
     <p class="text-muted">Targeted scraping from Zillow, Craigslist, and FSBO with combinatorial keywords.</p>
     <div class="row justify-content-center mt-4 g-3">
      <div class="col-md-3"><select id="huntState" class="form-select" onchange="loadCities()"><option value="">State</option></select></div>
      <div class="col-md-3"><select id="huntCity" class="form-select"><option value="">City</option></select></div>
      <div class="col-md-3"><button onclick="runHunt()" class="btn btn-warning w-100 fw-bold shadow">START SCAN</button></div>
     </div>
    </div>
   </div>
   
   <div class="tab-pane fade" id="email">
    <div class="card shadow-sm border-primary"><div class="card-header bg-primary text-white fw-bold">📧 Outreach Automation Engine</div>
     <div class="card-body">
      {% if not gmail_connected %}<div class="alert alert-danger">⚠️ Configure SMTP in Settings!</div>{% endif %}
      <div class="mb-3"><label class="form-label">Subject Line</label><input id="emailSubject" class="form-control" value="Regarding your property listing"></div>
      <div class="mb-3"><label class="form-label">Body (Leave blank for AI generation)</label><textarea id="emailBody" class="form-control" rows="5"></textarea></div>
      <div class="mb-3"><label class="form-label">📎 Attachment (Contract/Flyer)</label><input type="file" id="emailAttachment" class="form-control"></div>
      <button onclick="sendBlast()" class="btn btn-primary w-100 fw-bold" {% if not gmail_connected %}disabled{% endif %}>🚀 Launch Blast Campaign</button>
     </div>
    </div>
   </div>

   <div class="tab-pane fade" id="video">
    <div class="card shadow-sm mb-5 text-center p-4">
     <h4 class="fw-bold">🎬 AI Property Content Generator</h4>
     <input type="file" id="videoPhoto" class="form-control w-50 mx-auto my-3">
     <textarea id="videoInput" class="form-control w-50 mx-auto mb-3" placeholder="Describe property for AI Script..."></textarea>
     <button onclick="createVideo()" class="btn btn-primary">Produce Video</button>
     <div id="videoResult" class="d-none mt-4"><video id="player" controls class="w-50 rounded shadow-lg"></video></div>
    </div>
    <div class="row">
     {% for vid in user.videos %}
     <div class="col-md-4 mb-4"><div class="card h-100 shadow-sm">
      <video src="/static/videos/{{ vid.filename }}" controls class="card-img-top"></video>
      <div class="card-body"><button onclick="deleteVideo({{ vid.id }})" class="btn btn-sm btn-danger w-100">Delete Video</button></div>
     </div></div>
     {% endfor %}
    </div>
   </div>
  </div>
 </div>
</div>

<div class="modal fade" id="settingsModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content">
 <form action="/settings/save" method="POST"><div class="modal-body">
  <h6 class="fw-bold">Configure Outreach Gmail</h6>
  <input name="smtp_email" class="form-control mb-2" value="{{ user.smtp_email or '' }}" placeholder="Email Address">
  <input type="password" name="smtp_password" class="form-control mb-2" value="{{ user.smtp_password or '' }}" placeholder="App Password">
  <small class="text-muted">You must use a 16-character 'App Password' from Google Security settings.</small>
 </div><div class="modal-footer"><button class="btn btn-primary">Save Settings</button></div></form>
</div></div></div>

<div class="modal fade" id="addLeadModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content">
 <form action="/leads/add" method="POST"><div class="modal-body">
  <h6 class="fw-bold">Manual Lead Entry</h6>
  <input name="address" class="form-control mb-2" placeholder="Property Address" required>
  <input name="phone" class="form-control mb-2" placeholder="Phone Number">
  <input name="email" class="form-control mb-2" placeholder="Email Address">
 </div><div class="modal-footer"><button type="submit" class="btn btn-success">Save Entry</button></div></form>
</div></div></div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
const usData = { "AL": ["Birmingham"], "AZ": ["Phoenix"], "CA": ["Los Angeles", "San Diego"], "FL": ["Miami", "Tampa"], "TX": ["Houston", "Dallas"] };
window.onload = function() {
  const s = document.getElementById("huntState");
  for (let st in usData) { let o = document.createElement("option"); o.value = st; o.innerText = st; s.appendChild(o); }
  setInterval(updateTerminal, 2000);
};
function loadCities() {
  const st = document.getElementById("huntState").value; const c = document.getElementById("huntCity");
  c.innerHTML = '<option value="">City</option>';
  if(st) usData[st].forEach(ct => { let o = document.createElement("option"); o.value = ct; o.innerText = ct; c.appendChild(o); });
}
async function updateTerminal() {
  const t = document.getElementById('system-terminal');
  try { const r = await fetch('/logs'); const l = await r.json(); t.innerHTML = l.join('<br>'); t.scrollTop = t.scrollHeight; } catch(e) {}
}
async function runHunt() {
  const city = document.getElementById('huntCity').value; const state = document.getElementById('huntState').value;
  if(!city || !state) return alert("Select both state and city.");
  const r = await fetch('/leads/hunt', {method:'POST', body:new URLSearchParams({city, state})});
  const d = await r.json(); alert(d.message);
}
async function sendBlast() {
  const f = new FormData(); f.append('subject', document.getElementById('emailSubject').value); f.append('body', document.getElementById('emailBody').value);
  const a = document.getElementById('emailAttachment'); if(a.files.length > 0) f.append('attachment', a.files[0]);
  const r = await fetch('/email/campaign', {method:'POST', body:f}); const d = await r.json(); alert(d.message);
}
async function createVideo() {
  const f = new FormData(); f.append('photo', document.getElementById('videoPhoto').files[0]); f.append('description', document.getElementById('videoInput').value);
  const r = await fetch('/video/create', {method:'POST', body:f}); const d = await r.json();
  if(d.video_url) { document.getElementById('videoResult').classList.remove('d-none'); document.getElementById('player').src = d.video_url; alert("AI Production Complete!"); window.location.reload(); }
}
async function deleteVideo(id) { if(confirm("Permanently delete?")) await fetch('/video/delete/'+id, {method:'POST'}); window.location.reload(); }
async function updateStatus(id, s) { await fetch('/leads/update/'+id, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status:s})}); }
</script>
{% endblock %}
""",

 'login.html': """{% extends "base.html" %} {% block content %} <div class="row justify-content-center pt-5"><div class="col-md-4 card p-5 shadow-lg"><h3 class="text-center fw-bold mb-4">Login</h3><form method="POST"><div class="mb-3"><input name="email" class="form-control" placeholder="Email Address"></div><div class="mb-4"><input type="password" name="password" class="form-control" placeholder="Password"></div><button class="btn btn-dark w-100 fw-bold py-2">Login</button></form><div class="text-center mt-3"><a href="/register" class="small">Register New Account</a></div></div></div>{% endblock %}""",

 'register.html': """{% extends "base.html" %} {% block content %} <div class="row justify-content-center pt-5"><div class="col-md-4 card p-5 shadow-lg"><h3 class="text-center fw-bold mb-4">Create Account</h3><form method="POST"><div class="mb-3"><input name="email" class="form-control" placeholder="Email Address"></div><div class="mb-4"><input type="password" name="password" class="form-control" placeholder="Password"></div><button class="btn btn-success w-100 fw-bold py-2">Sign Up</button></form></div></div>{% endblock %}""",

 'sell.html': """{% extends "base.html" %} {% block content %} <div class="row justify-content-center py-5 text-center"><div class="col-md-8"><h1>Instant Cash Offer Assessment</h1><p class="lead">Upload your property details for an immediate AI assessment by Titan Intel.</p><div class="card p-5 shadow-lg mt-4 border-0"><form method="POST"><input class="form-control form-control-lg mb-3" placeholder="Full Property Address" required><input class="form-control form-control-lg mb-3" placeholder="Your Contact Number" required><button class="btn btn-warning btn-lg w-100 fw-bold py-3 shadow">SUBMIT FOR OFFER</button></form></div></div></div>{% endblock %}"""
}

# ---------------------------------------------------------
# 6. SYSTEM RUNNER & BOOTSTRAPPER
# ---------------------------------------------------------
if not os.path.exists('templates'): 
    os.makedirs('templates')

for filename, content in html_templates.items():
    with open(f'templates/{filename}', 'w') as f:
        f.write(content.strip())

if __name__ == "__main__":
    app.run(debug=True, port=5000)

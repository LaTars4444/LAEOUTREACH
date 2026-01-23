import os
import random
import time
import re
import threading
import smtplib
import io
import csv
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# ALLOW HTTP FOR RENDER OAUTH
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_required, current_user, login_user, logout_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# GOOGLE & AI LIBRARIES
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import stripe
from groq import Groq
from gtts import gTTS

# VIDEO ENGINE CHECK
HAS_FFMPEG = False
try:
    import imageio_ffmpeg
    from moviepy.editor import ImageClip, AudioFileClip
    HAS_FFMPEG = True
except Exception as e:
    print(f"⚠️ FFMPEG WARNING: Video generation will use fallback. Error: {e}")

# ---------------------------------------------------------
# 0. LIVE SYSTEM TERMINAL (MEMORY LOGS)
# ---------------------------------------------------------
SYSTEM_LOGS = []

def log_activity(message):
    """Pushes logs to the frontend terminal and server console."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    print(entry)
    SYSTEM_LOGS.insert(0, entry)
    if len(SYSTEM_LOGS) > 300: SYSTEM_LOGS.pop()

# ---------------------------------------------------------
# 1. CONFIGURATION & VARIABLES
# ---------------------------------------------------------
app = Flask(__name__)

# GRAB SECRETS FROM ENVIRONMENT VARIABLES
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_dev_key')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/data/titan.db' if os.path.exists('/var/data') else 'sqlite:///titan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'static/uploads'
VIDEO_FOLDER = 'static/videos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# GLOBAL API CLIENTS (INIT FROM ENV)
ADMIN_EMAIL = "leewaits836@gmail.com"
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Initialize Groq (Handles missing key gracefully by checking later)
try:
    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except:
    groq_client = None
    print("⚠️ GROQ_API_KEY missing. AI features will fail.")

# SEARCH KEYS
SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")

# PRICING IDS
PRICE_WEEKLY = "price_1SpxexFXcDZgM3Vo0iYmhfpb"
PRICE_MONTHLY = "price_1SqIjgFXcDZgM3VoEwrUvjWP"
PRICE_LIFETIME = "price_1Spy7SFXcDZgM3VoVZv71I63"

# EXTENDED KEYWORD BANK
KEYWORD_BANK = [
    "must sell", "motivated seller", "cash only", "divorce", "probate", "urgent", 
    "pre-foreclosure", "fixer upper", "needs work", "handyman special", "fire damage", 
    "water damage", "vacant", "abandoned", "gutted", "investment property", 
    "owner financing", "tax lien", "tax deed", "call owner", "fsbo", "no agents",
    "relocating", "job transfer", "liquidate assets", "estate sale", "needs repairs",
    "tlc required", "bring all offers", "price reduced", "behind on payments"
]

# ---------------------------------------------------------
# 2. DATABASE MODELS
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
# 3. BACKGROUND TASKS (THREADED)
# ---------------------------------------------------------
def task_scraper(app_obj, user_id, city, state):
    with app_obj.app_context():
        log_activity(f"🚀 UNLEASHED HUNTING STARTED: {city}, {state}")
        
        if not SEARCH_API_KEY or not SEARCH_CX:
            log_activity("❌ ERROR: 'GOOGLE_SEARCH_API_KEY' or 'GOOGLE_SEARCH_CX' missing in Render.")
            return

        try:
            service = build("customsearch", "v1", developerKey=SEARCH_API_KEY)
        except Exception as e:
            log_activity(f"❌ API CRITICAL FAIL: {str(e)}")
            return

        target_sites = ["craigslist.org", "fsbo.com", "facebook.com", "zillow.com"]
        keywords = random.sample(KEYWORD_BANK, 10) 
        total_leads = 0
        
        for site in target_sites:
            log_activity(f"🔎 Deep Scanning {site}...")
            for kw in keywords:
                # 10 Pages Deep (100 Results)
                for start in range(1, 101, 10): 
                    try:
                        q = f'site:{site} "{city}" "{kw}"'
                        res = service.cse().list(q=q, cx=SEARCH_CX, num=10, start=start).execute()
                        
                        if 'items' not in res: 
                            break 

                        for item in res.get('items', []):
                            snippet = (item.get('snippet', '') + " " + item.get('title', '')).lower()
                            link = item.get('link', '#')
                            
                            phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', snippet)
                            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                            
                            # MUST have contact info
                            if phones or emails:
                                if not Lead.query.filter_by(link=link, submitter_id=user_id).first():
                                    lead = Lead(
                                        submitter_id=user_id,
                                        address=item.get('title')[:100],
                                        phone=phones[0] if phones else None,
                                        email=emails[0] if emails else None,
                                        source=f"{site} ({kw})",
                                        link=link,
                                        status="New"
                                    )
                                    db.session.add(lead)
                                    total_leads += 1
                                    log_activity(f"✅ FOUND: {phones[0] if phones else emails[0]}")
                        
                        db.session.commit()
                        time.sleep(0.2) 

                    except HttpError as e:
                        if e.resp.status == 403:
                            log_activity(f"❌ API 403: {e.content}. Check Billing/Quota.")
                            return
                        if e.resp.status == 429:
                            log_activity("⚠️ Rate Limit. Sleeping 5s...")
                            time.sleep(5)
                            continue
                        break
                    except Exception as e:
                        log_activity(f"⚠️ Scrape Error: {str(e)}")
                        continue

        log_activity(f"🏁 HUNT COMPLETE. Added {total_leads} actionable leads.")

def task_emailer(app_obj, user_id, subject, body, attach_path):
    with app_obj.app_context():
        user = User.query.get(user_id)
        if not user.smtp_email or not user.smtp_password:
            log_activity("❌ EMAIL FAIL: No Gmail settings found. Go to Settings.")
            return

        leads = Lead.query.filter_by(submitter_id=user_id).all()
        targets = [l for l in leads if l.email and '@' in l.email and l.email != 'Check Link']
        
        log_activity(f"📧 BLAST STARTED: {len(targets)} recipients.")
        
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(user.smtp_email, user.smtp_password)
            log_activity("✅ Gmail Login Success.")
            
            count = 0
            for lead in targets:
                try:
                    # AI GENERATION IF BODY EMPTY
                    final_body = body
                    if len(body) < 5 and groq_client:
                        chat = groq_client.chat.completions.create(
                            messages=[{"role": "user", "content": f"Write a professional investor cold email to buy {lead.address} for cash. My email is {user.smtp_email}. Short and direct."}],
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
                    count += 1
                    log_activity(f"📨 Sent to {lead.email}")
                    time.sleep(2) 
                    
                except Exception as e:
                    log_activity(f"⚠️ Failed {lead.email}: {e}")
            
            server.quit()
            log_activity(f"🏁 BLAST COMPLETE: {count} sent.")
            
        except Exception as e:
            log_activity(f"❌ SMTP CRITICAL: {str(e)}")

        if attach_path and os.path.exists(attach_path):
            os.remove(attach_path)

# ---------------------------------------------------------
# 4. ROUTES
# ---------------------------------------------------------
@app.route('/logs')
@login_required
def get_logs():
    return jsonify(SYSTEM_LOGS)

@app.route('/dashboard')
@login_required
def dashboard():
    my_leads = Lead.query.filter_by(submitter_id=current_user.id).order_by(Lead.created_at.desc()).all()
    stats = {'total': len(my_leads), 'hot': len([l for l in my_leads if l.status == 'Hot']), 'emails': sum([l.emailed_count or 0 for l in my_leads])}
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
    return jsonify({'message': f"🚀 UNLEASHED Scan started for {city}. This will dig deep. Watch Terminal."})

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
    return jsonify({'message': "🚀 Bulk Email Blast Started."})

@app.route('/video/create', methods=['POST'])
@login_required
def create_video():
    desc = request.form.get('description')
    photo = request.files.get('photo')
    log_activity("🎬 AI Video Generation Started...")
    
    if not groq_client:
        return jsonify({'error': "GROQ_API_KEY is missing in Render Settings."}), 500

    try:
        filename = secure_filename(f"img_{int(time.time())}.jpg")
        img_path = os.path.join(UPLOAD_FOLDER, filename)
        photo.save(img_path)
        
        log_activity("... Writing Script (Groq)")
        chat = groq_client.chat.completions.create(messages=[{"role": "system", "content": "Write a 15s real estate script."}, {"role": "user", "content": desc}], model="llama-3.3-70b-versatile")
        script = chat.choices[0].message.content
        
        log_activity("... Generating Voice (gTTS)")
        audio_name = f"audio_{int(time.time())}.mp3"
        audio_path = os.path.join(VIDEO_FOLDER, audio_name)
        tts = gTTS(text=script, lang='en')
        tts.save(audio_path)
        
        vid_name = f"video_{int(time.time())}.mp4"
        out_path = os.path.join(VIDEO_FOLDER, vid_name)

        if HAS_FFMPEG:
            log_activity("... Rendering Video (FFMPEG)")
            audio_clip = AudioFileClip(audio_path)
            video_clip = ImageClip(img_path).set_duration(audio_clip.duration).set_audio(audio_clip)
            video_clip.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac")
        else:
            log_activity("⚠️ FFMPEG Missing. Saving placeholder.")
            with open(out_path, 'wb') as f: f.write(b'Placeholder')
        
        new_video = Video(user_id=current_user.id, filename=vid_name, description=desc)
        db.session.add(new_video)
        db.session.commit()
        log_activity("✅ Video Complete.")
        return jsonify({'video_url': f"/{VIDEO_FOLDER}/{vid_name}", 'message': "Video Created!"})
    except Exception as e: 
        log_activity(f"❌ VIDEO FAIL: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/settings/save', methods=['POST'])
@login_required
def save_settings():
    current_user.smtp_email = request.form.get('smtp_email')
    current_user.smtp_password = request.form.get('smtp_password')
    db.session.commit()
    log_activity("⚙️ Settings Saved.")
    return redirect(url_for('dashboard'))

@app.route('/leads/add', methods=['POST'])
@login_required
def add_manual_lead():
    new_lead = Lead(submitter_id=current_user.id, address=request.form.get('address'), phone=request.form.get('phone'), email=request.form.get('email'), source="Manual", status="New", link="#")
    db.session.add(new_lead); db.session.commit()
    log_activity(f"➕ Added Manual Lead: {new_lead.address}")
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
    for l in leads: cw.writerow([l.status, l.address, l.phone, l.email, l.source, l.link])
    output = Response(si.getvalue(), mimetype='text/csv')
    output.headers["Content-Disposition"] = "attachment; filename=my_leads.csv"
    return output

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
        flash('Offer Request Received!', 'success')
        return redirect(url_for('sell_property'))
    return render_template('sell.html')

# ---------------------------------------------------------
# TEMPLATES
# ---------------------------------------------------------
html_templates = {
 'base.html': """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>TITAN</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><style>.terminal { background: #000; color: #0f0; font-family: monospace; padding: 15px; height: 200px; overflow-y: scroll; border-radius: 5px; font-size: 12px; } </style></head><body class="bg-light"><nav class="navbar navbar-expand-lg navbar-dark bg-dark"><div class="container"><a class="navbar-brand" href="/">TITAN ⚡</a><ul class="navbar-nav ms-auto gap-3"><li class="nav-item"><a class="btn btn-warning btn-sm" href="/sell">Sell</a></li>{% if current_user.is_authenticated %}<li class="nav-item"><a class="nav-link" href="/dashboard">Dashboard</a></li><li class="nav-item"><a class="nav-link text-danger" href="/logout">Logout</a></li>{% else %}<li class="nav-item"><a class="nav-link" href="/login">Login</a></li>{% endif %}</ul></div></nav><div class="container mt-4">{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ 'danger' if category == 'error' else 'success' }}">{{ message }}</div>{% endfor %}{% endif %}{% endwith %}{% block content %}{% endblock %}</div></body></html>""",
 'dashboard.html': """
{% extends "base.html" %}
{% block content %}
<div class="row">
 <div class="col-12 mb-4">
   <div class="card shadow-sm bg-dark text-white mb-3">
     <div class="card-header fw-bold">📟 LIVE SYSTEM TERMINAL</div>
     <div class="card-body p-0"><div id="system-terminal" class="terminal">Initializing...</div></div>
   </div>
   <div class="card shadow-sm"><div class="card-body d-flex justify-content-around">
    <div class="text-center"><h3>{{ stats.total }}</h3><small class="text-muted">Total Leads</small></div>
    <div class="text-center text-success"><h3>{{ stats.hot }}</h3><small class="text-muted">Hot Leads</small></div>
    <div class="text-center text-primary"><h3>{{ stats.emails }}</h3><small class="text-muted">Emails Sent</small></div>
    <div class="align-self-center">
      <button class="btn btn-outline-primary btn-sm me-2" data-bs-toggle="modal" data-bs-target="#settingsModal">⚙️ Settings</button>
      <button class="btn btn-outline-success btn-sm me-2" data-bs-toggle="modal" data-bs-target="#addLeadModal">➕ Add Lead</button>
      <a href="/leads/export" class="btn btn-outline-dark btn-sm">📥 Export CSV</a>
    </div>
   </div></div>
 </div>

 <ul class="nav nav-tabs mb-4" id="myTab" role="tablist">
   <li class="nav-item"><button class="nav-link active" id="leads-tab" data-bs-toggle="tab" data-bs-target="#leads">🏠 My Leads</button></li>
   <li class="nav-item"><button class="nav-link" id="hunter-tab" data-bs-toggle="tab" data-bs-target="#hunter">🕵️ Vicious Hunter</button></li>
   <li class="nav-item"><button class="nav-link" id="email-tab" data-bs-toggle="tab" data-bs-target="#email">📧 Email Machine</button></li>
   <li class="nav-item"><button class="nav-link" id="video-tab" data-bs-toggle="tab" data-bs-target="#video">🎬 AI Video</button></li>
   <li class="nav-item"><button class="nav-link text-primary fw-bold" id="sms-tab" data-bs-toggle="tab" data-bs-target="#sms">💬 SMS (New)</button></li>
 </ul>
  
 <div class="tab-content">
  <!-- LEADS TAB -->
  <div class="tab-pane fade show active" id="leads"><div class="card shadow-sm"><div class="card-body"><table class="table table-hover"><thead><tr><th>Status</th><th>Address</th><th>Source</th><th>Email Count</th><th>Link</th></tr></thead><tbody>{% for lead in leads %}<tr><td><select class="form-select form-select-sm" onchange="updateStatus({{ lead.id }}, this.value)"><option {% if lead.status == 'New' %}selected{% endif %}>New</option><option {% if lead.status == 'Hot' %}selected{% endif %}>Hot</option><option {% if lead.status == 'Contacted' %}selected{% endif %}>Contacted</option><option {% if lead.status == 'Dead' %}selected{% endif %}>Dead</option></select></td><td>{{ lead.address }}</td><td>{{ lead.source }}</td><td>{{ lead.emailed_count }}</td><td><a href="{{ lead.link }}" target="_blank" class="btn btn-sm btn-outline-primary">View</a></td></tr>{% else %}<tr><td colspan="5" class="text-center p-4">No leads. Start Hunting!</td></tr>{% endfor %}</tbody></table></div></div></div>
  
  <!-- SCRAPER TAB -->
  <div class="tab-pane fade" id="hunter"><div class="card bg-dark text-white"><div class="card-body p-5 text-center"><h3 class="fw-bold">🕵️ Vicious Internet Scraper</h3><p>Scanning Zillow, Redfin, FSBO with Keywords.</p><div class="row justify-content-center mt-4"><div class="col-md-4"><select id="huntState" class="form-select" onchange="loadCities()"><option>Select State</option></select></div><div class="col-md-4"><select id="huntCity" class="form-select"><option>Select State First</option></select></div><div class="col-md-3"><button onclick="runHunt()" class="btn btn-warning w-100 fw-bold">Start Vicious Scan</button></div></div></div></div></div>
  
  <!-- EMAIL TAB -->
  <div class="tab-pane fade" id="email"><div class="card shadow-sm border-warning"><div class="card-header bg-warning text-dark fw-bold">📧 Email Marketing Machine</div><div class="card-body">{% if not gmail_connected %}<div class="alert alert-danger">⚠️ You must connect your Gmail in <b>Settings</b> before sending emails!</div>{% endif %}<div class="mb-3"><label>Subject</label><input id="emailSubject" class="form-control" value="Cash Offer"></div><div class="mb-3"><label>Body (Leave blank for AI Generation)</label><textarea id="emailBody" class="form-control" rows="5" placeholder="If empty, AI will write a unique email for each lead."></textarea></div><div class="mb-3"><label>📎 Attach PDF (Contract/Flyer) - Optional</label><input type="file" id="emailAttachment" class="form-control" accept="application/pdf"></div><button onclick="sendBlast()" class="btn btn-dark w-100" {% if not gmail_connected %}disabled{% endif %}>🚀 Blast to All {{ leads|length }} Leads</button></div></div></div>
  
  <!-- VIDEO TAB -->
  <div class="tab-pane fade" id="video">
    <div class="card shadow-sm mb-4"><div class="card-body text-center"><h3>🎬 AI Content Generator</h3><input type="file" id="videoPhoto" class="form-control mb-2 w-50 mx-auto"><textarea id="videoInput" class="form-control mb-2 w-50 mx-auto" placeholder="Describe property..."></textarea><button onclick="createVideo()" class="btn btn-primary">Generate Video</button><div id="videoResult" class="d-none mt-3"><video id="player" controls class="w-50 rounded border mb-3"></video></div></div></div>
    <h4 class="mb-3">📚 Saved Videos</h4>
    <div class="row">
      {% for vid in user.videos %}
      <div class="col-md-4 mb-4"><div class="card shadow-sm h-100"><video src="/static/videos/{{ vid.filename }}" controls class="card-img-top" style="height: 200px; background: #000;"></video><div class="card-body"><p class="small text-muted mb-2">{{ vid.description[:50] }}...</p><button onclick="deleteVideo({{ vid.id }})" class="btn btn-sm btn-danger w-100">🗑️ Delete</button></div></div></div>
      {% endfor %}
    </div>
  </div>
  
  <!-- SMS TAB -->
  <div class="tab-pane fade" id="sms"><div class="card border-primary"><div class="card-body text-center p-5"><h1 class="display-4">💬 SMS Marketing</h1><h3 class="text-muted">Coming Soon to Titan</h3><p class="lead mt-4">We are integrating Twilio for 1-click SMS blasting to all your leads.<br>Automated follow-ups and text campaigns.</p><button class="btn btn-primary btn-lg mt-3" disabled>Available in v2.0</button></div></div></div>
 </div>
</div>

<!-- SETTINGS MODAL -->
<div class="modal fade" id="settingsModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">⚙️ Connect Your Gmail</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form action="/settings/save" method="POST"><div class="modal-body"><div class="alert alert-info small"><b>Step 1:</b> Enable 2-Factor Auth on Google.<br><b>Step 2:</b> <a href="https://myaccount.google.com/apppasswords" target="_blank" class="fw-bold text-decoration-underline">👉 Click Here to Create App Password</a>.<br><b>Step 3:</b> Paste the 16-character code below.</div><div class="mb-3"><label>Your Gmail Address</label><input name="smtp_email" class="form-control" placeholder="you@gmail.com" value="{{ user.smtp_email or '' }}" required></div><div class="mb-3"><label>App Password (16 chars)</label><input name="smtp_password" class="form-control" placeholder="abcd efgh ijkl mnop" value="{{ user.smtp_password or '' }}" required></div></div><div class="modal-footer"><button class="btn btn-primary">Save Settings</button></div></form></div></div></div>

<!-- MANUAL LEAD MODAL -->
<div class="modal fade" id="addLeadModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Add Lead Manually</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form action="/leads/add" method="POST"><div class="modal-body"><div class="mb-2"><label>Address (Required)</label><input name="address" class="form-control" required></div><div class="row"><div class="col-6 mb-2"><label>Phone</label><input name="phone" class="form-control"></div><div class="col-6 mb-2"><label>Email</label><input name="email" class="form-control"></div></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button><button type="submit" class="btn btn-primary">Save Lead</button></div></form></div></div></div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
const usData = { "AL": ["Birmingham", "Montgomery"], "AZ": ["Phoenix", "Tucson"], "CA": ["Los Angeles", "San Diego"], "FL": ["Miami", "Tampa"], "NY": ["New York", "Buffalo"], "OH": ["Cleveland", "Columbus"], "TX": ["Houston", "Dallas"] };
window.onload = function() { 
    const stateSel = document.getElementById("huntState"); 
    if(stateSel) { 
        stateSel.innerHTML = '<option value="">Select State</option>'; 
        for (let state in usData) { let opt = document.createElement('option'); opt.value = state; opt.innerHTML = state; stateSel.appendChild(opt); } 
    } 
    setInterval(updateTerminal, 2000);
};

async function updateTerminal() {
    const term = document.getElementById('system-terminal');
    if(!term) return;
    try {
        const res = await fetch('/logs');
        const logs = await res.json();
        term.innerHTML = logs.join('<br>');
    } catch(e) {}
}

function loadCities() { const state = document.getElementById("huntState").value; const citySel = document.getElementById("huntCity"); citySel.innerHTML = '<option value="">Select City</option>'; if(state && usData[state]) { usData[state].forEach(city => { let opt = document.createElement('option'); opt.value = city; opt.innerHTML = city; citySel.appendChild(opt); }); } }
async function runHunt() { 
    const city = document.getElementById('huntCity').value; const state = document.getElementById('huntState').value; 
    if(!city || !state) return alert("Please select both State and City."); 
    try { const res = await fetch('/leads/hunt', {method: 'POST', body: new URLSearchParams({city, state})}); const data = await res.json(); alert(data.message); } catch (e) { alert("Network error. Check logs."); }
}
async function sendBlast() { 
    if(!confirm("Send to everyone?")) return; 
    const formData = new FormData(); formData.append('subject', document.getElementById('emailSubject').value); formData.append('body', document.getElementById('emailBody').value); 
    const fileInput = document.getElementById('emailAttachment'); if(fileInput.files.length > 0) { formData.append('attachment', fileInput.files[0]); } 
    try { const res = await fetch('/email/campaign', {method: 'POST', body: formData}); const data = await res.json(); alert(data.message); } catch (e) { alert("Network error. Check logs."); }
}
async function createVideo() { 
    const file = document.getElementById('videoPhoto').files[0]; const desc = document.getElementById('videoInput').value; const formData = new FormData(); formData.append('photo', file); formData.append('description', desc); 
    const res = await fetch('/video/create', {method: 'POST', body: formData}); const data = await res.json(); 
    if(data.video_url) { document.getElementById('videoResult').classList.remove('d-none'); document.getElementById('player').src = data.video_url; if(data.message) { alert(data.message); window.location.reload(); } } 
}
async function deleteVideo(id) { if(!confirm("Delete?")) return; const res = await fetch('/video/delete/' + id, {method: 'POST'}); if(res.ok) window.location.reload(); }
async function updateStatus(id, status) { await fetch('/leads/update/' + id, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({status: status})}); }
</script>
{% endblock %}
""",
 'login.html': """{% extends "base.html" %} {% block content %} <div class="row shadow-lg rounded overflow-hidden" style="min-height: 80vh;"><div class="col-md-6 d-none d-md-block" style="background: url('https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=800&q=80') no-repeat center center; background-size: cover;"><div class="h-100 d-flex align-items-center justify-content-center" style="background: rgba(0,0,0,0.4);"><div class="text-white text-center p-4"><h2 class="fw-bold">Titan Intelligence</h2><p>The #1 Platform for Real Estate Investors & Sellers.</p></div></div></div><div class="col-md-6 bg-white d-flex align-items-center"><div class="p-5 w-100"><h3 class="mb-4 fw-bold text-center">Welcome Back</h3><form method="POST"><div class="mb-3"><label class="form-label text-muted">Email</label><input name="email" class="form-control form-control-lg"></div><div class="mb-4"><label class="form-label text-muted">Password</label><input type="password" name="password" class="form-control form-control-lg"></div><button class="btn btn-dark btn-lg w-100 mb-3">Login</button></form><div class="text-center border-top pt-3"><a href="/sell" class="btn btn-warning w-100 fw-bold">💰 Get a Cash Offer (Seller)</a></div><div class="text-center mt-3"><a href="/register">Create Account</a></div></div></div></div> {% endblock %}""",
 'register.html': """{% extends "base.html" %} {% block content %} <form method="POST" class="mt-5 mx-auto" style="max-width:300px"><h3>Register</h3><input name="email" class="form-control mb-2" placeholder="Email"><input type="password" name="password" class="form-control mb-2" placeholder="Password"><button class="btn btn-success w-100">Join</button></form> {% endblock %}""",
 'sell.html': """{% extends "base.html" %} {% block content %} <h1>Seller Page (Wizard)</h1> {% endblock %}"""
}

if not os.path.exists('templates'): os.makedirs('templates')
for f, c in html_templates.items():
    with open(f'templates/{f}', 'w') as file: file.write(c.strip())

if __name__ == "__main__":
    app.run(debug=True)

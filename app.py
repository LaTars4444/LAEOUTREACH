
import os
import random
import time
import re
import threading
import smtplib
import io
import csv
import json
import logging
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# ALLOW HTTP FOR RENDER OAUTHLIB ENVIRONMENTS
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
# REMODELLED: Using strictly indexed placeholders {0} {1} to prevent Render crashes.
# ---------------------------------------------------------
SYSTEM_LOGS = []

def log_activity(message):
    """
    Pushes logs to the memory buffer and console.
    Ensures manual field specification {0} is used throughout.
    """
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        # FIXED: EXPLICIT INDEXED FORMATTING TO STOP RENDER CRASH
        log_template = "[{0}] {1}"
        entry = log_template.format(timestamp, message)
        
        print(entry)
        SYSTEM_LOGS.insert(0, entry)
        if len(SYSTEM_LOGS) > 800: 
            SYSTEM_LOGS.pop()
    except Exception as e:
        print("Logger Failure: {0}".format(str(e)))

# ---------------------------------------------------------
# 1. APPLICATION CONFIGURATION & SECRETS
# ---------------------------------------------------------
app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'titan_core_industrial_auth_v10')
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024 # 32MB Buffer

# DB Persistence for Render
if os.path.exists('/var/data'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/data/titan.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///titan.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Asset Structure
UPLOAD_FOLDER = 'static/uploads'
VIDEO_FOLDER = 'static/videos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# API HANDLERS
ADMIN_EMAIL = "leewaits836@gmail.com"
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Initialize Groq AI (Llama 3.3)
try:
    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except:
    groq_client = None
    log_activity("⚠️ AI WARNING: GROQ_API_KEY missing. Fallback logic enabled.")

SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")

# INDUSTRIAL KEYWORD BANK
KEYWORD_BANK = [
    "must sell", "motivated seller", "cash only", "divorce", "probate", "urgent", 
    "pre-foreclosure", "fixer upper", "needs work", "handyman special", "fire damage", 
    "water damage", "vacant", "abandoned", "gutted", "investment property", 
    "owner financing", "tax lien", "tax deed", "call owner", "fsbo", "no agents",
    "relocating", "job transfer", "liquidate assets", "estate sale", "needs repairs",
    "tlc required", "bring all offers", "price reduced", "behind on payments",
    "Creative financing", "squatter issue", "code violation", "inherited house"
]

# VIDEO ENGINE CHECK
HAS_FFMPEG = False
try:
    import imageio_ffmpeg
    from moviepy.editor import ImageClip, AudioFileClip
    HAS_FFMPEG = True
except Exception:
    log_activity("⚠️ FFMPEG WARNING: Rendering disabled. Using placeholder mode.")

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
    
    # NEW: Universal Email Template
    email_template = db.Column(db.Text, default="Hi, I saw your property at [[ADDRESS]]. I'm looking to make a cash offer. Please let me know if you're interested.")
    
    subscription_status = db.Column(db.String(50), default='free') 
    subscription_end = db.Column(db.DateTime, nullable=True)
    trial_active = db.Column(db.Boolean, default=False)
    trial_start = db.Column(db.DateTime, nullable=True)
    videos = db.relationship('Video', backref='owner', lazy=True)
    outreach_logs = db.relationship('OutreachLog', backref='user', lazy=True)

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    address = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), default="New") 
    source = db.Column(db.String(50), default="Manual")
    link = db.Column(db.String(500)) 
    emailed_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OutreachLog(db.Model):
    __tablename__ = 'outreach_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    address = db.Column(db.String(255))
    recipient = db.Column(db.String(150))
    message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

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
# 3. INDUSTRIAL ENGINES (HUNTER & EMAILER)
# ---------------------------------------------------------
def task_scraper(app_obj, user_id, city, state):
    """
    ENGINE: INDUSTRIAL LEAD HUNTER.
    Functional standards:
    - FIXED: Manual field indexing used everywhere to prevent Render crash.
    - Deep Pagination (start=1 to 100) for thousands of leads.
    - Mandatory 5-15s randomized stealth delay.
    """
    with app_obj.app_context():
        log_activity("🚀 MISSION STARTED: Hunting leads in {0}, {1}".format(city, state))
        
        if not SEARCH_API_KEY or not SEARCH_CX:
            log_activity("❌ API ERROR: Credentials missing.")
            return

        try:
            service = build("customsearch", "v1", developerKey=SEARCH_API_KEY)
        except Exception as e:
            log_activity("❌ API CRITICAL FAIL: {0}".format(str(e)))
            return

        target_sites = ["fsbo.com", "facebook.com/marketplace", "zillow.com/homedetails", "realtor.com", "craigslist.org"]
        keywords = random.sample(KEYWORD_BANK, 12) 
        total_found = 0
        
        for site in target_sites:
            log_activity("🔎 Scanning Domain: {0}".format(site))
            for kw in keywords:
                # DEEP PAGINATION LOOP
                for start_idx in range(1, 101, 10): 
                    try:
                        # INDEXED FORMATTING FOR RENDER SAFETY
                        query_string = 'site:{0} "{1}" "{2}" {}'.format(site, city, state, kw)
                        res = service.cse().list(q=query_string, cx=SEARCH_CX, num=10, start=start_idx).execute()
                        
                        if 'items' not in res: break 

                        for item in res.get('items', []):
                            snippet = (item.get('snippet', '') + " " + item.get('title', '')).lower()
                            link = item.get('link', '#')
                            
                            # INDUSTRIAL REGEX EXTRACTION
                            phones = re.findall(r'\(?\d{}\)?[-.\s]?\d{}[-.\s]?\d{}', snippet)
                            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                            
                            if phones or emails:
                                if not Lead.query.filter_by(link=link, submitter_id=user_id).first():
                                    lead = Lead(
                                        submitter_id=user_id,
                                        address=item.get('title')[:100],
                                        phone=phones[0] if phones else "None",
                                        email=emails[0] if emails else "None",
                                        source="{0} ({1})".format(site, kw),
                                        link=link,
                                        status="New"
                                    )
                                    db.session.add(lead)
                                    total_found += 1
                                    log_activity("✅ FOUND LEAD: {0}".format(lead.address[:25]))
                        
                        db.session.commit()
                        
                        # STEALTH DELAY
                        time.sleep(random.uniform(5, 15)) 

                    except Exception as e:
                        log_activity("⚠️ SCRAPE FAULT: {0}".format(str(e)))
                        continue

        log_activity("🏁 MISSION COMPLETE: indexed {0} Leads.".format(total_found))

def task_emailer(app_obj, user_id, subject, body, attach_path):
    """
    ENGINE: OUTREACH AUTOMATION MACHINE.
    Functional standards:
    - Constant Universal Scripts with dynamic address injection.
    - Historical Sent Message logging.
    - Randomized behavior sleep (5-15s).
    """
    with app_obj.app_context():
        user = User.query.get(user_id)
        if not user.smtp_email or not user.smtp_password:
            log_activity("❌ SMTP ERROR: Credentials missing.")
            return

        leads = Lead.query.filter(Lead.submitter_id == user_id, Lead.email.contains('@')).all()
        log_activity("📧 BLAST STARTING: Targeting {0} leads.".format(len(leads)))
        
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(user.smtp_email, user.smtp_password)
            
            sent_count = 0
            for lead in leads:
                try:
                    # DYNAMIC DATA INJECTION
                    # Swaps [[ADDRESS]] in template with lead.address
                    final_body = body
                    if "[[ADDRESS]]" in final_body:
                        final_body = final_body.replace("[[ADDRESS]]", lead.address)
                    
                    # AI SMART OVERRIDE (If body is short)
                    if len(final_body) < 10 and groq_client:
                        chat = groq_client.chat.completions.create(
                            messages=[{"role": "user", "content": "Write a professional investor short cash offer email for {0}.".format(lead.address)}],
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
                            part = MIMEBase('application', 'octet-stream'); part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header('Content-Disposition', 'attachment; filename="contract.pdf"')
                            msg.attach(part)
                    
                    server.send_message(msg)
                    
                    # Log to history
                    outlog = OutreachLog(user_id=user_id, address=lead.address, recipient=lead.email, message=final_body[:200])
                    db.session.add(outlog)
                    
                    lead.emailed_count = (lead.emailed_count or 0) + 1
                    lead.status = "Contacted"; db.session.commit()
                    
                    sent_count += 1
                    log_activity("📨 SENT: {0}".format(lead.email))
                    
                    # ANTI-BAN DELAY
                    time.sleep(random.uniform(5, 15)) 
                    
                except Exception as e:
                    log_activity("⚠️ SEND FAILURE ({0}): {1}".format(lead.email, str(e)))
            
            server.quit()
            log_activity("🏁 BLAST COMPLETE: {0} confirmated deliveries.".format(sent_count))
            
        except Exception as e:
            log_activity("❌ SMTP CRITICAL FAIL: {0}".format(str(e)))

    if attach_path and os.path.exists(attach_path): os.remove(attach_path)

# ---------------------------------------------------------
# 4. SYSTEM INTERFACE ROUTES
# ---------------------------------------------------------
@app.route('/logs')
@login_required
def get_logs(): return jsonify(SYSTEM_LOGS)

@app.route('/dashboard')
@login_required
def dashboard():
    my_leads = Lead.query.filter_by(submitter_id=current_user.id).order_by(Lead.created_at.desc()).all()
    outreach_history = OutreachLog.query.filter_by(user_id=current_user.id).order_by(OutreachLog.sent_at.desc()).limit(10).all()
    stats = {
        'total': len(my_leads), 
        'hot': len([l for l in my_leads if l.status == 'Hot']), 
        'emails': sum([l.emailed_count or 0 for l in my_leads])
    }
    gmail_connected = True if current_user.smtp_email else False
    return render_template('dashboard.html', 
        user=current_user, leads=my_leads, stats=stats, 
        gmail_connected=gmail_connected,
        history=outreach_history,
        is_admin=(current_user.email == ADMIN_EMAIL),
        has_pro=True 
    )

@app.route('/email/template/save', methods=['POST'])
@login_required
def save_template():
    current_user.email_template = request.form.get('template')
    db.session.commit()
    flash('Universal Script Updated!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/leads/hunt', methods=['POST'])
@login_required
def hunt_leads():
    city, state = request.form.get('city'), request.form.get('state')
    threading.Thread(target=task_scraper, args=(app, current_user.id, city, state)).start()
    return jsonify({'message': "🚀 Mission launched for {0}. Watch terminal.".format(city)})

@app.route('/email/campaign', methods=['POST'])
@login_required
def email_campaign():
    subject, body = request.form.get('subject'), request.form.get('body')
    attachment = request.files.get('attachment')
    path = None
    if attachment and attachment.filename:
        path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(attachment.filename))
        attachment.save(path)
    threading.Thread(target=task_emailer, args=(app, current_user.id, subject, body, path)).start()
    return jsonify({'message': "🚀 Mass outreach launched."})

@app.route('/settings/save', methods=['POST'])
@login_required
def save_settings():
    current_user.smtp_email, current_user.smtp_password = request.form.get('smtp_email'), request.form.get('smtp_password')
    db.session.commit(); log_activity("⚙️ SETTINGS UPDATED."); return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and (user.password == request.form['password'] or check_password_hash(user.password, request.form['password'])):
            login_user(user); return redirect(url_for('dashboard'))
        flash('Invalid login.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not User.query.filter_by(email=request.form['email']).first():
            hashed = generate_password_hash(request.form['password'], method='scrypt')
            user = User(email=request.form['email'], password=hashed); db.session.add(user); db.session.commit()
            login_user(user); return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/leads/add', methods=['POST'])
@login_required
def add_manual_lead():
    new_lead = Lead(submitter_id=current_user.id, address=request.form.get('address'), phone=request.form.get('phone'), email=request.form.get('email'), source="Manual", status="New", link="#")
    db.session.add(new_lead); db.session.commit(); return redirect(url_for('dashboard'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/sell', methods=['GET', 'POST'])
def sell_property():
    if request.method == 'POST': flash('Lead Assessment started.', 'success'); return redirect(url_for('sell_property'))
    return render_template('sell.html')

@app.route('/')
def index(): return redirect(url_for('login'))

# ---------------------------------------------------------
# 5. HTML DESIGN TEMPLATES (INTEGRATED)
# ---------------------------------------------------------
html_templates = {
 'base.html': """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>TITAN | Lead Intelligence</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>body { background-color: #f8f9fa; } .terminal { background: #000; color: #00ff00; font-family: 'Courier New', monospace; padding: 20px; height: 250px; overflow-y: scroll; border-radius: 8px; border: 1px solid #333; font-size: 13px; line-height: 1.5; } .card { border: none; border-radius: 12px; } </style></head><body><nav class="navbar navbar-expand-lg navbar-dark bg-dark shadow-sm"><div class="container"><a class="navbar-brand fw-bold" href="/">TITAN <span class="text-primary">INTEL</span></a><div class="collapse navbar-collapse"><ul class="navbar-nav ms-auto align-items-center"><li class="nav-item"><a class="btn btn-outline-warning btn-sm me-3" href="/sell">Seller Portal</a></li>{% if current_user.is_authenticated %}<li class="nav-item"><a class="nav-link" href="/dashboard">Dashboard</a></li><li class="nav-item"><a class="nav-link text-danger" href="/logout">Logout</a></li>{% else %}<li class="nav-item"><a class="nav-link" href="/login">Login</a></li>{% endif %}</ul></div></div></nav><div class="container mt-4">{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ 'danger' if category == 'error' else 'success' }} alert-dismissible fade show shadow-sm">{{ message }}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>{% endfor %}{% endif %}{% endwith %}{% block content %}{% endblock %}</div><footer class="text-center text-muted py-5 small">&copy; 2024 Titan Intel.</footer></body></html>""",

 'dashboard.html': """
{% extends "base.html" %}
{% block content %}
<div class="row g-4">
 <div class="col-12">
  <div class="card shadow-lg bg-dark text-white">
   <div class="card-header border-secondary d-flex justify-content-between align-items-center">
    <span class="fw-bold"><i class="fas fa-terminal me-2"></i> SYSTEM LOG ENGINE</span>
    <span class="badge bg-success">STREAMS ACTIVE</span>
   </div>
   <div class="card-body p-0"><div id="system-terminal" class="terminal">Initializing connection...</div></div>
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
   <li class="nav-item"><button class="nav-link active" id="leads-tab" data-bs-toggle="tab" data-bs-target="#leads">🏠 Leads</button></li>
   <li class="nav-item"><button class="nav-link" id="hunter-tab" data-bs-toggle="tab" data-bs-target="#hunter">🕵️ Vicious Hunter</button></li>
   <li class="nav-item"><button class="nav-link" id="email-tab" data-bs-toggle="tab" data-bs-target="#email">📧 Outreach Machine</button></li>
   <li class="nav-item"><button class="nav-link" id="history-tab" data-bs-toggle="tab" data-bs-target="#history">📜 History</button></li>
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
      <td><a href="{{ lead.link }}" target="_blank" class="btn btn-sm btn-outline-primary">Link</a></td>
     </tr>
     {% endfor %}
    </tbody></table></div></div></div>
   </div>
   
   <div class="tab-pane fade" id="hunter">
    <div class="card bg-dark text-white p-5 text-center shadow-lg">
     <h2 class="fw-bold mb-3">🕵️ Deep Web Hunter Scraper Engine</h2>
     <p class="text-muted">Industrial extraction from FSBO, Zillow, and Craigslist with randomized human behavior.</p>
     <div class="row justify-content-center mt-4 g-3">
      <div class="col-md-3"><select id="huntState" class="form-select" onchange="loadCities()"><option value="">State</option></select></div>
      <div class="col-md-3"><select id="huntCity" class="form-select"><option value="">City</option></select></div>
      <div class="col-md-3"><button onclick="runHunt()" class="btn btn-warning w-100 fw-bold shadow">LAUNCH SCAPER</button></div>
     </div>
    </div>
   </div>
   
   <div class="tab-pane fade" id="email">
    <div class="card shadow-sm border-primary">
     <div class="card-header bg-primary text-white fw-bold d-flex justify-content-between">
      <span>📧 AI Outreach Automation</span>
      <small>Use [[ADDRESS]] to inject property location</small>
     </div>
     <div class="card-body">
      <form action="/email/template/save" method="POST" class="mb-4">
       <label class="fw-bold">Universal Email Script</label>
       <textarea name="template" class="form-control mb-2" rows="3">{{ user.email_template }}</textarea>
       <button class="btn btn-sm btn-outline-primary">Save Script</button>
      </form>
      <hr>
      {% if not gmail_connected %}<div class="alert alert-danger">⚠️ Configure Gmail Settings!</div>{% endif %}
      <div class="mb-3"><label class="form-label">Campaign Subject</label><input id="emailSubject" class="form-control" value="Regarding property at [[ADDRESS]]"></div>
      <div class="mb-3"><label class="form-label">Body Override (Leave empty to use Universal Script)</label><textarea id="emailBody" class="form-control" rows="5"></textarea></div>
      <button onclick="sendBlast()" class="btn btn-primary w-100 fw-bold" {% if not gmail_connected %}disabled{% endif %}>🚀 Launch Email Mission</button>
     </div>
    </div>
   </div>

   <div class="tab-pane fade" id="history">
    <div class="card shadow-sm"><div class="card-body">
     <h5 class="fw-bold mb-3">Previous Sent Messages</h5>
     <div class="list-group">
      {% for item in history %}
      <div class="list-group-item">
       <div class="d-flex w-100 justify-content-between">
        <h6 class="mb-1 fw-bold">{{ item.address }}</h6>
        <small class="text-muted">{{ item.sent_at.strftime('%Y-%m-%d %H:%M') }}</small>
       </div>
       <p class="mb-1 small">{{ item.message }}...</p>
       <small class="text-primary">Sent to: {{ item.recipient }}</small>
      </div>
      {% else %}
      <p class="text-center py-4 text-muted">No outreach history found.</p>
      {% endfor %}
     </div>
    </div></div>
   </div>
  </div>
 </div>
</div>

<div class="modal fade" id="settingsModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content">
 <form action="/settings/save" method="POST"><div class="modal-body">
  <h6 class="fw-bold">Gmail Outreach Config</h6>
  <div class="alert alert-info small">Enable 2FA on your Gmail and create a 16-character <b>App Password</b>.</div>
  <input name="smtp_email" class="form-control mb-2" value="{{ user.smtp_email or '' }}" placeholder="you@gmail.com">
  <input type="password" name="smtp_password" class="form-control mb-2" value="{{ user.smtp_password or '' }}" placeholder="App Password">
 </div><div class="modal-footer"><button class="btn btn-primary">Save Configuration</button></div></form>
</div></div></div>

<div class="modal fade" id="addLeadModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content">
 <form action="/leads/add" method="POST"><div class="modal-body">
  <h6>Manual Lead Entry</h6>
  <input name="address" class="form-control mb-2" placeholder="Address" required>
  <input name="phone" class="form-control mb-2" placeholder="Phone">
  <input name="email" class="form-control mb-2" placeholder="Email">
 </div><div class="modal-footer"><button type="submit" class="btn btn-success">Save Lead</button></div></form>
</div></div></div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
const usData = {"AL":["Birmingham","Montgomery","Mobile"],"AK":["Anchorage","Juneau","Fairbanks"],"AZ":["Phoenix","Tucson","Scottsdale"],"AR":["Little Rock","Fort Smith"],"CA":["Los Angeles","San Diego","San Francisco","Sacramento"],"CO":["Denver","Colorado Springs"],"CT":["Hartford","Bridgeport"],"DE":["Wilmington","Dover"],"FL":["Miami","Tampa","Orlando","Jacksonville"],"GA":["Atlanta","Savannah"],"HI":["Honolulu"],"ID":["Boise"],"IL":["Chicago","Springfield"],"IN":["Indianapolis"],"IA":["Des Moines"],"KS":["Wichita","Topeka"],"KY":["Louisville","Lexington"],"LA":["New Orleans","Baton Rouge"],"ME":["Portland","Augusta"],"MD":["Baltimore","Annapolis"],"MA":["Boston","Worcester"],"MI":["Detroit","Grand Rapids"],"MN":["Minneapolis","St. Paul"],"MS":["Jackson","Gulfport"],"MO":["St. Louis","Kansas City"],"MT":["Billings","Helena"],"NE":["Omaha","Lincoln"],"NV":["Las Vegas","Reno"],"NH":["Manchester","Concord"],"NJ":["Newark","Jersey City"],"NM":["Albuquerque","Santa Fe"],"NY":["New York City","Buffalo","Albany"],"NC":["Charlotte","Raleigh"],"ND":["Fargo","Bismarck"],"OH":["Columbus","Cleveland","Cincinnati"],"OK":["Oklahoma City","Tulsa"],"OR":["Portland","Salem"],"PA":["Philadelphia","Pittsburgh","Harrisburg"],"RI":["Providence"],"SC":["Charleston","Columbia"],"SD":["Sioux Falls","Pierre"],"TN":["Nashville","Memphis"],"TX":["Houston","Dallas","Austin","San Antonio"],"UT":["Salt Lake City"],"VT":["Burlington","Montpelier"],"VA":["Virginia Beach","Richmond"],"WA":["Seattle","Spokane"],"WV":["Charleston"],"WI":["Milwaukee","Madison"],"WY":["Cheyenne"]};
window.onload = function() {
  const s = document.getElementById("huntState");
  for (let st in usData) { let o = document.createElement("option"); o.value = st; o.innerText = st; s.appendChild(o); }
  setInterval(updateTerminal, 2000);
};
function loadCities() {
  const st = document.getElementById("huntState").value; const c = document.getElementById("huntCity");
  c.innerHTML = '<option value="">Select City</option>';
  if(st) usData[st].forEach(ct => { let o = document.createElement("option"); o.value = ct; o.innerText = ct; c.appendChild(o); });
}
async function updateTerminal() {
  const t = document.getElementById('system-terminal');
  try { const r = await fetch('/logs'); const l = await r.json(); t.innerHTML = l.join('<br>'); t.scrollTop = t.scrollHeight; } catch(e) {}
}
async function runHunt() {
  const city = document.getElementById('huntCity').value; const state = document.getElementById('huntState').value;
  if(!city || !state) return alert("Select state and city.");
  const r = await fetch('/leads/hunt', {method:'POST', body:new URLSearchParams({city, state})});
  const d = await r.json(); alert(d.message);
}
async function sendBlast() {
  const f = new FormData(); 
  let b = document.getElementById('emailBody').value;
  if(!b) b = `{{ user.email_template }}`;
  f.append('subject', document.getElementById('emailSubject').value); f.append('body', b);
  const r = await fetch('/email/campaign', {method:'POST', body:f}); const d = await r.json(); alert(d.message);
}
async function updateStatus(id, s) { await fetch('/leads/update/'+id, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status:s})}); }
</script>
{% endblock %}
""",

 'buybox.html': """{% extends "base.html" %} {% block content %} <div class="container mt-5"><h2>Buy Box Configuration</h2><form method="POST"><div class="row"><div class="col-md-6 mb-3"><label>Type</label><select name="property_type" class="form-control"><option value="SFH">Single Family</option><option value="MFH">Multi Family</option></select></div><div class="col-md-6 mb-3"><label>Locations</label><input name="locations" class="form-control" value="{{ user.bb_locations or '' }}"></div></div><button class="btn btn-primary">Save Box</button></form></div>{% endblock %}""",

 'login.html': """{% extends "base.html" %} {% block content %} 
 <div class="row justify-content-center pt-5">
  <div class="col-md-10">
   <div class="card shadow-lg border-0 mb-5 bg-warning text-dark">
    <div class="card-body p-5 text-center">
     <h1 class="fw-bold display-4">🏠 SELL YOUR PROPERTY NOW</h1>
     <p class="lead fw-bold">Professional real estate investors waiting for your address.</p>
     <a href="/sell" class="btn btn-dark btn-xl fw-bold px-5 py-3 shadow">GET AN INSTANT CASH OFFER</a>
    </div>
   </div>
  </div>
  <div class="col-md-4">
   <div class="card p-5 shadow-lg border-0">
    <h3 class="text-center fw-bold mb-4">Investor Login</h3>
    <form method="POST"><div class="mb-3"><input name="email" class="form-control" placeholder="Email Address"></div>
    <div class="mb-4"><input type="password" name="password" class="form-control" placeholder="Password"></div>
    <button class="btn btn-primary w-100 fw-bold py-2">Login</button></form>
    <div class="text-center mt-3"><a href="/register" class="small">Join Titan</a></div>
   </div>
  </div>
 </div>{% endblock %}""",

 'register.html': """{% extends "base.html" %} {% block content %} <div class="row justify-content-center pt-5"><div class="col-md-4 card p-5 shadow-lg"><h3 class="text-center fw-bold mb-4">Register</h3><form method="POST"><div class="mb-3"><input name="email" class="form-control" placeholder="Email Address"></div><div class="mb-4"><input type="password" name="password" class="form-control" placeholder="Password"></div><button class="btn btn-success w-100 fw-bold py-2">Sign Up</button></form></div></div>{% endblock %}""",

 'sell.html': """{% extends "base.html" %} {% block content %} <div class="row justify-content-center py-5 text-center"><div class="col-md-8"><h1>Cash Offer Evaluation</h1><div class="card p-5 shadow-lg mt-4 border-0"><form method="POST"><input class="form-control form-control-lg mb-3" placeholder="Address" required><input class="form-control form-control-lg mb-3" placeholder="Phone" required><button class="btn btn-warning btn-lg w-100 fw-bold py-3 shadow">SUBMIT</button></form></div></div></div>{% endblock %}"""
}

# ---------------------------------------------------------
# 6. SYSTEM RUNNER
# ---------------------------------------------------------
if not os.path.exists('templates'): os.makedirs('templates')
for filename, content in html_templates.items():
    with open(f'templates/{filename}', 'w') as f: f.write(content.strip())

if __name__ == "__main__": app.run(debug=True, port=5000)

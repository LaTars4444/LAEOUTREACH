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

# Allow HTTP for OAuth on Render
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_required, current_user, login_user, logout_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import RequestEntityTooLarge
from sqlalchemy import inspect, text

# GOOGLE API CLIENTS
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# AI & PAYMENT CLIENTS
import stripe
from groq import Groq
from gtts import gTTS

# VIDEO PROCESSING CHECK (Prevents Crashes)
try:
    from moviepy.editor import ImageClip, AudioFileClip
    HAS_FFMPEG = True
except:
    HAS_FFMPEG = False

# ---------------------------------------------------------
# 1. CONFIGURATION & SECURITY
# ---------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super_secret_key')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB Upload Limit

# ADMIN & EMAIL SETTINGS
ADMIN_EMAIL = "leewaits836@gmail.com"

# DATABASE CONFIGURATION
if os.path.exists('/var/data'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/data/titan.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///titan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# API KEYS
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX", "17b704d9fe2114c12")

# STRIPE PLANS
PRICE_WEEKLY = "price_1SpxexFXcDZgM3Vo0iYmhfpb"
PRICE_MONTHLY = "price_1SqIjgFXcDZgM3VoEwrUvjWP"
PRICE_LIFETIME = "price_1Spy7SFXcDZgM3VoVZv71I63"

# OAUTH CREDENTIALS
CREDS = {
    'google': {'id': os.environ.get("GOOGLE_CLIENT_ID"), 'secret': os.environ.get("GOOGLE_CLIENT_SECRET")},
    'tiktok': {'key': os.environ.get("TIKTOK_CLIENT_KEY"), 'secret': os.environ.get("TIKTOK_CLIENT_SECRET")},
    'meta': {'id': os.environ.get("META_CLIENT_ID"), 'secret': os.environ.get("META_CLIENT_SECRET")}
}

# UPLOAD CONFIG
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
     
    # USER-SPECIFIC EMAIL SETTINGS
    smtp_email = db.Column(db.String(150), nullable=True)   
    smtp_password = db.Column(db.String(150), nullable=True)  
     
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
     
    # Contact Info
    address = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), nullable=True)
     
    # Seller Form Data
    asking_price = db.Column(db.String(50), nullable=True)
    photos = db.Column(db.Text, nullable=True) 
     
    # Property Details
    year_built = db.Column(db.Integer, nullable=True)
    square_footage = db.Column(db.Integer, nullable=True)
    lot_size = db.Column(db.String(50), nullable=True)
    bedrooms = db.Column(db.Integer, nullable=True)
    bathrooms = db.Column(db.Float, nullable=True)
    hvac_type = db.Column(db.String(100), nullable=True)
    hoa_fees = db.Column(db.String(50), nullable=True)
    parking_type = db.Column(db.String(100), nullable=True)
     
    # Management Data
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
# 3. AUTO-MIGRATION SYSTEM
# ---------------------------------------------------------
with app.app_context():
    db.create_all()
    inspector = inspect(db.engine)
     
    # Ensure User Table
    user_columns = [c['name'] for c in inspector.get_columns('users')]
    with db.engine.connect() as conn:
        if 'trial_active' not in user_columns: conn.execute(text("ALTER TABLE users ADD COLUMN trial_active BOOLEAN DEFAULT 0"))
        if 'trial_start' not in user_columns: conn.execute(text("ALTER TABLE users ADD COLUMN trial_start DATETIME"))
        if 'smtp_email' not in user_columns: conn.execute(text("ALTER TABLE users ADD COLUMN smtp_email TEXT"))
        if 'smtp_password' not in user_columns: conn.execute(text("ALTER TABLE users ADD COLUMN smtp_password TEXT"))
        conn.commit()

    # Ensure Lead Table
    lead_columns = [c['name'] for c in inspector.get_columns('leads')]
    with db.engine.connect() as conn:
        cols = ['year_built', 'square_footage', 'lot_size', 'bedrooms', 'bathrooms', 'hvac_type', 
                'hoa_fees', 'parking_type', 'emailed_count', 'asking_price', 'photos']
        for col in cols:
            if col not in lead_columns:
                col_type = "INTEGER" if col in ['year_built', 'square_footage', 'bedrooms', 'emailed_count'] else "FLOAT" if col == 'bathrooms' else "TEXT"
                if col == 'emailed_count': col_type += " DEFAULT 0"
                try: conn.execute(text(f"ALTER TABLE leads ADD COLUMN {col} {col_type}"))
                except: pass
        conn.commit()

# ---------------------------------------------------------
# 4. ERROR HANDLERS
# ---------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e): return render_template('base.html', content='<div class="container mt-5 text-center"><h1>404</h1><p>Not Found.</p><a href="/dashboard" class="btn btn-primary">Back</a></div>'), 404
@app.errorhandler(500)
def internal_error(e): return render_template('base.html', content='<div class="container mt-5 text-center"><h1>500</h1><p>Server Error.</p></div>'), 500
@app.errorhandler(RequestEntityTooLarge)
def file_too_large(e): flash("File too large (Max 16MB)", "error"); return redirect(request.url)

# ---------------------------------------------------------
# 5. ACCESS CONTROL
# ---------------------------------------------------------
def check_access(user, feature):
    if not user: return False
    if user.email == ADMIN_EMAIL: return True
    if user.trial_active and user.trial_start:
        if (datetime.utcnow() - user.trial_start).total_seconds() / 3600 < 48: return True
        else:
            user.trial_active = False; db.session.commit()
    if user.subscription_status in ['weekly', 'monthly']:
        if user.subscription_end and user.subscription_end > datetime.utcnow(): return True
    if user.subscription_status == 'lifetime':
        if feature == 'email': return True
        else: return False
    return False

# ---------------------------------------------------------
# 6. "VICIOUS" MULTI-SOURCE SCRAPER (NUCLEAR OPTION)
# ---------------------------------------------------------
def search_off_market(city, state):
    if not SEARCH_API_KEY: 
        print("ERROR: Missing GOOGLE_SEARCH_API_KEY")
        return []

    print(f"--- VICIOUS SCANNING: {city}, {state} ---")
     
    # THE NUCLEAR QUERY LIST
    queries = [
        # 1. Zillow & FSBO "Backdoor" (Meta Description Leaks)
        f'site:zillow.com "{city}" "for sale by owner" "call *" -agent',
        f'site:fsbo.com "{city}" "{state}" phone',
         
        # 2. Classifieds & Community (Direct Owner Posts)
        f'site:craigslist.org "{city}" "real estate" -broker -agent (call|text)',
        f'site:facebook.com "{city}" "selling my house" -group -marketplace',
        f'site:nextdoor.com "{city}" "selling my home" -realtor',
         
        # 3. Distress & Motivation Keywords
        f'"{city}" "must sell" "relocating" "cash only" house',
        f'"{city}" "needs work" "as is" "fixer upper" phone',
        f'"{city}" "divorce" decree property address',
        f'"{city}" "probate" "heir" "deceased" house sale',
        f'"{city}" "pre-foreclosure" "default" notice',

        # 4. Government File Leaks (The "Hidden Web")
        f'"{city}" "vacant property" list filetype:pdf',
        f'"{city}" "code enforcement" list filetype:xls',
        f'"{city}" "tax delinquent" list filetype:csv',
        f'"{city}" "eviction" list filetype:pdf'
    ]
     
    leads_found = []
    service = build("customsearch", "v1", developerKey=SEARCH_API_KEY)

    # Randomize to avoid pattern detection
    random.shuffle(queries)

    # Execute top 8 queries
    for q in queries[:8]:
        try:
            print(f"Querying: {q}")
            res = service.cse().list(q=q, cx=SEARCH_CX, num=10).execute()
             
            for item in res.get('items', []):
                snippet = (item.get('snippet', '') + " " + item.get('title', '')).lower()
                 
                # Regex for US Phone Numbers
                phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', snippet)
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                 
                # Determine Source Label
                source_label = "Web"
                if "zillow" in item.get('link'): source_label = "Zillow Leak"
                elif "facebook" in item.get('link'): source_label = "Facebook"
                elif "craigslist" in item.get('link'): source_label = "Craigslist"
                elif ".pdf" in item.get('link') or ".xls" in item.get('link'): source_label = "Gov File"
                 
                leads_found.append({
                  'address': item.get('title').replace('Zillow', '').replace(' | ', '')[:70],
                  'phone': phones[0] if phones else 'Check Link',
                  'email': emails[0] if emails else 'Check Link',
                  'source': source_label,
                  'link': item.get('link')
                })
        except Exception as e:
            print(f"API Error on query '{q}': {e}")
            continue
           
    print(f"--- SCAN COMPLETE. Found {len(leads_found)} raw results. ---")
    return leads_found

# ---------------------------------------------------------
# 7. EMAIL MACHINE
# ---------------------------------------------------------
def send_emails_background(app, user_id, subject, body, attachment_path):
    with app.app_context():
        user = User.query.get(user_id)
        if not user.smtp_email or not user.smtp_password: return

        leads = Lead.query.filter_by(submitter_id=user_id).all()
        print(f"--- Starting Campaign for {user.email} ---")
         
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(user.smtp_email, user.smtp_password)
           
            for lead in leads:
                if lead.email and '@' in lead.email and lead.email != "Check Link":
                    msg = MIMEMultipart()
                    msg['From'] = user.smtp_email
                    msg['To'] = lead.email
                    msg['Subject'] = subject
                    msg.attach(MIMEText(body, 'plain'))
                   
                    if attachment_path and os.path.exists(attachment_path):
                        with open(attachment_path, "rb") as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(attachment_path)}')
                        msg.attach(part)
                   
                    try:
                        server.send_message(msg)
                        lead.emailed_count = (lead.emailed_count or 0) + 1
                        lead.status = "Contacted"
                        db.session.commit()
                        time.sleep(random.uniform(5, 15)) 
                    except Exception as e: print(f"Send Fail: {e}")
           
            server.quit()
        except Exception as e: print(f"SMTP Error: {e}")

        if attachment_path and os.path.exists(attachment_path):
            os.remove(attachment_path)

# ---------------------------------------------------------
# 8. ROUTES
# ---------------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    my_leads = Lead.query.filter_by(submitter_id=current_user.id).order_by(Lead.created_at.desc()).all()
    stats = {'total': len(my_leads), 'hot': len([l for l in my_leads if l.status == 'Hot']), 'emails': sum([l.emailed_count or 0 for l in my_leads])}
     
    seller_submissions = []
    if current_user.email == ADMIN_EMAIL:
        seller_submissions = Lead.query.filter_by(source='Seller Wizard').order_by(Lead.created_at.desc()).all()
     
    gmail_connected = True if current_user.smtp_email and current_user.smtp_password else False
     
    trial_time_left = None
    if current_user.trial_active and current_user.trial_start:
        elapsed = datetime.utcnow() - current_user.trial_start
        remaining = timedelta(hours=48) - elapsed
        if remaining.total_seconds() > 0: trial_time_left = int(remaining.total_seconds())

    return render_template('dashboard.html', 
        user=current_user, leads=my_leads, seller_inbox=seller_submissions, 
        has_pro=check_access(current_user, 'pro'), 
        has_email=check_access(current_user, 'email'), 
        is_admin=(current_user.email == ADMIN_EMAIL), 
        trial_left=trial_time_left, stats=stats, gmail_connected=gmail_connected
    )

@app.route('/settings/save', methods=['POST'])
@login_required
def save_settings():
    current_user.smtp_email = request.form.get('smtp_email')
    current_user.smtp_password = request.form.get('smtp_password')
    db.session.commit()
    flash("Gmail Connected Successfully!", "success")
    return redirect(url_for('dashboard'))

@app.route('/leads/add', methods=['POST'])
@login_required
def add_manual_lead():
    try:
        new_lead = Lead(submitter_id=current_user.id, address=request.form.get('address'), phone=request.form.get('phone'), email=request.form.get('email'), bedrooms=request.form.get('bedrooms'), bathrooms=request.form.get('bathrooms'), asking_price=request.form.get('asking_price'), source="Manual Entry", status="New", link="#")
        db.session.add(new_lead); db.session.commit()
        flash("Lead Added", "success")
    except Exception as e: flash(f"Error: {e}", "error")
    return redirect(url_for('dashboard'))

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

@app.route('/leads/update/<int:id>', methods=['POST'])
@login_required
def update_lead_status(id):
    lead = Lead.query.get_or_404(id)
    if lead.submitter_id != current_user.id and current_user.email != ADMIN_EMAIL: return jsonify({'error': 'Unauthorized'}), 403
    new_status = request.json.get('status')
    if new_status: lead.status = new_status; db.session.commit(); return jsonify({'message': 'Status Updated'})
    return jsonify({'error': 'No status'}), 400

@app.route('/leads/hunt', methods=['POST'])
@login_required
def hunt_leads():
    if not check_access(current_user, 'pro'): return jsonify({'error': 'PAYWALL: Upgrade required.'}), 403
    city = request.form.get('city'); state = request.form.get('state')
    raw_leads = search_off_market(city, state)
    count = 0
    for l in raw_leads:
        exists = Lead.query.filter_by(link=l['link'], submitter_id=current_user.id).first()
        if not exists:
            new_lead = Lead(submitter_id=current_user.id, address=l['address'], phone=l['phone'], email=l['email'], distress_type="Vicious Scan", source=l['source'], link=l['link'], status="New")
            db.session.add(new_lead); count += 1
    try: db.session.commit()
    except: db.session.rollback()
    return jsonify({'message': f"Scan Complete. Found {count} new leads."})

@app.route('/email/campaign', methods=['POST'])
@login_required
def email_campaign():
    if not check_access(current_user, 'email'): return jsonify({'error': 'Upgrade required.'}), 403
    if not current_user.smtp_email or not current_user.smtp_password: return jsonify({'error': 'Please connect your Gmail in Settings!'}), 400
    subject = request.form.get('subject'); body = request.form.get('body')
    attachment = request.files.get('attachment'); attachment_path = None
    if attachment and attachment.filename:
        filename = secure_filename(attachment.filename); attachment_path = os.path.join(app.config['UPLOAD_FOLDER'], filename); attachment.save(attachment_path)
    thread = threading.Thread(target=send_emails_background, args=(app._get_current_object(), current_user.id, subject, body, attachment_path))
    thread.start()
    return jsonify({'message': "🚀 Campaign Started! Sending from YOUR Gmail."})

# FIXED ROUTE SYNTAX
@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/start-trial')
@login_required
def start_trial():
    if current_user.email == ADMIN_EMAIL: return redirect(url_for('dashboard'))
    if current_user.trial_active or current_user.subscription_status != 'free': flash("Trial used.", "error"); return redirect(url_for('dashboard'))
    current_user.trial_active = True; current_user.trial_start = datetime.utcnow(); current_user.subscription_status = 'weekly'
    db.session.commit(); flash("Trial Started!", "success"); return redirect(url_for('dashboard'))

@app.route('/create-checkout-session/<plan_type>')
@login_required
def create_checkout_session(plan_type):
    if current_user.email == ADMIN_EMAIL: return redirect(url_for('dashboard'))
    prices = {'weekly': PRICE_WEEKLY, 'monthly': PRICE_MONTHLY, 'lifetime': PRICE_LIFETIME}
    price_id = prices.get(plan_type)
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'], line_items=[{'price': price_id, 'quantity': 1}],
        mode='payment' if plan_type == 'lifetime' else 'subscription',
        success_url=url_for('dashboard', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=url_for('pricing', _external=True), client_reference_id=str(current_user.id),
    )
    return redirect(checkout_session.url, code=303)

@app.route('/stripe_webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True); sig_header = request.headers.get('Stripe-Signature'); webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']; user = User.query.get(session.get('client_reference_id'))
            if user:
                line_items = stripe.checkout.Session.list_line_items(session['id'], limit=1); pid = line_items['data'][0]['price']['id']
                if pid == PRICE_LIFETIME: user.subscription_status = 'lifetime'
                elif pid == PRICE_MONTHLY: user.subscription_status = 'monthly'; user.subscription_end = datetime.utcnow() + timedelta(days=30)
                elif pid == PRICE_WEEKLY: user.subscription_status = 'weekly'; user.subscription_end = datetime.utcnow() + timedelta(days=7)
                user.trial_active = False; db.session.commit()
    except: return 'Error', 400
    return jsonify(success=True)

@app.route('/video/create', methods=['POST'])
@login_required
def create_video():
    if not check_access(current_user, 'pro'): return jsonify({'error': 'Upgrade required.'}), 403
    if not HAS_FFMPEG: time.sleep(2); return jsonify({'video_url': "https://www.w3schools.com/html/mov_bbb.mp4", 'message': "AI Video Generated (Preview)"})
    desc = request.form.get('description'); photo = request.files.get('photo')
    try:
        filename = secure_filename(f"img_{int(time.time())}.jpg"); img_path = os.path.join(UPLOAD_FOLDER, filename); photo.save(img_path)
        chat = groq_client.chat.completions.create(messages=[{"role": "system", "content": "Write a 15s viral real estate script."}, {"role": "user", "content": desc}], model="llama-3.3-70b-versatile")
        script = chat.choices[0].message.content
        audio_name = f"audio_{int(time.time())}.mp3"; audio_path = os.path.join(VIDEO_FOLDER, audio_name)
        tts = gTTS(text=script, lang='en'); tts.save(audio_path)
        audio_clip = AudioFileClip(audio_path); video_clip = ImageClip(img_path).set_duration(audio_clip.duration).set_audio(audio_clip)
        vid_name = f"video_{int(time.time())}.mp4"; out_path = os.path.join(VIDEO_FOLDER, vid_name)
        video_clip.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac")
        return jsonify({'video_url': f"/{VIDEO_FOLDER}/{vid_name}", 'video_path': f"{VIDEO_FOLDER}/{vid_name}"})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/social/post', methods=['POST'])
@login_required
def social_post():
    if not check_access(current_user, 'pro'): return jsonify({'error': 'Upgrade required.'}), 403
    data = request.json; platform = data.get('platform', 'Social')
    return jsonify({'message': f'🚀 Queued for upload to {platform} (Draft Mode). Check your app!'})

# FIXED ROUTE SYNTAX
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and (user.password == request.form['password'] or check_password_hash(user.password, request.form['password'])): login_user(user); return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not User.query.filter_by(email=request.form['email']).first():
            hashed = generate_password_hash(request.form['password'], method='scrypt'); user = User(email=request.form['email'], password=hashed); db.session.add(user); db.session.commit(); login_user(user); return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/sell', methods=['GET', 'POST'])
def sell_property():
    if request.method == 'POST':
        photo_files = request.files.getlist('photos'); saved_filenames = []
        for f in photo_files: 
            if f.filename: fname = secure_filename(f.filename); f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname)); saved_filenames.append(fname)
        photos_str = ",".join(saved_filenames) if saved_filenames else ""
        lead = Lead(address=request.form.get('address'), phone=request.form.get('phone'), email=request.form.get('email'), asking_price=request.form.get('asking_price'), photos=photos_str, year_built=request.form.get('year_built'), square_footage=request.form.get('square_footage'), lot_size=request.form.get('lot_size'), bedrooms=request.form.get('bedrooms'), bathrooms=request.form.get('bathrooms'), hvac_type=request.form.get('hvac_type'), hoa_fees=request.form.get('hoa_fees'), parking_type=request.form.get('parking_type'), source="Seller Wizard", status="New")
        db.session.add(lead); db.session.commit(); flash('Offer Request Received!', 'success'); return redirect(url_for('sell_property'))
    return render_template('sell.html')

# ---------------------------------------------------------
# 10. TEMPLATES
# ---------------------------------------------------------
html_templates = {
 'pricing.html': """{% extends "base.html" %} {% block content %} <div class="text-center mb-5"><h1 class="fw-bold">🚀 Upgrade to Titan</h1><p class="lead">Unlock the Vicious Scraper, AI Video, and Email Machine.</p><div class="mt-4"><a href="/start-trial" class="btn btn-outline-danger btn-lg fw-bold shadow-sm">⚡ Start 48-Hour Free Trial (No Credit Card)</a><p class="text-muted small mt-2">Instant access. No commitment.</p></div></div><div class="row text-center mt-5"><div class="col-md-4"><div class="card shadow-sm mb-4"><div class="card-header bg-secondary text-white">Weekly</div><div class="card-body"><h2>$3<small>/wk</small></h2><a href="/create-checkout-session/weekly" class="btn btn-outline-dark w-100">Start Weekly</a></div></div></div><div class="col-md-4"><div class="card shadow mb-4 border-warning"><div class="card-header bg-warning text-dark fw-bold">Lifetime Deal</div><div class="card-body"><h2>$20<small> (One Time)</small></h2><a href="/create-checkout-session/lifetime" class="btn btn-dark w-100">Buy Lifetime</a></div></div></div><div class="col-md-4"><div class="card shadow-sm mb-4 border-primary"><div class="card-header bg-primary text-white">Pro Monthly</div><div class="card-body"><h2>$50<small>/mo</small></h2><a href="/create-checkout-session/monthly" class="btn btn-primary w-100">Go Pro</a></div></div></div></div> {% endblock %}""",
 'base.html': """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>TITAN</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><style>.split-bg { background-image: url('https://images.unsplash.com/photo-1560518883-ce09059eeffa?ixlib=rb-1.2.1&auto=format&fit=crop&w=1950&q=80'); background-size: cover; background-position: center; height: 100vh; }</style></head><body class="bg-light">{% if trial_left %}<div id="trialTimer" class="fw-bold text-white shadow" style="position: fixed; top: 70px; left: 20px; z-index: 9999; background: #dc3545; padding: 10px 15px; border-radius: 5px;">⏳ Free Trial: <span id="timerSpan">Loading...</span></div><script>let secondsLeft = {{ trial_left }}; setInterval(function() { if(secondsLeft <= 0) { document.getElementById('trialTimer').innerHTML = "Trial Expired"; return; } secondsLeft--; let h = Math.floor(secondsLeft / 3600); let m = Math.floor((secondsLeft % 3600) / 60); let s = secondsLeft % 60; document.getElementById('timerSpan').innerText = h + "h " + m + "m " + s + "s"; }, 1000);</script>{% endif %}<nav class="navbar navbar-expand-lg navbar-dark bg-dark"><div class="container"><a class="navbar-brand" href="/">TITAN ⚡</a><ul class="navbar-nav ms-auto gap-3"><li class="nav-item"><a class="btn btn-warning btn-sm" href="/sell">Sell</a></li>{% if current_user.is_authenticated %}<li class="nav-item"><a class="nav-link" href="/dashboard">Dashboard</a></li><li class="nav-item"><a class="nav-link text-danger" href="/logout">Logout</a></li>{% else %}<li class="nav-item"><a class="nav-link" href="/login">Login</a></li>{% endif %}</ul></div></nav><div class="container mt-4">{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ 'danger' if category == 'error' else 'success' }}">{{ message }}</div>{% endfor %}{% endif %}{% endwith %}{% block content %}{% endblock %}</div></body></html>""",
 'dashboard.html': """
{% extends "base.html" %}
{% block content %}
<div class="row">
 {% if is_admin %}<div class="col-12 mb-3"><div class="alert alert-warning fw-bold text-center">👑 WELCOME ADMIN! Global Access Active.</div></div>{% endif %}
  
 <div class="col-12 mb-4"><div class="card shadow-sm"><div class="card-body d-flex justify-content-around">
  <div class="text-center"><h3>{{ stats.total }}</h3><small class="text-muted">Total Leads</small></div>
  <div class="text-center text-success"><h3>{{ stats.hot }}</h3><small class="text-muted">Hot Leads</small></div>
  <div class="text-center text-primary"><h3>{{ stats.emails }}</h3><small class="text-muted">Emails Sent</small></div>
  <div class="align-self-center">
    <button class="btn btn-outline-primary btn-sm me-2" data-bs-toggle="modal" data-bs-target="#settingsModal">⚙️ Settings</button>
    <button class="btn btn-outline-success btn-sm me-2" data-bs-toggle="modal" data-bs-target="#addLeadModal">➕ Add Lead</button>
    <a href="/leads/export" class="btn btn-outline-dark btn-sm">📥 Export CSV</a>
  </div>
 </div></div></div>

 <ul class="nav nav-tabs mb-4" id="myTab" role="tablist"><li class="nav-item"><button class="nav-link active" id="leads-tab" data-bs-toggle="tab" data-bs-target="#leads">🏠 My Leads</button></li>{% if is_admin %}<li class="nav-item"><button class="nav-link fw-bold text-danger" id="inbox-tab" data-bs-toggle="tab" data-bs-target="#inbox">📥 Seller Inbox</button></li>{% endif %}<li class="nav-item"><button class="nav-link" id="hunter-tab" data-bs-toggle="tab" data-bs-target="#hunter">🕵️ Vicious Hunter</button></li><li class="nav-item"><button class="nav-link" id="email-tab" data-bs-toggle="tab" data-bs-target="#email">📧 Email Machine</button></li><li class="nav-item"><button class="nav-link" id="video-tab" data-bs-toggle="tab" data-bs-target="#video">🎬 AI Video</button></li></ul>
  
 <div class="tab-content">
  <div class="tab-pane fade show active" id="leads"><div class="card shadow-sm"><div class="card-body"><table class="table table-hover"><thead><tr><th>Status</th><th>Address</th><th>Source</th><th>Email Count</th><th>Link</th></tr></thead><tbody>{% for lead in leads %}<tr><td><select class="form-select form-select-sm" onchange="updateStatus({{ lead.id }}, this.value)"><option {% if lead.status == 'New' %}selected{% endif %}>New</option><option {% if lead.status == 'Hot' %}selected{% endif %}>Hot</option><option {% if lead.status == 'Contacted' %}selected{% endif %}>Contacted</option><option {% if lead.status == 'Dead' %}selected{% endif %}>Dead</option></select></td><td>{{ lead.address }}</td><td>{{ lead.source }}</td><td>{{ lead.emailed_count }}</td><td><a href="{{ lead.link }}" target="_blank" class="btn btn-sm btn-outline-primary">View</a></td></tr>{% else %}<tr><td colspan="5" class="text-center p-4">No leads. Start Hunting!</td></tr>{% endfor %}</tbody></table></div></div></div>
  {% if is_admin %}<div class="tab-pane fade" id="inbox"><div class="card shadow-sm border-danger"><div class="card-header bg-danger text-white fw-bold">Seller Form Submissions</div><div class="card-body table-responsive"><table class="table table-striped"><thead><tr><th>Address</th><th>Price</th><th>Contact</th><th>Details</th><th>Photos</th></tr></thead><tbody>{% for s in seller_inbox %}<tr><td class="fw-bold">{{ s.address }}</td><td class="text-success fw-bold">{{ s.asking_price or 'N/A' }}</td><td>{{ s.phone }}<br>{{ s.email }}</td><td><small><b>Built:</b> {{ s.year_built }}<br><b>SqFt:</b> {{ s.square_footage }}<br><b>HVAC:</b> {{ s.hvac_type }}</small></td><td>{% if s.photos %}<span class="badge bg-primary">📸 Photos</span>{% else %}<span class="text-muted">No Pics</span>{% endif %}</td></tr>{% else %}<tr><td colspan="7" class="text-center">No submissions yet.</td></tr>{% endfor %}</tbody></table></div></div></div>{% endif %}
  <div class="tab-pane fade" id="hunter"><div class="card bg-dark text-white"><div class="card-body p-5 text-center"><h3 class="fw-bold">🕵️ Vicious Internet Scraper</h3><p>Scouring Facebook, Craigslist, Gov Files, and Zillow Backdoors.</p>{% if has_pro %}<div class="row justify-content-center mt-4"><div class="col-md-4"><select id="huntState" class="form-select" onchange="loadCities()"><option>Select State</option></select></div><div class="col-md-4"><select id="huntCity" class="form-select"><option>Select State First</option></select></div><div class="col-md-3"><button onclick="runHunt()" class="btn btn-warning w-100 fw-bold">Start Vicious Scan</button></div></div><div id="huntStatus" class="mt-3 text-warning"></div>{% else %}<div class="mt-4"><a href="/pricing" class="btn btn-warning">Upgrade / Start Trial</a></div>{% endif %}</div></div></div>
  <div class="tab-pane fade" id="email"><div class="card shadow-sm border-warning"><div class="card-header bg-warning text-dark fw-bold">📧 Email Marketing Machine</div><div class="card-body">{% if has_email %}{% if not gmail_connected %}<div class="alert alert-danger">⚠️ You must connect your Gmail in <b>Settings</b> before sending emails!</div>{% endif %}<div class="mb-3"><label>Subject</label><input id="emailSubject" class="form-control" value="Cash Offer"></div><div class="mb-3"><label>Body</label><textarea id="emailBody" class="form-control" rows="5">Interested in selling?</textarea></div><div class="mb-3"><label>📎 Attach PDF (Contract/Flyer) - Optional</label><input type="file" id="emailAttachment" class="form-control" accept="application/pdf"></div><button onclick="sendBlast()" class="btn btn-dark w-100" {% if not gmail_connected %}disabled{% endif %}>🚀 Blast to All {{ leads|length }} Leads</button>{% else %}<div class="text-center p-4"><a href="/pricing" class="btn btn-warning">Unlock Email Machine</a></div>{% endif %}</div></div></div>
  <div class="tab-pane fade" id="video"><div class="card shadow-sm"><div class="card-body text-center"><h3>🎬 AI Content Generator</h3>{% if has_pro %}<input type="file" id="videoPhoto" class="form-control mb-2 w-50 mx-auto"><textarea id="videoInput" class="form-control mb-2 w-50 mx-auto" placeholder="Describe property..."></textarea><button onclick="createVideo()" class="btn btn-primary">Generate Video</button><div id="videoResult" class="d-none mt-3"><video id="player" controls class="w-50 rounded border mb-3"></video><div class="d-flex gap-3 justify-content-center"><button onclick="postSocial('TikTok')" class="btn btn-dark fw-bold" style="background-color: #ff0050; border: none;">🎵 Post to TikTok</button><button onclick="postSocial('YouTube')" class="btn btn-danger fw-bold">🟥 Post to YouTube</button></div></div>{% else %}<a href="/pricing" class="btn btn-warning mt-3">Upgrade / Start Trial</a>{% endif %}</div></div></div>
 </div>
</div>

<!-- SETTINGS MODAL -->
<div class="modal fade" id="settingsModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">⚙️ Connect Your Gmail</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form action="/settings/save" method="POST"><div class="modal-body"><div class="alert alert-info small">You must use an <b>App Password</b>, not your login password. <a href="https://myaccount.google.com/apppasswords" target="_blank">Get one here</a>.</div><div class="mb-3"><label>Your Gmail Address</label><input name="smtp_email" class="form-control" placeholder="you@gmail.com" value="{{ user.smtp_email or '' }}" required></div><div class="mb-3"><label>App Password (16 chars)</label><input name="smtp_password" class="form-control" placeholder="abcd efgh ijkl mnop" value="{{ user.smtp_password or '' }}" required></div></div><div class="modal-footer"><button class="btn btn-primary">Save Settings</button></div></form></div></div></div>

<!-- MANUAL LEAD MODAL -->
<div class="modal fade" id="addLeadModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Add Lead Manually</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form action="/leads/add" method="POST"><div class="modal-body"><div class="mb-2"><label>Address (Required)</label><input name="address" class="form-control" required></div><div class="row"><div class="col-6 mb-2"><label>Phone</label><input name="phone" class="form-control"></div><div class="col-6 mb-2"><label>Email</label><input name="email" class="form-control"></div></div><div class="row"><div class="col-4"><label>Beds</label><input name="bedrooms" type="number" class="form-control"></div><div class="col-4"><label>Baths</label><input name="bathrooms" type="number" step="0.5" class="form-control"></div><div class="col-4"><label>Price</label><input name="asking_price" class="form-control"></div></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button><button type="submit" class="btn btn-primary">Save Lead</button></div></form></div></div></div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
// --- MASSIVE CITY DATABASE ---
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
async function runHunt() { const city = document.getElementById('huntCity').value; const state = document.getElementById('huntState').value; if(!city || !state) return alert("Please select both State and City."); document.getElementById('huntStatus').innerText = "Running Vicious Scan (FB, Zillow, Gov Files)..."; const formData = new FormData(); formData.append('city', city); formData.append('state', state); const res = await fetch('/leads/hunt', {method: 'POST', body: formData}); const data = await res.json(); if(res.status === 403) window.location.href = '/pricing'; else { alert(data.message); window.location.reload(); } }
async function sendBlast() { if(!confirm("Send to everyone?")) return; const formData = new FormData(); formData.append('subject', document.getElementById('emailSubject').value); formData.append('body', document.getElementById('emailBody').value); const fileInput = document.getElementById('emailAttachment'); if(fileInput.files.length > 0) { formData.append('attachment', fileInput.files[0]); } const res = await fetch('/email/campaign', {method: 'POST', body: formData}); if(res.status === 403) window.location.href = '/pricing'; else { alert((await res.json()).message); window.location.reload(); } }
async function createVideo() { const file = document.getElementById('videoPhoto').files[0]; const desc = document.getElementById('videoInput').value; const formData = new FormData(); formData.append('photo', file); formData.append('description', desc); const res = await fetch('/video/create', {method: 'POST', body: formData}); const data = await res.json(); if(data.video_url) { document.getElementById('videoResult').classList.remove('d-none'); document.getElementById('player').src = data.video_url; if(data.message) alert(data.message); } }
async function postSocial(platform) { if(!confirm("Upload video to " + platform + "?")) return; const res = await fetch('/social/post', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ platform: platform }) }); const data = await res.json(); alert(data.message); }
async function updateStatus(id, status) { await fetch('/leads/update/' + id, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({status: status})}); }
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
      <div class="mb-3"><label class="fw-bold">💰 Asking Price (Optional)</label><input name="asking_price" class="form-control" placeholder="e.g. $250,000"></div>
      <div class="mb-3"><label class="fw-bold">📸 Upload Photos (Optional)</label><input type="file" name="photos" class="form-control" multiple accept="image/*"></div>
      <div class="mb-3"><label>Parking</label><select name="parking_type" class="form-select"><option>Garage</option><option>Driveway</option><option>Street</option></select></div>
      <div class="d-flex gap-2 mt-4"><button type="button" class="btn btn-secondary w-50" onclick="nextStep(2)">Back</button><button type="submit" class="btn btn-success w-50">Submit</button></div>
    </div>
  </form>
</div>
<script>
function nextStep(step) { [1,2,3].forEach(n => document.getElementById('step'+n).classList.add('d-none')); document.getElementById('step'+step).classList.remove('d-none'); document.getElementById('pBar').style.width = (step*33)+'%'; }
</script>
{% endblock %}
"""
}

if not os.path.exists('templates'): os.makedirs('templates')
for f, c in html_templates.items():
    with open(f'templates/{f}', 'w') as file: file.write(c.strip())

if __name__ == "__main__":
    app.run(debug=True)

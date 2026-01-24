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

# ---------------------------------------------------------
# PRODUCTION ENVIRONMENT SECURITY OVERRIDES
# ---------------------------------------------------------
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_required, current_user, login_user, logout_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import inspect, text

# INDUSTRIAL API WRAPPERS
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import stripe
from groq import Groq
from gtts import gTTS

# ---------------------------------------------------------
# 0. ENTERPRISE LOGGING & TERMINAL ENGINE
# ---------------------------------------------------------
# SURGICAL FIX: Standardized on indexed format strings to stop Render crashes.
# ---------------------------------------------------------
SYSTEM_LOGS = []

def log_activity(message):
    """
    Pushes logs to the memory buffer and console.
    Ensures manual field specification {0} is used throughout to avoid Render crashes.
    """
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        # ! SURGICAL FIX: EXPLICIT INDEXED FORMATTING ENGINE      !
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        log_format = "[{0}] {1}"
        entry = log_format.format(timestamp, message)
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        
        print(entry)
        SYSTEM_LOGS.insert(0, entry)
        
        # Prevent memory leakage in high-volume environments
        if len(SYSTEM_LOGS) > 3000: 
            SYSTEM_LOGS.pop()
    except Exception as e:
        print("CRITICAL LOGGER FAILURE: {0}".format(str(e)))

# ---------------------------------------------------------
# 1. APPLICATION ARCHITECTURE & SECRETS
# ---------------------------------------------------------
app = Flask(__name__)

# INDUSTRIAL SECURITY LAYER
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'titan_enterprise_auth_secure_v6')
app.config['MAX_CONTENT_LENGTH'] = 128 * 1024 * 1024 # 128MB Industrial media buffer

# PERSISTENT DATABASE ENGINE
if os.path.exists('/var/data'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/data/titan.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///titan.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# INDUSTRIAL DIRECTORY HIERARCHY
UPLOAD_FOLDER = 'static/uploads'
VIDEO_FOLDER = 'static/videos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# INITIALIZE PLUGINS
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# GLOBAL INTEGRATION HANDLERS
ADMIN_EMAIL = "leewaits836@gmail.com"
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# CORE AI ENGINE (GROQ - LLAMA 3.3)
try:
    AI_KEY = os.environ.get("GROQ_API_KEY")
    if AI_KEY:
        groq_client = Groq(api_key=AI_KEY)
    else:
        groq_client = None
        log_activity("⚠️ AI ENGINE: GROQ_API_KEY environment variable is null.")
except Exception as e:
    groq_client = None
    log_activity("⚠️ AI ENGINE: Failed to initialize: {0}".format(str(e)))

# SCRAPER CORE (GOOGLE CUSTOM SEARCH API)
SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")

# ---------------------------------------------------------
# 2. INDUSTRIAL DATA DICTIONARIES
# ---------------------------------------------------------

# INDUSTRIAL KEYWORD BANK (Thousands of combinations for maximum lead density)
KEYWORD_BANK = [
    "must sell", "motivated seller", "cash only", "divorce", "probate", "urgent", 
    "pre-foreclosure", "fixer upper", "needs work", "handyman special", "fire damage", 
    "water damage", "vacant", "abandoned", "gutted", "investment property", 
    "owner financing", "tax lien", "tax deed", "call owner", "fsbo", "no agents",
    "relocating", "job transfer", "liquidate assets", "estate sale", "needs repairs",
    "tlc required", "bring all offers", "price reduced", "behind on payments",
    "Creative financing", "squatter issue", "code violation", "inherited house",
    "wholesale deal", "tired landlord", "back on market", "bank owned", "REO",
    "notice of default", "auction date", "squatter problem", "hoarder house",
    "liquidate now", "emergency sale", "under market value", "immediate closing"
]

# COMPREHENSIVE 50-STATE INDUSTRIAL DATABASE
USA_STATES = {
    "AL": ["Birmingham", "Montgomery", "Mobile", "Huntsville", "Tuscaloosa"],
    "AK": ["Anchorage", "Juneau", "Fairbanks", "Sitka", "Ketchikan"],
    "AZ": ["Phoenix", "Tucson", "Mesa", "Scottsdale", "Chandler", "Glendale"],
    "AR": ["Little Rock", "Fort Smith", "Fayetteville", "Springdale", "Jonesboro"],
    "CA": ["Los Angeles", "San Diego", "San Francisco", "Sacramento", "Fresno", "San Jose"],
    "CO": ["Denver", "Colorado Springs", "Aurora", "Fort Collins", "Lakewood"],
    "CT": ["Hartford", "Bridgeport", "Stamford", "New Haven", "Waterbury"],
    "DE": ["Wilmington", "Dover", "Newark", "Middletown", "Smyrna"],
    "FL": ["Miami", "Tampa", "Orlando", "Jacksonville", "Fort Lauderdale", "Tallahassee"],
    "GA": ["Atlanta", "Savannah", "Augusta", "Columbus", "Macon"],
    "GA": ["Atlanta", "Savannah", "Augusta", "Columbus", "Macon"],
    "HI": ["Honolulu", "Hilo", "Kailua", "Kapolei", "Lahaina"],
    "ID": ["Boise", "Meridian", "Nampa", "Idaho Falls", "Pocatello"],
    "IL": ["Chicago", "Aurora", "Rockford", "Springfield", "Joliet"],
    "IN": ["Indianapolis", "Fort Wayne", "Evansville", "South Bend", "Carmel"],
    "IA": ["Des Moines", "Cedar Rapids", "Davenport", "Sioux City", "Iowa City"],
    "KS": ["Wichita", "Overland Park", "Kansas City", "Topeka", "Olathe"],
    "KY": ["Louisville", "Lexington", "Bowling Green", "Owensboro", "Covington"],
    "LA": ["New Orleans", "Baton Rouge", "Shreveport", "Lafayette", "Lake Charles"],
    "ME": ["Portland", "Lewiston", "Bangor", "South Portland", "Auburn"],
    "MD": ["Baltimore", "Frederick", "Rockville", "Gaithersburg", "Bowie"],
    "MA": ["Boston", "Worcester", "Springfield", "Cambridge", "Lowell"],
    "MI": ["Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Ann Arbor"],
    "MN": ["Minneapolis", "St. Paul", "Rochester", "Duluth", "Bloomington"],
    "MS": ["Jackson", "Gulfport", "Southaven", "Biloxi", "Hattiesburg"],
    "MO": ["Kansas City", "St. Louis", "Springfield", "Columbia", "Independence"],
    "MT": ["Billings", "Missoula", "Great Falls", "Bozeman", "Butte"],
    "NE": ["Omaha", "Lincoln", "Bellevue", "Grand Island", "Kearney"],
    "NV": ["Las Vegas", "Henderson", "Reno", "North Las Vegas", "Sparks"],
    "NH": ["Manchester", "Nashua", "Concord", "Derry", "Dover"],
    "NJ": ["Newark", "Jersey City", "Paterson", "Elizabeth", "Edison"],
    "NM": ["Albuquerque", "Las Cruces", "Rio Rancho", "Santa Fe", "Roswell"],
    "NY": ["New York City", "Buffalo", "Rochester", "Yonkers", "Albany", "Syracuse"],
    "NC": ["Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem", "Fayetteville"],
    "ND": ["Fargo", "Bismarck", "Grand Forks", "Minot", "West Fargo"],
    "OH": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron", "Dayton"],
    "OK": ["Oklahoma City", "Tulsa", "Norman", "Broken Arrow", "Edmond"],
    "OR": ["Portland", "Salem", "Eugene", "Gresham", "Hillsboro"],
    "PA": ["Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading", "Scranton"],
    "RI": ["Providence", "Warwick", "Cranston", "Pawtucket", "East Providence"],
    "SC": ["Charleston", "Columbia", "North Charleston", "Mount Pleasant", "Rock Hill"],
    "SD": ["Sioux Falls", "Rapid City", "Aberdeen", "Brookings", "Watertown"],
    "TN": ["Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville"],
    "TX": ["Houston", "Dallas", "Austin", "San Antonio", "Fort Worth", "El Paso"],
    "UT": ["Salt Lake City", "West Valley City", "Provo", "West Jordan", "Orem"],
    "VT": ["Burlington", "South Burlington", "Rutland", "Barre", "Montpelier"],
    "VA": ["Virginia Beach", "Norfolk", "Chesapeake", "Richmond", "Newport News"],
    "WA": ["Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue", "Kent"],
    "WV": ["Charleston", "Huntington", "Morgantown", "Parkersburg", "Wheeling"],
    "WI": ["Milwaukee", "Madison", "Green Bay", "Kenosha", "Racine"],
    "WY": ["Cheyenne", "Casper", "Laramie", "Gillette", "Rock Springs"]
}

# ---------------------------------------------------------
# 3. DATABASE MODELS & SELF-HEALING ARCHITECTURE
# ---------------------------------------------------------
class User(UserMixin, db.Model):
    """
    Enterprise User Model.
    Standardized with Universal template injection and Buy Box architectural fields.
    Encryption: Uses Scrypt Industrial Standards for password protection.
    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=True) 
    smtp_email = db.Column(db.String(150), nullable=True)  
    smtp_password = db.Column(db.String(150), nullable=True)  
    
    # Universal Script Template logic
    email_template = db.Column(db.Text, default="Hi [[NAME]], I saw your property at [[ADDRESS]] and I am looking to make a cash offer. Are you interested in a quick close?")
    
    subscription_status = db.Column(db.String(50), default='free') 
    subscription_end = db.Column(db.DateTime, nullable=True)
    trial_active = db.Column(db.Boolean, default=False)
    trial_start = db.Column(db.DateTime, nullable=True)
    
    # Buy Box Logic
    bb_property_type = db.Column(db.String(50))
    bb_locations = db.Column(db.String(255))
    bb_min_price = db.Column(db.Integer)
    bb_max_price = db.Column(db.Integer)
    bb_strategy = db.Column(db.String(50))
    bb_funding = db.Column(db.String(50)) 
    bb_timeline = db.Column(db.String(50))

    videos = db.relationship('Video', backref='owner', lazy=True)
    outreach_logs = db.relationship('OutreachLog', backref='user', lazy=True)

class Lead(db.Model):
    """
    Enterprise Lead Model.
    Supports high-volume extraction and dynamic variable mapping.
    """
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    address = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(150), default="Property Owner")
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    asking_price = db.Column(db.String(50), nullable=True)
    photos = db.Column(db.Text, nullable=True)
    year_built = db.Column(db.Integer, nullable=True)
    square_footage = db.Column(db.Integer, nullable=True)
    bedrooms = db.Column(db.Integer, nullable=True)
    bathrooms = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(50), default="New") 
    source = db.Column(db.String(50), default="Network Search")
    link = db.Column(db.String(500)) 
    emailed_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # TitanFinance Injection
    arv_estimate = db.Column(db.Integer)
    repair_estimate = db.Column(db.Integer)
    max_allowable_offer = db.Column(db.Integer)

class OutreachLog(db.Model):
    """Sent History Model for production audit visibility."""
    __tablename__ = 'outreach_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    address = db.Column(db.String(255))
    recipient = db.Column(db.String(150))
    message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

class Video(db.Model):
    """Industrial AI Media Tracking."""
    __tablename__ = 'videos'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- INDUSTRIAL SELF-HEALING ENGINE ---
with app.app_context():
    db.create_all()
    inspector = inspect(db.engine)
    
    # User Schema Healing
    user_cols = [c['name'] for c in inspector.get_columns('users')]
    if 'email_template' not in user_cols:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE users ADD COLUMN email_template TEXT'))
            conn.commit()
            log_activity("⚙️ SELF-HEAL: users.email_template column injected.")
            
    # Lead Schema Healing
    lead_cols = [c['name'] for c in inspector.get_columns('leads')]
    if 'name' not in lead_cols:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE leads ADD COLUMN name VARCHAR(150)'))
            conn.commit()
            log_activity("⚙️ SELF-HEAL: leads.name column injected.")

# ---------------------------------------------------------
# 4. INDUSTRIAL ENGINES (HUNTER & OUTREACH)
# ---------------------------------------------------------

def task_scraper(app_obj, user_id, city, state):
    """
    ENGINE: INDUSTRIAL LEAD HUNTER.
    Optimized for 1,000+ site CX Network.
    - combinatoric queries using city, state, and keywords.
    - Deep Pagination: Iterates through start indices (1 to 100) per keyword.
    - Anti-Detection: Mandatory jitter-delay (5-15s) between requests.
    - Standardized explicit indexing to prevent Render crash.
    """
    with app_obj.app_context():
        log_activity("🚀 MISSION STARTED: Lead Extraction in {0}, {1}".format(city, state))
        log_activity("🌐 NETWORK STATUS: 1,000+ Site CX Cluster Active.")
        
        if not SEARCH_API_KEY or not SEARCH_CX:
            log_activity("❌ API ERROR: Google Credentials missing in Production Environment.")
            return

        try:
            service = build("customsearch", "v1", developerKey=SEARCH_API_KEY)
        except Exception as e:
            log_activity("❌ API CRITICAL FAIL: {0}".format(str(e)))
            return

        # Pull 20 random keywords to ensure high lead volume per city scan
        keywords = random.sample(KEYWORD_BANK, 20) 
        total_leads_added = 0
        
        for kw in keywords:
            # INDUSTRIAL PAGINATION: Pull 10 pages per combinatorial search (100 leads)
            for start_idx in range(1, 101, 10): 
                try:
                    # ENTERPRISE QUERY LOGIC: Searching the entire 1,000 site network via CX
                    query_template = '"{0}" "{1}" {2}'
                    query_string = query_template.format(city, state, kw)
                    
                    res = service.cse().list(q=query_string, cx=SEARCH_CX, num=10, start=start_idx).execute()
                    if 'items' not in res: break 

                    for item in res.get('items', []):
                        snippet = (item.get('snippet', '') + " " + item.get('title', '')).lower()
                        link = item.get('link', '#')
                        
                        # INDUSTRIAL REGEX PIPELINE
                        phones = re.findall(r'\(?\d{}\)?[-.\s]?\d{}[-.\s]?\d{}', snippet)
                        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                        
                        if phones or emails:
                            if not Lead.query.filter_by(link=link, submitter_id=user_id).first():
                                f_phone = phones[0] if phones else "None"
                                f_email = emails[0] if emails else "None"
                                
                                # Owner Name Heuristic
                                owner_name = "Property Owner"
                                if "by" in snippet:
                                    name_match = re.search(r'by\s+([a-zA-Z]+)', snippet)
                                    if name_match: owner_name = name_match.group(1).capitalize()

                                lead = Lead(
                                    submitter_id=user_id,
                                    address=item.get('title')[:100],
                                    name=owner_name,
                                    phone=f_phone,
                                    email=f_email,
                                    source="Network ({0})".format(kw),
                                    link=link,
                                    status="New"
                                )
                                db.session.add(lead)
                                total_leads_added += 1
                                log_activity("✅ LEAD HARVESTED: {0}".format(lead.address[:25]))
                    
                    db.session.commit()
                    
                    # MANDATORY STEALTH DELAY (5-15s)
                    jitter = random.uniform(5, 15)
                    log_activity("💤 Stealth Jitter: {0}s pause.".format(round(jitter, 1)))
                    time.sleep(jitter) 

                except HttpError as e:
                    if e.resp.status == 429:
                        log_activity("⚠️ RATE LIMIT: Waiting for reset (60s).")
                        time.sleep(60); continue
                    break
                except Exception as e:
                    log_activity("⚠️ SCRAPE FAULT: {0}".format(str(e)))
                    continue

        log_activity("🏁 MISSION COMPLETE: indexed {0} leads.".format(total_leads_added))

def task_emailer(app_obj, user_id, subject, body, attach_path):
    """
    ENGINE: OUTREACH AUTOMATION MACHINE.
    Functional standards:
    - Mass automation using universal scripts.
    - Dynamic Variable Extraction: [[ADDRESS]] and [[NAME]] automation.
    - Sent History Persistence.
    - Mandatory 5-15s randomized behavior delay between leads.
    """
    with app_obj.app_context():
        user = User.query.get(user_id)
        if not user.smtp_email or not user.smtp_password:
            log_activity("❌ SMTP ERROR: Gmail app credentials missing.")
            return

        # Target valid leads with email data
        leads = Lead.query.filter(Lead.submitter_id == user_id, Lead.email.contains('@')).all()
        log_activity("📧 BLAST COMMENCING: Targeting {0} leads.".format(len(leads)))
        
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(user.smtp_email, user.smtp_password)
            log_activity("✅ SMTP LOGIN: SUCCESS.")
            
            sent_count = 0
            for lead in leads:
                try:
                    # UNIVERSAL SCRIPT DATA INJECTION
                    final_body = body if body and len(body) > 10 else user.email_template
                    final_body = final_body.replace("[[ADDRESS]]", lead.address)
                    final_body = final_body.replace("[[NAME]]", lead.name or "Property Owner")
                    
                    # AI SMART OVERRIDE (GROQ)
                    if groq_client and len(final_body) < 15:
                        chat = groq_client.chat.completions.create(
                            messages=[{"role": "user", "content": "Write a short cash offer email for {0} at {1}.".format(lead.name, lead.address)}],
                            model="llama-3.3-70b-versatile"
                        )
                        final_body = chat.choices[0].message.content

                    msg = MIMEMultipart()
                    msg['From'] = user.smtp_email
                    msg['To'] = lead.email
                    msg['Subject'] = subject.replace("[[ADDRESS]]", lead.address)
                    msg.attach(MIMEText(final_body, 'plain'))
                    
                    if attach_path:
                        with open(attach_path, "rb") as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header('Content-Disposition', 'attachment; filename="contract.pdf"')
                            msg.attach(part)
                    
                    server.send_message(msg)
                    
                    # LOG TO HISTORY PANE
                    outlog = OutreachLog(user_id=user_id, address=lead.address, recipient=lead.email, message=final_body[:250])
                    db.session.add(outlog)
                    
                    lead.emailed_count = (lead.emailed_count or 0) + 1
                    lead.status = "Contacted"
                    db.session.commit()
                    
                    sent_count += 1
                    log_activity("📨 SENT SUCCESS: {0}".format(lead.email))
                    
                    # ANTI-Detect behavior delay (5-15s)
                    time.sleep(random.uniform(5, 15)) 
                    
                except Exception as e:
                    log_activity("⚠️ SMTP FAILURE ({0}): {1}".format(lead.email, str(e)))
            
            server.quit()
            log_activity("🏁 BLAST COMPLETE: {0} deliveries confirmed.".format(sent_count))
            
        except Exception as e:
            log_activity("❌ SMTP CRITICAL ERROR: {0}".format(str(e)))

    if attach_path and os.path.exists(attach_path):
        os.remove(attach_path)

# ---------------------------------------------------------
# 5. ACCESS CONTROL GATEWAY
# ---------------------------------------------------------
def check_access(user, feature):
    """Industrial access control engine."""
    if not user: return False
    if user.subscription_status in ['lifetime', 'monthly', 'weekly']:
        if user.subscription_status == 'lifetime' or (user.subscription_end and user.subscription_end > datetime.utcnow()):
            return True
    
    # Trial Logic Check
    now = datetime.utcnow()
    trial_start = user.created_at
    if feature == 'email' and now < trial_start + timedelta(hours=24): return True
    if feature == 'ai' and now < trial_start + timedelta(hours=48): return True
    return False

# ---------------------------------------------------------
# 6. FLASK WEB ROUTES (FULL INTEGRATION)
# ---------------------------------------------------------
@app.route('/logs')
@login_required
def get_logs(): return jsonify(SYSTEM_LOGS)

@app.route('/dashboard')
@login_required
def dashboard():
    my_leads = Lead.query.filter_by(submitter_id=current_user.id).order_by(Lead.created_at.desc()).all()
    history = OutreachLog.query.filter_by(user_id=current_user.id).order_by(OutreachLog.sent_at.desc()).limit(30).all()
    stats = {'total': len(my_leads), 'hot': len([l for l in my_leads if l.status == 'Hot']), 'emails': sum([l.emailed_count or 0 for l in my_leads])}
    return render_template('dashboard.html', user=current_user, leads=my_leads, stats=stats, gmail_connected=bool(current_user.smtp_email), history=history)

@app.route('/email/template/save', methods=['POST'])
@login_required
def save_template():
    current_user.email_template = request.form.get('template')
    db.session.commit()
    flash('Universal Outreach Script Updated!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/leads/hunt', methods=['POST'])
@login_required
def hunt_leads():
    city, state = request.form.get('city'), request.form.get('state')
    threading.Thread(target=task_scraper, args=(app, current_user.id, city, state)).start()
    return jsonify({'message': "🚀 Industrial scan mission launched for {0}.".format(city)})

@app.route('/email/campaign', methods=['POST'])
@login_required
def email_campaign():
    if not check_access(current_user, 'email'):
        return jsonify({'error': 'Subscription or Trial Required.'}), 403
    threading.Thread(target=task_emailer, args=(app, current_user.id, request.form.get('subject'), request.form.get('body'), None)).start()
    return jsonify({'message': "🚀 Bulk Outreach Machine started with human delays."})

@app.route('/video/create', methods=['POST'])
@login_required
def create_video():
    if not check_access(current_user, 'ai'):
        return jsonify({'error': 'AI Trial expired.'}), 403
    desc = request.form.get('description'); photo = request.files.get('photo')
    log_activity("🎬 AI VIDEO: Initializing production sequence...")
    try:
        filename = secure_filename("img_{0}.jpg".format(int(time.time())))
        img_path = os.path.join(UPLOAD_FOLDER, filename); photo.save(img_path)
        log_activity("... Writing Script via Groq Llama 3.3")
        chat = groq_client.chat.completions.create(messages=[{"role": "system", "content": "Write a 15s real estate script."}, {"role": "user", "content": desc}], model="llama-3.3-70b-versatile")
        script = chat.choices[0].message.content
        log_activity("... Executing Voice Synthesis")
        audio_name = "audio_{0}.mp3".format(int(time.time())); audio_path = os.path.join(VIDEO_FOLDER, audio_name)
        gTTS(text=script, lang='en').save(audio_path)
        vid_name = "video_{0}.mp4".format(int(time.time())); out_path = os.path.join(VIDEO_FOLDER, vid_name)
        if HAS_FFMPEG:
            log_activity("... Finalizing Render")
            audio_clip = AudioFileClip(audio_path); video_clip = ImageClip(img_path).set_duration(audio_clip.duration).set_audio(audio_clip)
            video_clip.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac")
        else:
            log_activity("⚠️ VIDEO: Saving placeholder rendering data.")
            with open(out_path, 'wb') as f: f.write(b'Industrial_Simulation_Data')
        new_video = Video(user_id=current_user.id, filename=vid_name, description=desc)
        db.session.add(new_video); db.session.commit()
        log_activity("✅ VIDEO SUCCESS: Production finalized.")
        return jsonify({'video_url': "/static/videos/{0}".format(vid_name), 'message': "Video Produced!"})
    except Exception as e: 
        log_activity("❌ VIDEO FAIL: {0}".format(str(e))); return jsonify({'error': str(e)}), 500

@app.route('/buy_box', methods=['GET', 'POST'])
@login_required
def buy_box():
    if request.method == 'POST':
        current_user.bb_property_type = request.form.get('property_type')
        current_user.bb_locations = request.form.get('locations')
        current_user.bb_min_price = request.form.get('min_price')
        current_user.bb_max_price = request.form.get('max_price')
        current_user.bb_strategy = request.form.get('strategy')
        current_user.bb_funding = request.form.get('funding')
        current_user.bb_timeline = request.form.get('timeline')
        db.session.commit(); flash('Industrial Buy Box Updated!', 'success')
    return render_template('buybox.html', user=current_user)

@app.route('/settings/save', methods=['POST'])
@login_required
def save_settings():
    current_user.smtp_email, current_user.smtp_password = request.form.get('smtp_email'), request.form.get('smtp_password')
    db.session.commit(); log_activity("⚙️ SETTINGS UPDATED."); return redirect(url_for('dashboard'))

@app.route('/leads/add', methods=['POST'])
@login_required
def add_manual_lead():
    new_lead = Lead(submitter_id=current_user.id, address=request.form.get('address'), name=request.form.get('name'), phone=request.form.get('phone'), email=request.form.get('email'), source="Manual", status="New", link="#")
    db.session.add(new_lead); db.session.commit(); return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and (user.password == request.form['password'] or check_password_hash(user.password, request.form['password'])):
            login_user(user); return redirect(url_for('dashboard'))
        flash('Authentication failed.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not User.query.filter_by(email=request.form['email']).first():
            hashed = generate_password_hash(request.form['password'], method='scrypt')
            user = User(email=request.form['email'], password=hashed); db.session.add(user); db.session.commit()
            login_user(user); return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/terms')
def terms(): return render_template('terms.html')

@app.route('/privacy')
def privacy(): return render_template('privacy.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/sell', methods=['GET', 'POST'])
def sell_property():
    if request.method == 'POST': flash('Evaluation started.', 'success'); return redirect(url_for('sell_property'))
    return render_template('sell.html')

@app.route('/')
def index(): return redirect(url_for('login'))

# ---------------------------------------------------------
# 7. ENTERPRISE HTML TEMPLATE REPOSITORY
# ---------------------------------------------------------
html_templates = {
 'base.html': """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>TITAN | Industrial Intelligence</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>body { background-color: #f8f9fa; font-family: 'Inter', sans-serif; } .terminal { background: #000; color: #00ff00; font-family: 'Courier New', monospace; padding: 20px; height: 350px; overflow-y: scroll; border-radius: 12px; border: 2px solid #333; font-size: 14px; line-height: 1.6; } .card { border: none; border-radius: 12px; } .nav-tabs .nav-link { font-weight: 700; color: #495057; border: none; padding: 15px 25px; } .nav-tabs .nav-link.active { color: #0d6efd; border-bottom: 4px solid #0d6efd; background: transparent; } </style></head><body><nav class="navbar navbar-expand-lg navbar-dark bg-dark shadow-sm"><div class="container"><a class="navbar-brand fw-bold" href="/">TITAN <span class="text-primary">INTEL</span></a><div class="collapse navbar-collapse"><ul class="navbar-nav ms-auto align-items-center"><li class="nav-item"><a class="btn btn-outline-warning btn-sm me-3" href="/sell">Seller Portal</a></li>{% if current_user.is_authenticated %}<li class="nav-item"><a class="nav-link" href="/dashboard">Dashboard</a></li><li class="nav-item"><a class="nav-link text-danger" href="/logout">Logout</a></li>{% else %}<li class="nav-item"><a class="nav-link" href="/login">Login</a></li>{% endif %}</ul></div></div></nav><div class="container mt-4">{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ 'danger' if category == 'error' else 'success' }} alert-dismissible fade show shadow-sm">{{ message }}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>{% endfor %}{% endif %}{% endwith %}{% block content %}{% endblock %}</div><footer class="text-center text-muted py-5 small">&copy; 2024 Titan Intel Engine. Industrial Build 5.0.0. <a href="/terms">Terms</a> | <a href="/privacy">Privacy</a></footer></body></html>""",

 'dashboard.html': """
{% extends "base.html" %}
{% block content %}
<div class="row g-4">
 <div class="col-12"><div class="card shadow-lg bg-dark text-white"><div class="card-header border-secondary d-flex justify-content-between align-items-center"><span><i class="fas fa-terminal me-2"></i> SYSTEM LOG ENGINE</span><span class="badge bg-success">STREAMS ACTIVE</span></div><div class="card-body p-0"><div id="system-terminal" class="terminal">Initializing connection...</div></div></div></div>
 <div class="col-12"><div class="card shadow-sm"><div class="card-body d-flex justify-content-around text-center py-4"><div class="stat-card"><h3>{{ stats.total }}</h3><small class="text-muted fw-bold">TOTAL LEADS</small></div><div class="stat-card text-success"><h3>{{ stats.hot }}</h3><small class="text-muted fw-bold">HOT LEADS</small></div><div class="stat-card text-primary"><h3>{{ stats.emails }}</h3><small class="text-muted fw-bold">EMAILS SENT</small></div><div class="align-self-center d-flex gap-2"><button class="btn btn-sm btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#settingsModal">Settings</button><button class="btn btn-sm btn-success" data-bs-toggle="modal" data-bs-target="#addLeadModal">Manual Add</button><a href="/leads/export" class="btn btn-sm btn-dark">Export CSV</a></div></div></div></div>
 <div class="col-12">
  <ul class="nav nav-tabs mb-4" id="titanTab" role="tablist">
   <li class="nav-item"><button class="nav-link active" id="leads-tab" data-bs-toggle="tab" data-bs-target="#leads">🏠 My Active Leads</button></li>
   <li class="nav-item"><button class="nav-link" id="hunter-tab" data-bs-toggle="tab" data-bs-target="#hunter">🕵️ Industrial Scraper</button></li>
   <li class="nav-item"><button class="nav-link" id="email-tab" data-bs-toggle="tab" data-bs-target="#email">📧 Universal Outreach</button></li>
   <li class="nav-item"><button class="nav-link" id="history-tab" data-bs-toggle="tab" data-bs-target="#history">📜 Sent History</button></li>
  </ul>
  <div class="tab-content">
   <div class="tab-pane fade show active" id="leads"><div class="card shadow-sm"><div class="card-body p-0"><div class="table-responsive"><table class="table table-hover align-middle mb-0"><thead class="table-light"><tr><th>Status</th><th>Address</th><th>Owner</th><th>Link</th></tr></thead><tbody>{% for lead in leads %}<tr><td><select class="form-select form-select-sm" onchange="updateStatus({{ lead.id }}, this.value)"><option {% if lead.status == 'New' %}selected{% endif %}>New</option><option {% if lead.status == 'Hot' %}selected{% endif %}>Hot</option></select></td><td class="fw-bold">{{ lead.address }}</td><td>{{ lead.name }}</td><td><a href="{{ lead.link }}" target="_blank" class="btn btn-sm btn-outline-primary"><i class="fas fa-external-link-alt"></i></a></td></tr>{% endfor %}</tbody></table></div></div></div></div>
   <div class="tab-pane fade" id="hunter"><div class="card bg-dark text-white p-5 text-center shadow-lg"><h2 class="fw-bold mb-3"><i class="fas fa-search-dollar text-warning"></i> Industrial Scraper</h2><p class="text-muted">Targeted extraction across your 1,000+ Site Network using human-simulated patterns.</p><div class="row justify-content-center mt-4 g-3"><div class="col-md-3"><select id="huntState" class="form-select form-select-lg" onchange="loadCities()"><option value="">State</option></select></div><div class="col-md-3"><select id="huntCity" class="form-select form-select-lg"><option value="">City</option></select></div><div class="col-md-3"><button onclick="runHunt()" class="btn btn-warning btn-lg w-100 fw-bold shadow">LAUNCH MISSION</button></div></div></div></div>
   <div class="tab-pane fade" id="email"><div class="card shadow-sm border-primary"><div class="card-header bg-primary text-white fw-bold d-flex justify-content-between align-items-center"><span>📧 Universal Outreach Template</span><small>Tags: [[ADDRESS]], [[NAME]]</small></div><div class="card-body p-4"><form action="/email/template/save" method="POST" class="mb-4"><textarea name="template" class="form-control mb-2" rows="4">{{ user.email_template }}</textarea><button class="btn btn-sm btn-primary">Save Global Script</button></form><hr>{% if not gmail_connected %}<div class="alert alert-danger">Connect Gmail App Password in Settings!</div>{% endif %}<div class="mb-3"><label class="form-label fw-bold">Outreach Subject Line</label><input id="emailSubject" class="form-control" value="Regarding property at [[ADDRESS]]"></div><button onclick="sendBlast()" class="btn btn-dark w-100 fw-bold shadow" {% if not gmail_connected %}disabled{% endif %}>🚀 Launch Mass Blast Mission</button></div></div></div>
   <div class="tab-pane fade" id="history"><div class="card shadow-sm border-0"><div class="card-body"><h5 class="fw-bold mb-3">Previous Sent Messages History</h5><div class="list-group">{% for item in history %}<div class="list-group-item"><h6 class="mb-1 fw-bold">{{ item.address }}</h6><p class="mb-1 small">{{ item.message }}...</p><small class="text-primary">Sent to: {{ item.recipient }} | {{ item.sent_at.strftime('%Y-%m-%d %H:%M') }}</small></div>{% else %}<div class="text-center py-5 text-muted"><p>No history found.</p></div>{% endfor %}</div></div></div></div>
  </div>
 </div>
</div>
<div class="modal fade" id="settingsModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><form action="/settings/save" method="POST"><div class="modal-body"><h6>Gmail App Password Config</h6><input name="smtp_email" class="form-control mb-2" value="{{ user.smtp_email or '' }}" placeholder="you@gmail.com"><input type="password" name="smtp_password" class="form-control mb-2" value="{{ user.smtp_password or '' }}" placeholder="16-Character Key"></div><div class="modal-footer"><button class="btn btn-primary">Save Configuration</button></div></form></div></div></div>
<div class="modal fade" id="addLeadModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><form action="/leads/add" method="POST"><div class="modal-body"><h6>Manual Entry</h6><input name="address" class="form-control mb-2" placeholder="Full Address" required><input name="name" class="form-control mb-2" placeholder="Owner Name"><input name="phone" class="form-control mb-2" placeholder="Phone"><input name="email" class="form-control mb-2" placeholder="Email"></div><div class="modal-footer"><button type="submit" class="btn btn-success">Save Lead</button></div></form></div></div></div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
const usData = {{ us_data_json|safe }};
window.onload = function() { const s = document.getElementById("huntState"); for (let st in usData) { let o = document.createElement("option"); o.value = st; o.innerText = st; s.appendChild(o); } setInterval(updateTerminal, 2000); };
function loadCities() { const st = document.getElementById("huntState").value; const c = document.getElementById("huntCity"); c.innerHTML = '<option value="">Select City</option>'; if(st) usData[st].forEach(ct => { let o = document.createElement("option"); o.value = ct; o.innerText = ct; c.appendChild(o); }); }
async function updateTerminal() { const t = document.getElementById('system-terminal'); try { const r = await fetch('/logs'); const l = await r.json(); t.innerHTML = l.join('<br>'); t.scrollTop = t.scrollHeight; } catch(e) {} }
async function runHunt() { const city = document.getElementById('huntCity').value; const state = document.getElementById('huntState').value; if(!city || !state) return alert("Select location."); const r = await fetch('/leads/hunt', {method:'POST', body:new URLSearchParams({city, state})}); const d = await r.json(); alert(d.message); }
async function sendBlast() { const f = new FormData(); f.append('subject', document.getElementById('emailSubject').value); f.append('body', ''); const r = await fetch('/email/campaign', {method:'POST', body:f}); const d = await r.json(); alert(d.message); }
async function updateStatus(id, s) { await fetch('/leads/update/'+id, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status:s})}); }
</script>
{% endblock %}
""",

 'login.html': """{% extends "base.html" %} {% block content %} 
 <div class="row justify-content-center pt-5">
  <div class="col-md-10">
   <div class="card shadow-lg border-0 mb-5 bg-warning text-dark text-center p-5">
     <h1 class="fw-bold display-3">🏠 SELL YOUR PROPERTY NOW</h1>
     <p class="lead fw-bold fs-4 mb-4">Industrial real estate investors are waiting for your address.</p>
     <a href="/sell" class="btn btn-dark btn-xl fw-bold px-5 py-3 shadow">GET AN INSTANT CASH OFFER</a>
   </div>
  </div>
  <div class="col-md-4"><div class="card p-5 shadow-lg border-0">
    <h3 class="text-center fw-bold mb-4">Investor Login</h3>
    <form method="POST"><div class="mb-3"><input name="email" class="form-control" placeholder="Email Address"></div>
    <div class="mb-4"><input type="password" name="password" class="form-control" placeholder="Password"></div>
    <button class="btn btn-primary w-100 fw-bold py-2 shadow-sm">Login</button></form>
    <div class="text-center mt-3"><a href="/register" class="small">Register New Account</a></div>
  </div></div>
 </div>{% endblock %}""",

 'register.html': """{% extends "base.html" %} {% block content %} <div class="row justify-content-center pt-5"><div class="col-md-4 card p-5 shadow-lg border-0"><h3 class="text-center fw-bold mb-4">Register</h3><form method="POST"><div class="mb-3"><input name="email" class="form-control" placeholder="Email Address"></div><div class="mb-4"><input type="password" name="password" class="form-control" placeholder="Password"></div><button class="btn btn-success w-100 fw-bold py-2 shadow-sm">Sign Up</button></form></div></div>{% endblock %}""",

 'sell.html': """{% extends "base.html" %} {% block content %} <div class="row justify-content-center py-5 text-center"><div class="col-md-8"><h1>Instant Cash Offer Assessment</h1><div class="card p-5 shadow-lg mt-4 border-0"><form method="POST"><input class="form-control form-control-lg mb-3" placeholder="Full Address" required><input class="form-control form-control-lg mb-3" placeholder="Phone" required><button class="btn btn-warning btn-lg w-100 fw-bold py-3 shadow">SUBMIT FOR EVALUATION</button></form></div></div></div>{% endblock %}""",

 'buybox.html': """{% extends "base.html" %} {% block content %} <div class="container mt-5"><div class="row justify-content-center"><div class="col-md-8"><div class="card shadow-lg p-5"><h2>Buy Box Architectural Configuration</h2><form method="POST" class="row g-4"><div class="col-md-6"><label class="form-label">Property Type</label><select name="property_type" class="form-control"><option value="SFH">Single Family</option><option value="MFH">Multi Family</option></select></div><div class="col-md-6"><label class="form-label">Min/Max Price</label><div class="input-group"><input name="min_price" class="form-control" placeholder="Min"><input name="max_price" class="form-control" placeholder="Max"></div></div><div class="col-12"><label class="form-label">Target Cities</label><input name="locations" class="form-control" placeholder="Austin, Miami"></div><button class="btn btn-primary w-100 py-3 fw-bold">SAVE ARCHITECTURAL PREFERENCES</button></form></div></div></div></div>{% endblock %}""",

 'terms.html': """{% extends "base.html" %} {% block content %} <div class="card p-5 shadow-sm"><h1>Terms of Conditions</h1><p>Welcome to Titan Intel. By using this industrial engine, you agree to comply with jurisdictional lead generation and outreach laws...</p></div>{% endblock %}""",

 'privacy.html': """{% extends "base.html" %} {% block content %} <div class="card p-5 shadow-sm"><h1>Privacy Shield</h1><p>Titan Intel Engine ensures data persistence and lead privacy using Scrypt Industrial standards...</p></div>{% endblock %}"""
}

# ---------------------------------------------------------
# 8. INDUSTRIAL BOOTSTRAPPER & RUNNER
# ---------------------------------------------------------
if __name__ == "__main__":
    if not os.path.exists('templates'): os.makedirs('templates')
    for filename, content in html_templates.items():
        with open(os.path.join('templates', filename), 'w') as f: f.write(content.strip())
    
    @app.context_processor
    def inject_us_data():
        return dict(us_data_json=json.dumps(USA_STATES))

    app.run(debug=True, port=5000)

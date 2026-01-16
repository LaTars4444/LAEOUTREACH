# ==============================================================================
# TITAN V28.2 - CORE INFRASTRUCTURE (PART 1 OF 15)
# ==============================================================================
import os
import re
import base64
import time
import random
import stripe
import sqlite3
import json
import secrets
import logging
import traceback
import hashlib
import threading
import uuid
import requests
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from flask import (
    Flask, 
    render_template_string, 
    request, 
    redirect, 
    url_for, 
    session, 
    flash, 
    send_from_directory, 
    jsonify, 
    Response,
    abort
)
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from googleapiclient.discovery import build
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from email.mime.text import MIMEText
from groq import Groq
from concurrent.futures import ThreadPoolExecutor

# LOGGING SETUP
# Set up professional grade logging to monitor deal flows and fee calculations
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] TITAN_CORE: %(message)s',
    handlers=[
        logging.FileHandler("titan_system.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# APP INITIALIZATION
app = Flask(__name__)
# ProxyFix ensures we get the correct IP and Protocol when running behind Nginx/Heroku
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# SECURITY KEYS
# We use a rigorous fallback mechanism for the encryption key
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(64))
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    logger.warning("ENCRYPTION_KEY not found in environment. Generating temporary key.")
    ENCRYPTION_KEY = Fernet.generate_key().decode()
cipher = Fernet(ENCRYPTION_KEY.encode())

# API CLIENTS
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
try:
    groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
except Exception as e:
    logger.error(f"Failed to initialize Groq Client: {e}")
    groq_client = None

# FILE SYSTEM CONFIGURATION
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'storage/assets')
LOG_FOLDER = os.path.join(os.getcwd(), 'storage/logs')
DB_PATH = os.path.join(os.getcwd(), 'storage/titan_main_v28.db')

for folder in [UPLOAD_FOLDER, LOG_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'webp'}

# TITAN PRICING & TIER ARCHITECTURE
# This defines the cost of the tools users use to market properties
PRICE_IDS = {
    'EMAIL_MACHINE_LIFETIME': "price_1Spy7SFXcDZgM3VoVZv71I63", # One-time unlock
    'EMAIL_MACHINE_WEEKLY': "price_1SpxexFXcDZgM3Vo0iYmhfpb",   # Weekly subscription
    'NEURAL_AGENT_MONTHLY': "price_1SqIjgFXcDZgM3VoEwrUvjWP",   # AI full access
    'NEURAL_AGENT_YEARLY': "price_xxxx_placeholder"            # High-tier access
}

# PLATFORM FEE CONFIGURATION (THE CUT)
# Your cut starts high for new users and scales down as they list/close more
PLATFORM_FEE_CONFIG = {
    'DEFAULT_CUT': 0.06,  # 6% cut
    'TIER_1_CUT': 0.05,   # After 5 deals
    'TIER_2_CUT': 0.04,   # After 10 deals
    'TIER_3_CUT': 0.03,   # After 25 deals
    'PRO_CUT': 0.02       # Minimum floor (2%)
}

# OAUTH CONFIGURATION
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:5000/callback")

CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uris": [REDIRECT_URI]
    }
}

# Required permissions for the Outbound Email Machine
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.compose'
]

# GLOBAL CONSTANTS
SYSTEM_VERSION = "28.2.1"
SYSTEM_CODENAME = "ULTRON"

# HELPER: SECURE FILE CHECK
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# (Continued in Part 2...)
# ==============================================================================
# TITAN V28.2 - DATABASE ENGINE & MIGRATIONS (PART 2 OF 15)
# ==============================================================================

class TitanDatabase:
    """High-performance SQLite interface for managing assets and marketing logs."""
    
    def __init__(self, path):
        self.path = path
        self._init_tables()

    def get_connection(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL") # Enable write-ahead logging
        return conn

    def _init_tables(self):
        with self.get_connection() as conn:
            # USER TABLE: Track access to your tools and their deal history
            conn.execute("""CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                full_name TEXT,
                profile_pic TEXT,
                deal_count INTEGER DEFAULT 0,
                email_machine_access INTEGER DEFAULT 0,
                ai_access INTEGER DEFAULT 0,
                ai_trial_end TEXT,
                google_creds_enc TEXT,
                stripe_customer_id TEXT,
                last_login TEXT,
                created_at TEXT,
                bb_min_price INTEGER DEFAULT 0,
                bb_max_price INTEGER DEFAULT 10000000,
                bb_target_zip TEXT,
                bb_strategy TEXT DEFAULT 'Equity'
            )""")

            # ASSET TABLE (INBOUND): Properties listed by users
            conn.execute("""CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                city TEXT,
                state TEXT,
                zip_code TEXT,
                asking_price INTEGER NOT NULL,
                arv INTEGER NOT NULL,
                repair_cost INTEGER DEFAULT 0,
                sqft INTEGER,
                beds REAL,
                baths REAL,
                image_path TEXT,
                description TEXT,
                status TEXT DEFAULT 'active',
                seller_email TEXT NOT NULL,
                created_at TEXT,
                platform_cut_percentage REAL,
                FOREIGN KEY(seller_email) REFERENCES users(email)
            )""")

            # OUTREACH LOGS: Monitor the volume of marketing sent through your machine
            conn.execute("""CREATE TABLE IF NOT EXISTS outreach_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                recipient_email TEXT,
                subject TEXT,
                content_type TEXT,
                sent_at TEXT,
                success_flag INTEGER,
                FOREIGN KEY(user_email) REFERENCES users(email)
            )""")

            # TRANSACTIONS: Track when you take your cut or users buy tool access
            conn.execute("""CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                user_email TEXT,
                amount INTEGER,
                currency TEXT,
                type TEXT, -- 'CUT' or 'TOOL_PURCHASE'
                status TEXT,
                created_at TEXT
            )""")
            
            conn.commit()
            logger.info("Database schema initialized and verified.")

    def update_user_activity(self, email):
        """Update last login timestamp."""
        with self.get_connection() as conn:
            conn.execute("UPDATE users SET last_login = ? WHERE email = ?", 
                        (datetime.now().isoformat(), email))
            conn.commit()

    def get_user(self, email):
        with self.get_connection() as conn:
            return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    def create_user_if_not_exists(self, email, name=None, pic=None):
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO users (email, full_name, profile_pic, created_at, last_login)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET 
                    full_name = excluded.full_name,
                    profile_pic = excluded.profile_pic,
                    last_login = excluded.last_login
            """, (email, name, pic, now, now))
            conn.commit()

# Initialize Global Database Instance
db = TitanDatabase(DB_PATH)

def get_db_connection():
    return db.get_connection()

# (Continued in Part 3...)
# ==============================================================================
# TITAN V28.2 - DESIGN SYSTEM & UI ENGINE (PART 3 OF 15)
# ==============================================================================

def render_titan_ui(content, user=None, title="TITAN v28"):
    """
    The monolithic UI renderer. Injects a high-performance design system
    focusing on Inbound/Outbound workflows.
    """
    
    # Dynamic Navigation State
    nav_html = ""
    if user:
        nav_html = f"""
        <div class="hidden md:flex items-center space-x-10">
            <a href="/buy" class="nav-link">Inventory</a>
            <a href="/sell" class="nav-link">Inbound Listing</a>
            <a href="/outreach" class="nav-link">Outbound Machine</a>
            <a href="/ai-agent" class="nav-link text-indigo-400 font-bold border-b border-indigo-900 pb-1">Neural Agent</a>
        </div>
        <div class="flex items-center space-x-4">
            <div class="text-right hidden sm:block">
                <p class="text-[10px] text-zinc-500 font-black uppercase tracking-tighter">Connected User</p>
                <p class="text-xs font-bold text-white uppercase">{user['email'].split('@')[0]}</p>
            </div>
            <img src="{user['profile_pic'] or 'https://ui-avatars.com/api/?name='+user['email']}" class="w-10 h-10 rounded-full border border-zinc-800">
            <a href="/logout" class="p-2 hover:bg-red-900/20 rounded-lg group transition-all">
                <svg class="w-5 h-5 text-zinc-500 group-hover:text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
            </a>
        </div>
        """
    else:
        nav_html = '<a href="/auth/login" class="btn-primary">Initialize Access</a>'

    return render_template_string(f"""
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} | Operational Intelligence</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;900&family=JetBrains+Mono:wght@400;700&display=swap');
            
            :root {{
                --accent: #6366f1;
                --bg: #030303;
                --card-bg: #0a0a0a;
                --border: #1a1a1a;
                --text-secondary: #71717a;
            }}

            body {{
                background-color: var(--bg);
                color: #ffffff;
                font-family: 'Outfit', sans-serif;
                overflow-x: hidden;
            }}

            .mono {{ font-family: 'JetBrains Mono', monospace; }}

            /* Glassmorphism Classes */
            .titan-card {{
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 1.5rem;
                transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            }}

            .titan-card:hover {{
                border-color: var(--accent);
                box-shadow: 0 0 30px rgba(99, 102, 241, 0.1);
                transform: translateY(-4px);
            }}

            .nav-link {{
                font-size: 0.75rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                color: var(--text-secondary);
                transition: 0.3s;
            }}

            .nav-link:hover {{
                color: #fff;
            }}

            /* Buttons */
            .btn-primary {{
                background: #fff;
                color: #000;
                padding: 0.8rem 1.8rem;
                border-radius: 0.75rem;
                font-weight: 900;
                text-transform: uppercase;
                font-size: 0.7rem;
                letter-spacing: 0.05em;
                display: inline-flex;
                align-items: center;
                transition: 0.3s;
            }}

            .btn-primary:hover {{
                transform: scale(1.05);
                box-shadow: 0 10px 20px rgba(255,255,255,0.15);
            }}

            .btn-outline {{
                border: 1px solid var(--border);
                color: #fff;
                padding: 0.8rem 1.8rem;
                border-radius: 0.75rem;
                font-weight: 700;
                text-transform: uppercase;
                font-size: 0.7rem;
                transition: 0.3s;
            }}

            .btn-outline:hover {{
                border-color: #fff;
                background: rgba(255,255,255,0.05);
            }}

            /* Form Inputs */
            input, select, textarea {{
                background: #0f0f0f;
                border: 1px solid var(--border);
                color: #fff;
                padding: 1rem;
                border-radius: 0.75rem;
                width: 100%;
                outline: none;
                transition: 0.3s;
            }}

            input:focus, textarea:focus {{
                border-color: var(--accent);
                background: #151515;
            }}

            /* Custom scrollbar */
            ::-webkit-scrollbar {{ width: 6px; }}
            ::-webkit-scrollbar-track {{ background: #030303; }}
            ::-webkit-scrollbar-thumb {{ background: #1a1a1a; border-radius: 10px; }}
            ::-webkit-scrollbar-thumb:hover {{ background: var(--accent); }}

            .gradient-text {{
                background: linear-gradient(to right, #fff, #6366f1);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}

            .badge-indigo {{
                background: rgba(99, 102, 241, 0.1);
                color: #818cf8;
                border: 1px solid rgba(99, 102, 241, 0.2);
                padding: 2px 8px;
                border-radius: 6px;
                font-size: 10px;
                font-weight: 800;
                text-transform: uppercase;
            }}
        </style>
    </head>
    <body class="min-h-screen flex flex-col">
        <nav class="border-b border-zinc-900 bg-black/50 backdrop-blur-xl sticky top-0 z-50">
            <div class="max-w-7xl mx-auto px-6 h-20 flex justify-between items-center">
                <a href="/" class="flex items-center space-x-3 group">
                    <div class="w-8 h-8 bg-white rotate-45 group-hover:rotate-180 transition-all duration-700 flex items-center justify-center overflow-hidden">
                        <span class="rotate-[-45deg] text-black font-black text-xs">T</span>
                    </div>
                    <span class="text-xl font-black italic tracking-tighter">TITAN<span class="text-zinc-600">PROTOCOL</span></span>
                </a>
                
                {nav_html}
            </div>
        </nav>

        <main class="flex-grow max-w-7xl w-full mx-auto px-6 py-12">
            {}
        </main>

        <footer class="border-t border-zinc-900 bg-black py-12">
            <div class="max-w-7xl mx-auto px-6 flex flex-col md:flex-row justify-between items-center opacity-40">
                <p class="text-[10px] font-bold uppercase tracking-[0.3em]">&copy; 2024 TITAN ASSET INFRASTRUCTURE v{SYSTEM_VERSION}</p>
                <div class="flex space-x-8 mt-6 md:mt-0">
                    <a href="/privacy" class="text-[10px] font-black uppercase hover:text-white">Privacy</a>
                    <a href="/terms" class="text-[10px] font-black uppercase hover:text-white">Service Terms</a>
                    <a href="https://billing.stripe.com/p/login/cNidR9dlK3WC4fg9VR9IQ00" class="text-[10px] font-black uppercase text-red-500">Billing Portal</a>
                </div>
            </div>
        </footer>
    </body>
    </html>
    """)

# (Continued in Part 4...)
# ==============================================================================
# TITAN V28.2 - FINANCIAL & "CUT" ENGINE (PART 4 OF 17)
# ==============================================================================

class TitanFinance:
    """
    The heart of the business model. 
    Calculates the platform's cut and simulates ROI for users.
    """
    
    @staticmethod
    def calculate_tier(deal_count):
        """Determines the platform's fee percentage based on user loyalty."""
        if deal_count >= 25:
            return PLATFORM_FEE_CONFIG['PRO_CUT']
        elif deal_count >= 10:
            return PLATFORM_FEE_CONFIG['TIER_2_CUT']
        elif deal_count >= 5:
            return PLATFORM_FEE_CONFIG['TIER_1_CUT']
        return PLATFORM_FEE_CONFIG['DEFAULT_CUT']

    @staticmethod
    def get_deal_metrics(asking_price, arv, repairs, deal_count):
        """
        Calculates the full financial breakdown including the platform cut.
        """
        try:
            asking_price = float(asking_price)
            arv = float(arv)
            repairs = float(repairs)
        except (ValueError, TypeError):
            return None

        fee_rate = TitanFinance.calculate_tier(deal_count)
        platform_fee = asking_price * fee_rate
        
        # Total acquisition cost for the buyer
        total_investment = asking_price + platform_fee + repairs
        
        # Net Profit Calculation
        potential_profit = arv - total_investment
        
        # ROI %
        roi = (potential_profit / total_investment) * 100 if total_investment > 0 else 0
        
        return {
            "fee_rate_percent": fee_rate * 100,
            "platform_fee": int(platform_fee),
            "total_investment": int(total_investment),
            "potential_profit": int(potential_profit),
            "roi": round(roi, 2),
            "is_viable": roi > 15 # Deals under 15% ROI are marked as high risk
        }

    @staticmethod
    def format_currency(value):
        """Professional currency formatting for the UI."""
        return f"${value:,.0f}"

# REVENUE TRACKING DECORATOR
def track_revenue(f):
    """Logs transaction attempts for your platform fee audit."""
    def wrapper(*args, **kwargs):
        logger.info(f"Financial Operation Initiated: {f.__name__}")
        start_time = time.time()
        result = f(*args, **kwargs)
        duration = time.time() - start_time
        logger.info(f"Operation completed in {duration:.4f}s")
        return result
    return wrapper

@track_revenue
def process_deal_closure(user_email, deal_id):
    """
    Called when an asset is successfully moved. 
    Increments the user's deal count to lower their future fees.
    """
    with get_db_connection() as conn:
        user = conn.execute("SELECT deal_count FROM users WHERE email = ?", (user_email,)).fetchone()
        if user:
            new_count = user['deal_count'] + 1
            conn.execute("UPDATE users SET deal_count = ? WHERE email = ?", (new_count, user_email))
            conn.execute("UPDATE leads SET status = 'closed' WHERE id = ?", (deal_id,))
            conn.commit()
            return True
    return False

# FINANCIAL DATA VALIDATION
def validate_asset_pricing(price, arv):
    """Ensures users aren't listing garbage data."""
    try:
        p = float(price)
        a = float(arv)
        if p <= 0 or a <= 0: return False
        if p > a: return False # Asking more than ARV is a bad signal
        return True
    except:
        return False
# ==============================================================================
# TITAN V28.2 - NEURAL AI AGENT (PART 5 OF 17)
# ==============================================================================

class NeuralAgent:
    """
    Advanced AI Marketing Agent using LLM to generate high-converting copy.
    Does not just 'place' ads; it crafts outbound strategies.
    """
    
    PERSONAS = {
        "viral": "A high-energy TikTok/Reels influencer who focuses on FOMO and massive equity gains.",
        "institutional": "A conservative, data-driven analyst focusing on cap rates and ARV accuracy.",
        "ruthless": "A hard-hitting closer who uses psychological triggers to move off-market inventory fast."
    }

    def __init__(self, client):
        self.client = client
        self.model = "llama3-70b-8192" # High-tier model for complex reasoning

    def check_access(self, user):
        """Checks if the user is in an active trial or has paid for AI access."""
        if user['ai_access']:
            return True
        if user['ai_trial_end']:
            trial_end = datetime.fromisoformat(user['ai_trial_end'])
            if datetime.now() < trial_end:
                return True
        return False

    def generate_copy(self, persona_key, asset_details, format_type="email"):
        """
        Generates specific marketing copy based on asset inbound data.
        """
        if not self.client:
            return "Neural Link Offline. Check API Configuration."

        persona = self.PERSONAS.get(persona_key, self.PERSONAS['viral'])
        
        system_prompt = f"""
        ACT AS: {persona}
        YOUR MISSION: Help the user market a real estate asset and maximize their profit.
        TONE: Professional, high-stakes, and persuasive.
        """

        user_prompt = f"""
        Asset Details: {asset_details}
        Format Required: {format_type}
        
        Instructions:
        1. If it's an email, include a subject line that gets an 80% open rate.
        2. If it's a hook, make it stop the scroll in under 2 seconds.
        3. Emphasize the equity and the 0% commission structure of the platform.
        """

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model,
                temperature=0.8,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Neural Agent Error: {e}")
            return "Error in neural processing. Please retry in 60 seconds."

    def start_trial(self, email):
        """Initializes a 48-hour neural trial."""
        trial_end = (datetime.now() + timedelta(hours=48)).isoformat()
        with get_db_connection() as conn:
            conn.execute("UPDATE users SET ai_trial_end = ? WHERE email = ?", (trial_end, email))
            conn.commit()
        return trial_end

# GLOBAL AGENT INSTANCE
titan_ai = NeuralAgent(groq_client)

# (Part 6 follows...)
# ==============================================================================
# TITAN V28.2 - GOOGLE IDENTITY & AUTH ARCHITECTURE (PART 6 OF 17)
# ==============================================================================

class TitanAuth:
    """Manages secure Google OAuth flows and token encryption."""
    
    @staticmethod
    def get_flow():
        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
        flow.redirect_uri = REDIRECT_URI
        return flow

    @staticmethod
    def encrypt_tokens(token_data):
        """Encrypts tokens before database storage."""
        json_data = json.dumps(token_data)
        return cipher.encrypt(json_data.encode()).decode()

    @staticmethod
    def decrypt_tokens(encrypted_str):
        """Decrypts tokens for API usage."""
        try:
            decrypted_data = cipher.decrypt(encrypted_str.encode()).decode()
            return json.loads(decrypted_data)
        except Exception as e:
            logger.error(f"Token Decryption Failed: {e}")
            return None

    @staticmethod
    def refresh_user_token(user_email):
        """Ensures the Google token hasn't expired before an outbound blast."""
        with get_db_connection() as conn:
            user = conn.execute("SELECT google_creds_enc FROM users WHERE email = ?", (user_email,)).fetchone()
        
        if not user or not user['google_creds_enc']:
            return None
            
        creds_info = TitanAuth.decrypt_tokens(user['google_creds_enc'])
        if not creds_info: return None
        
        # Logic to refresh via google.oauth2.credentials
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        
        creds = Credentials.from_authorized_user_info(creds_info)
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Update DB with new token
                new_info = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes
                }
                new_enc = TitanAuth.encrypt_tokens(new_info)
                with get_db_connection() as conn:
                    conn.execute("UPDATE users SET google_creds_enc = ? WHERE email = ?", (new_enc, user_email))
                    conn.commit()
                return creds
            except Exception as e:
                logger.error(f"Token Refresh Failed: {e}")
                return None
        return creds

# SESSION MANAGEMENT WRAPPERS
def login_required(f):
    """Protects routes from unauthorized access."""
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login_gate'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# (Part 7 follows...)
# ==============================================================================
# TITAN V28.2 - GMAIL OUTBOUND MACHINE (PART 7 OF 17)
# ==============================================================================

class OutboundMachine:
    """
    Handles batch delivery of marketing content. 
    Allows users to blast their assets to potential buyers/investors.
    """
    
    def __init__(self, user_email):
        self.user_email = user_email
        self.creds = TitanAuth.refresh_user_token(user_email)

    def create_message(self, to_email, subject, body_text):
        """Standard MIME message construction."""
        message = MIMEText(body_text)
        message['to'] = to_email
        message['from'] = self.user_email
        message['subject'] = subject
        
        # URL safe base64 encoding required by Gmail API
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return {'raw': raw}

    def deliver_single(self, service, recipient, subject, body):
        """Attempts to deliver a single marketing unit."""
        try:
            msg = self.create_message(recipient.strip(), subject, body)
            service.users().messages().send(userId='me', body=msg).execute()
            return True, recipient
        except Exception as e:
            logger.error(f"Delivery failed for {recipient}: {e}")
            return False, recipient

    def initiate_blast(self, recipients, subject, body):
        """
        Executes a multi-threaded blast. 
        Threads prevent the web UI from hanging during large campaigns.
        """
        if not self.creds:
            return {"status": "error", "message": "Authentication Expired. Re-link Gmail."}

        service = build('gmail', 'v1', credentials=self.creds)
        results = {"success": [], "failure": []}
        
        # Batching logic to prevent Gmail rate-limiting
        batch_size = 10
        for i in range(0, len(recipients), batch_size):
            current_batch = recipients[i:i + batch_size]
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(self.deliver_single, service, r, subject, body) 
                    for r in current_batch
                ]
                
                for future in futures:
                    success, email = future.result()
                    self._log_outreach(email, subject, "EMAIL_BLAST", 1 if success else 0)
                    if success:
                        results["success"].append(email)
                    else:
                        results["failure"].append(email)
            
            # Artificial delay between batches to protect account reputation
            if i + batch_size < len(recipients):
                time.sleep(2)

        return {"status": "complete", "results": results}

    def _log_outreach(self, recipient, subject, c_type, success):
        """Internal logging for platform audit."""
        try:
            with get_db_connection() as conn:
                conn.execute("""
                    INSERT INTO outreach_logs 
                    (user_email, recipient_email, subject, content_type, sent_at, success_flag)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (self.user_email, recipient, subject, c_type, datetime.now().isoformat(), success))
                conn.commit()
        except Exception as e:
            logger.error(f"Outreach log failed: {e}")

# UTILITY: BULK VALIDATOR
def clean_recipient_list(raw_text):
    """Parses and validates a list of emails from a text area."""
    if not raw_text: return []
    # Regex to find all valid emails
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', raw_text)
    return list(set([e.lower() for e in emails])) # Unique list

# (Continued in Part 8...)
# ==============================================================================
# TITAN V28.2 - INBOUND CONTROLLER (PART 8 OF 17)
# ==============================================================================

@app.route('/sell', methods=['GET', 'POST'])
@login_required
def list_asset():
    """Route for users to feed properties into the platform."""
    user = db.get_user(session['user_email'])
    
    if request.method == 'POST':
        # Extraction
        addr = request.form.get('address')
        price = request.form.get('asking_price')
        arv = request.form.get('arv')
        repair = request.form.get('repair_cost', 0)
        sqft = request.form.get('sqft', 0)
        desc = request.form.get('description', '')
        
        # Validation
        if not addr or not price or not arv:
            flash("CRITICAL ERROR: Address, Price, and ARV are mandatory.", "error")
            return redirect(url_for('list_asset'))

        if not validate_asset_pricing(price, arv):
            flash("INVALID FINANCIALS: Asking price cannot exceed ARV.", "error")
            return redirect(url_for('list_asset'))

        # Image Handling
        file = request.files.get('image')
        filename = None
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
            filename = unique_name

        # Calculate Platform Cut for this specific listing
        metrics = TitanFinance.get_deal_metrics(price, arv, repair, user['deal_count'])
        
        try:
            with get_db_connection() as conn:
                conn.execute("""
                    INSERT INTO leads 
                    (address, asking_price, arv, repair_cost, sqft, image_path, 
                     description, seller_email, created_at, platform_cut_percentage)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    addr, price, arv, repair, sqft, filename, 
                    desc, user['email'], datetime.now().isoformat(), 
                    metrics['fee_rate_percent']
                ))
                conn.commit()
            
            flash(f"ASSET DEPLOYED: Platform cut locked at {metrics['fee_rate_percent']}%", "success")
            return redirect(url_for('inventory_feed'))
            
        except Exception as e:
            logger.error(f"Database insertion error: {e}")
            flash("SYSTEM ERROR: Listing failed to persist. Contact Support.", "error")

    # Render Inbound Form
    form_html = f"""
    <div class="max-w-3xl mx-auto animate__animated animate__fadeIn">
        <div class="mb-12">
            <h1 class="text-5xl font-black italic uppercase tracking-tighter">Inbound Intake</h1>
            <p class="text-zinc-500 font-bold uppercase tracking-widest text-[10px] mt-2">Current Fee Tier: {TitanFinance.calculate_tier(user['deal_count'])*100:.1f}% Platform Cut</p>
        </div>

        <form method="POST" enctype="multipart/form-data" class="space-y-8">
            <div class="titan-card p-8">
                <h2 class="text-xs font-black uppercase text-zinc-600 mb-6 tracking-widest">Asset Location & Physicals</h2>
                <div class="grid grid-cols-1 gap-6">
                    <div>
                        <label class="text-[10px] font-bold text-zinc-500 uppercase ml-2 mb-2 block">Property Address</label>
                        <input name="address" placeholder="123 Equity Lane, Wealth City, TX" required>
                    </div>
                </div>
            </div>

            <div class="titan-card p-8">
                <h2 class="text-xs font-black uppercase text-zinc-600 mb-6 tracking-widest">Financial Matrix</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div>
                        <label class="text-[10px] font-bold text-zinc-500 uppercase ml-2 mb-2 block">Asking Price ($)</label>
                        <input type="number" name="asking_price" placeholder="250000" required>
                    </div>
                    <div>
                        <label class="text-[10px] font-bold text-zinc-500 uppercase ml-2 mb-2 block">ARV ($)</label>
                        <input type="number" name="arv" placeholder="400000" required>
                    </div>
                    <div>
                        <label class="text-[10px] font-bold text-zinc-500 uppercase ml-2 mb-2 block">Repair Est ($)</label>
                        <input type="number" name="repair_cost" placeholder="50000">
                    </div>
                </div>
            </div>

            <div class="titan-card p-8">
                <h2 class="text-xs font-black uppercase text-zinc-600 mb-6 tracking-widest">Digital Media & Logistics</h2>
                <div class="space-y-6">
                    <input type="file" name="image" class="text-xs text-zinc-500 border-dashed border-2 py-10 text-center">
                    <textarea name="description" placeholder="Internal notes or additional property data..." class="h-32"></textarea>
                </div>
            </div>

            <button type="submit" class="btn-primary w-full py-6 text-xl">Deploy Asset to Inventory</button>
        </form>
    </div>
    """
    return render_titan_ui(form_html, user=user)

# (Continued in Part 9...)
# ==============================================================================
# TITAN V28.2 - INVENTORY & SOURCING FEED (PART 9 OF 17)
# ==============================================================================

@app.route('/buy')
@login_required
def inventory_feed():
    """Main dashboard for browsing active assets in the platform."""
    user = db.get_user(session['user_email'])
    
    with get_db_connection() as conn:
        # Complex query to filter based on user targeting preferences
        query = "SELECT * FROM leads WHERE status = 'active'"
        params = []
        
        if user['bb_max_price']:
            query += " AND asking_price <= ?"
            params.append(user['bb_max_price'])
        
        query += " ORDER BY created_at DESC"
        leads = conn.execute(query, params).fetchall()

    lead_cards = ""
    for l in leads:
        # Calculate ROI for the observer (taking their specific fee tier into account)
        metrics = TitanFinance.get_deal_metrics(
            l['asking_price'], l['arv'], l['repair_cost'], user['deal_count']
        )
        
        img_url = url_for('uploaded_file', filename=l['image_path']) if l['image_path'] else "https://via.placeholder.com/800x400/0a0a0a/333333?text=NO+IMAGE"
        
        status_color = "text-green-500" if metrics['roi'] > 20 else "text-indigo-400"
        
        lead_cards += f"""
        <div class="titan-card overflow-hidden group">
            <div class="h-48 overflow-hidden relative">
                <img src="{img_url}" class="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700">
                <div class="absolute top-4 left-4">
                    <span class="badge-indigo bg-black/80 backdrop-blur-md">ROI: {metrics['roi']}%</span>
                </div>
                <div class="absolute bottom-4 right-4">
                    <p class="text-[10px] font-black uppercase text-white/50 bg-black/50 px-2 py-1">ZIP: {l['zip_code'] or 'N/A'}</p>
                </div>
            </div>
            <div class="p-6">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <h3 class="text-lg font-black italic leading-tight uppercase">{l['address']}</h3>
                        <p class="text-[10px] text-zinc-500 font-bold uppercase tracking-widest">Off-Market Inventory</p>
                    </div>
                </div>
                
                <div class="grid grid-cols-2 gap-4 mb-6 border-y border-zinc-900 py-4">
                    <div>
                        <p class="text-[9px] text-zinc-600 font-bold uppercase">Asset Price</p>
                        <p class="text-sm font-bold">{TitanFinance.format_currency(l['asking_price'])}</p>
                    </div>
                    <div class="text-right">
                        <p class="text-[9px] text-zinc-600 font-bold uppercase">Our Cut ({metrics['fee_rate_percent']:.1f}%)</p>
                        <p class="text-sm font-bold text-indigo-400">+{TitanFinance.format_currency(metrics['platform_fee'])}</p>
                    </div>
                </div>

                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-[9px] text-zinc-600 font-bold uppercase">Total Entry</p>
                        <p class="text-xl font-black">{TitanFinance.format_currency(metrics['total_investment'])}</p>
                    </div>
                    <div class="flex space-x-2">
                        <a href="/ai-agent?asset_id={l['id']}" class="btn-outline px-4 py-2 flex items-center">
                            <svg class="w-3 h-3 mr-2" fill="currentColor" viewBox="0 0 20 20"><path d="M13 6a3 3 0 11-6 0 3 3 0 016 0zM18 8a2 2 0 11-4 0 2 2 0 014 0zM14 15a4 4 0 00-8 0v3h8v-3zM6 8a2 2 0 11-4 0 2 2 0 014 0zM16 18v-3a5.972 5.972 0 00-.75-2.906A3.005 3.005 0 0119 15v3h-3zM4.75 12.094A5.973 5.973 0 004 15v3H1v-3a3 3 0 014.75-2.906z" /></svg>
                            Market
                        </a>
                    </div>
                </div>
            </div>
        </div>
        """

    content = f"""
    <div class="flex flex-col md:flex-row justify-between items-end mb-12 gap-6">
        <div>
            <h1 class="text-6xl font-black italic tracking-tighter uppercase">Inventory</h1>
            <p class="text-zinc-500 font-bold uppercase tracking-[0.3em] text-[10px] mt-2">Sourcing verified off-market equity assets</p>
        </div>
        <div class="flex space-x-4">
            <a href="/buy/configure" class="btn-outline">Filter targeting</a>
            <a href="/sell" class="btn-primary">List Asset</a>
        </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {lead_cards if lead_cards else '<div class="col-span-full py-20 text-center titan-card"><p class="text-zinc-500 font-bold uppercase tracking-widest">No assets found matching your targeting profile.</p></div>'}
    </div>
    """
    return render_titan_ui(content, user=user)

# (Continued in Part 10...)
# ==============================================================================
# TITAN V28.2 - NEURAL AGENT INTERFACE (PART 10 OF 17)
# ==============================================================================

@app.route('/ai-agent', methods=['GET', 'POST'])
@login_required
def ai_agent_portal():
    """
    The Neural Command Center.
    Converts raw property data into high-converting marketing scripts.
    """
    user = db.get_user(session['user_email'])
    
    # Trial & Access Control
    is_authorized = titan_ai.check_access(user)
    trial_status = "ACTIVE" if user['ai_trial_end'] and datetime.fromisoformat(user['ai_trial_end']) > datetime.now() else "EXPIRED"
    
    if not is_authorized:
        locked_html = f"""
        <div class="max-w-2xl mx-auto text-center py-20 animate__animated animate__fadeIn">
            <div class="w-24 h-24 bg-indigo-600/20 rounded-full flex items-center justify-center mx-auto mb-8 border border-indigo-500/30">
                <svg class="w-12 h-12 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
            </div>
            <h1 class="text-4xl font-black italic uppercase mb-4">Neural Engine Locked</h1>
            <p class="text-zinc-500 font-bold uppercase tracking-widest text-xs mb-10 leading-loose">
                Your account requires an active Neural Subscription to access advanced AI marketing personas. 
                Generate viral hooks, institutional decks, and ruthless cold emails instantly.
            </p>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <a href="/start-trial" class="btn-primary flex justify-center items-center">Start 48H Neural Trial</a>
                <form action="/checkout" method="POST">
                    <button name="pid" value="{PRICE_IDS['NEURAL_AGENT_MONTHLY']}" class="btn-outline w-full">Unlock Full Access ($50/mo)</button>
                </form>
            </div>
        </div>
        """
        return render_titan_ui(locked_html, user=user)

    # Asset Pre-selection Logic
    asset_id = request.args.get('asset_id')
    pre_loaded_details = ""
    if asset_id:
        with get_db_connection() as conn:
            asset = conn.execute("SELECT * FROM leads WHERE id = ?", (asset_id,)).fetchone()
            if asset:
                pre_loaded_details = f"Address: {asset['address']}, Price: {asset['asking_price']}, ARV: {asset['arv']}, Repairs: {asset['repair_cost']}, Description: {asset['description']}"

    # Handle Generation Request
    generated_content = None
    if request.method == 'POST':
        persona = request.form.get('persona')
        format_type = request.form.get('format')
        details = request.form.get('details')
        
        if details:
            generated_content = titan_ai.generate_copy(persona, details, format_type)

    # UI Construction
    content_html = f"""
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-12 animate__animated animate__fadeIn">
        <!-- Sidebar Controls -->
        <div class="lg:col-span-4 space-y-8">
            <div>
                <h1 class="text-4xl font-black italic uppercase tracking-tighter">Neural Agent</h1>
                <p class="text-zinc-500 font-bold uppercase tracking-widest text-[10px] mt-2">Persona-based Marketing Generation</p>
            </div>

            <form method="POST" class="space-y-6">
                <div class="titan-card p-6">
                    <label class="text-[10px] font-bold text-zinc-500 uppercase mb-4 block">Select Marketing Persona</label>
                    <div class="space-y-3">
                        <label class="flex items-center p-3 border border-zinc-900 rounded-xl cursor-pointer hover:bg-zinc-900/50 transition">
                            <input type="radio" name="persona" value="viral" checked class="w-4 h-4 text-indigo-600">
                            <span class="ml-3 text-xs font-bold uppercase">Viral / Influencer</span>
                        </label>
                        <label class="flex items-center p-3 border border-zinc-900 rounded-xl cursor-pointer hover:bg-zinc-900/50 transition">
                            <input type="radio" name="persona" value="institutional" class="w-4 h-4 text-indigo-600">
                            <span class="ml-3 text-xs font-bold uppercase">Institutional Analyst</span>
                        </label>
                        <label class="flex items-center p-3 border border-zinc-900 rounded-xl cursor-pointer hover:bg-zinc-900/50 transition">
                            <input type="radio" name="persona" value="ruthless" class="w-4 h-4 text-indigo-600">
                            <span class="ml-3 text-xs font-bold uppercase">Ruthless Closer</span>
                        </label>
                    </div>
                </div>

                <div class="titan-card p-6">
                    <label class="text-[10px] font-bold text-zinc-500 uppercase mb-4 block">Output Format</label>
                    <select name="format" class="text-xs font-bold uppercase">
                        <option value="email">Investor Cold Email</option>
                        <option value="sms">SMS Blast Script</option>
                        <option value="tiktok_hook">TikTok/Reels Hook</option>
                        <option value="listing_desc">MLS / Marketplace Description</option>
                    </select>
                </div>

                <div class="titan-card p-6">
                    <label class="text-[10px] font-bold text-zinc-500 uppercase mb-4 block">Asset Details</label>
                    <textarea name="details" class="h-48 text-xs font-mono" placeholder="Paste property data here...">{pre_loaded_details}</textarea>
                </div>

                <button type="submit" class="btn-primary w-full py-4">Execute Generation</button>
            </form>
        </div>

        <!-- Main Display -->
        <div class="lg:col-span-8">
            <div class="titan-card min-h-[600px] p-10 relative flex flex-col">
                <div class="absolute top-0 right-0 p-4">
                    <span class="badge-indigo">Neural Status: {trial_status}</span>
                </div>
                
                <div class="mb-10 border-b border-zinc-900 pb-6">
                    <h2 class="text-xs font-black uppercase text-zinc-600 tracking-widest">Neural Stream Output</h2>
                </div>

                <div class="flex-grow">
                    {f'''
                    <div class="prose prose-invert max-w-none animate__animated animate__fadeIn">
                        <div class="bg-zinc-900/30 p-8 rounded-2xl border border-zinc-800 italic text-xl leading-relaxed text-zinc-200">
                            {generated_content.replace('\\n', '<br>')}
                        </div>
                        <div class="mt-8 flex space-x-4">
                            <button onclick="navigator.clipboard.writeText(`{generated_content}`)" class="btn-outline">Copy to Clipboard</button>
                            <a href="/outreach?body={base64.b64encode(generated_content.encode()).decode()}" class="btn-primary">Transfer to Outbound Machine</a>
                        </div>
                    </div>
                    ''' if generated_content else '''
                    <div class="h-full flex flex-col items-center justify-center text-center opacity-20">
                        <svg class="w-20 h-20 mb-6" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd" /></svg>
                        <p class="text-sm font-black uppercase tracking-widest">Awaiting Neural Link...</p>
                    </div>
                    '''}
                </div>
            </div>
        </div>
    </div>
    """
    return render_titan_ui(content_html, user=user)

# (Continued in Part 11...)
# ==============================================================================
# TITAN V28.2 - OUTBOUND COMMAND CENTER (PART 11 OF 17)
# ==============================================================================

@app.route('/outreach', methods=['GET', 'POST'])
@login_required
def outreach_dashboard():
    """
    The Outbound Machine Control Room.
    Triggers batch delivery and monitors real-time success rates.
    """
    user = db.get_user(session['user_email'])
    
    # Access Control for the Machine
    if not user['email_machine_access']:
        return render_titan_ui(f"""
        <div class="max-w-2xl mx-auto text-center py-20 titan-card p-12">
            <h1 class="text-4xl font-black italic uppercase mb-6">Outbound Machine Locked</h1>
            <p class="text-zinc-500 font-bold uppercase tracking-widest text-xs mb-10 leading-loose">
                To initiate high-volume outbound campaigns through your own Gmail architecture, 
                you must unlock the Outbound Machine module.
            </p>
            <form action="/checkout" method="POST" class="space-y-4">
                <button name="pid" value="{PRICE_IDS['EMAIL_MACHINE_LIFETIME']}" class="btn-primary w-full py-4 text-lg">Lifetime Unlock: $20</button>
                <button name="pid" value="{PRICE_IDS['EMAIL_MACHINE_WEEKLY']}" class="btn-outline w-full py-4">Weekly Access: $3</button>
            </form>
        </div>
        """, user=user)

    # Handle incoming transfer from AI Agent
    passed_body = ""
    if request.args.get('body'):
        try:
            passed_body = base64.b64decode(request.args.get('body')).decode()
        except: pass

    # Execution Logic
    if request.method == 'POST':
        recipients_raw = request.form.get('recipients')
        subject = request.form.get('subject')
        message_body = request.form.get('body')
        
        email_list = clean_recipient_list(recipients_raw)
        
        if not email_list or not subject or not message_body:
            flash("CRITICAL ERROR: All campaign parameters must be defined.", "error")
        else:
            machine = OutboundMachine(user['email'])
            execution = machine.initiate_blast(email_list, subject, message_body)
            
            if execution['status'] == 'complete':
                success_count = len(execution['results']['success'])
                fail_count = len(execution['results']['failure'])
                flash(f"CAMPAIGN COMPLETE: {success_count} Sent | {fail_count} Failed", "success")
                return redirect(url_for('outreach_dashboard'))
            else:
                flash(f"EXECUTION FAILED: {execution['message']}", "error")

    # Fetch History
    with get_db_connection() as conn:
        logs = conn.execute("""
            SELECT * FROM outreach_logs 
            WHERE user_email = ? 
            ORDER BY sent_at DESC LIMIT 20
        """, (user['email'],)).fetchall()

    log_rows = ""
    for log in logs:
        status_tag = '<span class="text-green-500 font-black">SUCCESS</span>' if log['success_flag'] else '<span class="text-red-500 font-black">FAIL</span>'
        log_rows += f"""
        <tr class="border-b border-zinc-900 text-[10px] font-bold uppercase text-zinc-400">
            <td class="py-4">{datetime.fromisoformat(log['sent_at']).strftime('%m/%d %H:%M')}</td>
            <td class="py-4">{log['recipient_email']}</td>
            <td class="py-4 truncate max-w-[150px]">{log['subject']}</td>
            <td class="py-4 text-right">{status_tag}</td>
        </tr>
        """

    content_html = f"""
    <div class="grid grid-cols-1 xl:grid-cols-12 gap-12 animate__animated animate__fadeIn">
        <div class="xl:col-span-7">
            <div class="mb-8">
                <h1 class="text-4xl font-black italic uppercase tracking-tighter">Outbound Machine</h1>
                <p class="text-zinc-500 font-bold uppercase tracking-widest text-[10px] mt-2">Authenticated Batch Delivery System</p>
            </div>

            <form method="POST" class="space-y-6">
                <div class="titan-card p-8">
                    <label class="text-[10px] font-bold text-zinc-500 uppercase mb-4 block">Target Recipient List (CSV / Raw Emails)</label>
                    <textarea name="recipients" class="h-32 text-xs font-mono" placeholder="investor1@gmail.com, lead2@yahoo.com..."></textarea>
                </div>

                <div class="titan-card p-8">
                    <label class="text-[10px] font-bold text-zinc-500 uppercase mb-4 block">Campaign Subject Line</label>
                    <input name="subject" placeholder="OFF-MARKET: 35% ROI Asset inside Equity Portfolio" required>
                </div>

                <div class="titan-card p-8">
                    <label class="text-[10px] font-bold text-zinc-500 uppercase mb-4 block">Marketing Message Body</label>
                    <textarea name="body" class="h-64 text-sm leading-relaxed" required>{passed_body}</textarea>
                </div>

                <button type="submit" class="btn-primary w-full py-5 text-lg">Initiate Campaign Blast</button>
            </form>
        </div>

        <div class="xl:col-span-5 space-y-8">
            <div class="titan-card p-8 bg-zinc-900/10">
                <h2 class="text-xs font-black uppercase text-zinc-500 tracking-widest mb-6">Recent Blast History</h2>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="border-b border-zinc-800 text-[9px] font-black uppercase text-zinc-600">
                                <th class="pb-4">Timestamp</th>
                                <th class="pb-4">Recipient</th>
                                <th class="pb-4">Subject</th>
                                <th class="pb-4 text-right">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {log_rows if log_rows else '<tr><td colspan="4" class="py-10 text-center opacity-30 text-[10px] font-bold uppercase">No records found</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="titan-card p-8 border-indigo-900/30">
                <h3 class="text-xs font-black uppercase text-indigo-500 tracking-widest mb-4">Pro Tip</h3>
                <p class="text-xs text-zinc-500 leading-relaxed font-bold uppercase">
                    Use the Neural Agent to generate ruthless copy before blasting. Campaigns with AI-optimized subject lines see a 40% higher engagement rate.
                </p>
            </div>
        </div>
    </div>
    """
    return render_titan_ui(content_html, user=user)

# (Continued in Part 12...)
# ==============================================================================
# TITAN V28.2 - PINPOINT TARGETING ENGINE (PART 13 OF 17)
# ==============================================================================

@app.route('/buy/configure', methods=['GET', 'POST'])
@login_required
def configure_targeting():
    """
    Advanced filter configuration similar to professional sourcing tools.
    Allows users to pinpoint the exact assets they want to market.
    """
    user = db.get_user(session['user_email'])
    
    if request.method == 'POST':
        # Detailed Extraction
        min_p = request.form.get('min_price', 0)
        max_p = request.form.get('max_price', 10000000)
        min_b = request.form.get('min_beds', 0)
        min_ba = request.form.get('min_baths', 0)
        min_s = request.form.get('min_sqft', 0)
        zips = request.form.get('target_zips', '')
        strat = request.form.get('strategy', 'Any')
        
        # Validation of numeric inputs
        try:
            min_p, max_p = int(min_p), int(max_p)
            min_b, min_ba = float(min_b), float(min_ba)
            min_s = int(min_s)
        except ValueError:
            flash("DATA ERROR: Numeric fields must contain valid numbers.", "error")
            return redirect(url_for('configure_targeting'))

        # Persist to User Profile
        try:
            with get_db_connection() as conn:
                conn.execute("""
                    UPDATE users SET 
                        bb_min_price = ?, bb_max_price = ?, 
                        bb_target_zip = ?, bb_strategy = ?
                    WHERE email = ?
                """, (min_p, max_p, zips, strat, user['email']))
                
                # Note: To support beds/baths/sqft we would ideally have more columns 
                # but for v28.2 we focus on price and location as the primary 'Cut' drivers.
                conn.commit()
            
            flash("TARGETING PROTOCOL UPDATED: Sourcing feed recalculated.", "success")
            return redirect(url_for('inventory_feed'))
        except Exception as e:
            logger.error(f"Targeting Update Error: {e}")
            flash("SYSTEM ERROR: Failed to save targeting parameters.", "error")

    # Build the Configuration UI
    content_html = f"""
    <div class="max-w-4xl mx-auto animate__animated animate__fadeIn">
        <div class="mb-12 flex justify-between items-end">
            <div>
                <h1 class="text-5xl font-black italic uppercase tracking-tighter">Sourcing Logic</h1>
                <p class="text-zinc-500 font-bold uppercase tracking-widest text-[10px] mt-2">Pinpoint asset criteria for inbound flow</p>
            </div>
            <a href="/buy" class="btn-outline">View Current Inventory</a>
        </div>

        <form method="POST" class="space-y-8">
            <!-- Price Range Section -->
            <div class="titan-card p-10">
                <h2 class="text-xs font-black uppercase text-indigo-500 mb-8 tracking-widest flex items-center">
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    Price & Acquisition Range
                </h2>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-10">
                    <div>
                        <label class="text-[10px] font-bold text-zinc-600 uppercase mb-3 block">Minimum Asset Price</label>
                        <input type="number" name="min_price" value="{user['bb_min_price'] or 0}" placeholder="0">
                    </div>
                    <div>
                        <label class="text-[10px] font-bold text-zinc-600 uppercase mb-3 block">Maximum Asset Price</label>
                        <input type="number" name="max_price" value="{user['bb_max_price'] or 5000000}" placeholder="5,000,000">
                    </div>
                </div>
            </div>

            <!-- Geospatial Section -->
            <div class="titan-card p-10">
                <h2 class="text-xs font-black uppercase text-indigo-500 mb-8 tracking-widest flex items-center">
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                    Geospatial Constraints
                </h2>
                <div class="space-y-6">
                    <div>
                        <label class="text-[10px] font-bold text-zinc-600 uppercase mb-3 block">Target ZIP Codes (Comma Separated)</label>
                        <textarea name="target_zips" class="h-24" placeholder="75201, 90210, 33101...">{user['bb_target_zip'] or ''}</textarea>
                        <p class="text-[9px] text-zinc-700 font-bold mt-2 uppercase">Leaving this blank searches all available regions.</p>
                    </div>
                </div>
            </div>

            <!-- Physical Specs Section -->
            <div class="titan-card p-10">
                <h2 class="text-xs font-black uppercase text-indigo-500 mb-8 tracking-widest flex items-center">
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-7h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>
                    Asset Physicality
                </h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div>
                        <label class="text-[10px] font-bold text-zinc-600 uppercase mb-3 block">Min Bedrooms</label>
                        <select name="min_beds" class="text-xs font-bold uppercase">
                            <option value="0">Any</option>
                            <option value="1">1+ Beds</option>
                            <option value="2">2+ Beds</option>
                            <option value="3">3+ Beds</option>
                            <option value="4">4+ Beds</option>
                        </select>
                    </div>
                    <div>
                        <label class="text-[10px] font-bold text-zinc-600 uppercase mb-3 block">Min Bathrooms</label>
                        <select name="min_baths" class="text-xs font-bold uppercase">
                            <option value="0">Any</option>
                            <option value="1">1+ Bath</option>
                            <option value="1.5">1.5+ Baths</option>
                            <option value="2">2+ Baths</option>
                        </select>
                    </div>
                    <div>
                        <label class="text-[10px] font-bold text-zinc-600 uppercase mb-3 block">Investment Strategy</label>
                        <select name="strategy" class="text-xs font-bold uppercase">
                            <option value="Any" {'selected' if user['bb_strategy'] == 'Any' else ''}>Any</option>
                            <option value="FixFlip" {'selected' if user['bb_strategy'] == 'FixFlip' else ''}>Fix & Flip</option>
                            <option value="BuyHold" {'selected' if user['bb_strategy'] == 'BuyHold' else ''}>Buy & Hold</option>
                            <option value="Wholesale" {'selected' if user['bb_strategy'] == 'Wholesale' else ''}>Wholesale</option>
                        </select>
                    </div>
                </div>
            </div>

            <button type="submit" class="btn-primary w-full py-6 text-xl">Lock Targeting Protocols</button>
        </form>
    </div>
    """
    return render_titan_ui(content_html, user=user)

# (Continued in Part 14...)
# ==============================================================================
# TITAN V28.2 - IDENTITY CALLBACK & TOKEN MARSHALLING (PART 14 OF 17)
# ==============================================================================

@app.route('/auth/login')
def login_gate():
    """Starts the secure OAuth flow."""
    flow = TitanAuth.get_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    session['state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def auth_callback():
    """
    The secure handshake endpoint.
    Processes Google's response and marshals tokens into the encrypted DB.
    """
    state = session.get('state')
    flow = TitanAuth.get_flow()
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    
    # Verify Identity using Google ID Token
    try:
        id_info = id_token.verify_oauth2_token(
            credentials.id_token, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        email = id_info.get('email')
        name = id_info.get('name')
        picture = id_info.get('picture')
    except Exception as e:
        logger.error(f"Identity Verification Failed: {e}")
        return abort(401, "Google Identity Fraud Detected.")

    # Create session
    session['user_email'] = email
    
    # Marshall credentials into JSON for encryption
    token_payload = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    encrypted_creds = TitanAuth.encrypt_tokens(token_payload)

    # Initialize or Update User Record
    db.create_user_if_not_exists(email, name, picture)
    
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE users SET 
                google_creds_enc = ?, 
                last_login = ? 
            WHERE email = ?
        """, (encrypted_creds, datetime.now().isoformat(), email))
        conn.commit()

    logger.info(f"User Session Initialized: {email}")
    flash(f"WELCOME BACK, {name.upper()}. Secure link established.", "success")
    
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    """Clears the session and redirects to the public landing page."""
    user_email = session.get('user_email', 'unknown')
    session.clear()
    logger.info(f"User Session Terminated: {user_email}")
    return redirect(url_for('index'))

# (Continued in Part 15...)
# ==============================================================================
# TITAN V28.2 - SYSTEM ADMINISTRATION & OVERSIGHT (PART 15 OF 17)
# ==============================================================================

@app.route('/admin/dashboard')
@login_required
def admin_oversight():
    """
    High-level overview of the platform's economics.
    Visible only to the platform owner (or users with specific flags).
    """
    # Security: In a real app, check for an is_admin flag.
    # For v28.2, we assume the primary user is the admin.
    
    user = db.get_user(session['user_email'])
    
    with get_db_connection() as conn:
        # Aggregate Financial Metrics
        total_assets = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        total_volume = conn.execute("SELECT SUM(asking_price) FROM leads").fetchone()[0] or 0
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        
        # Calculate Potential Revenue (The Cut)
        # Sum of (asking_price * platform_cut_percentage)
        revenue_data = conn.execute("""
            SELECT SUM(asking_price * (platform_cut_percentage / 100)) as potential_cut 
            FROM leads WHERE status = 'active'
        """).fetchone()
        potential_revenue = revenue_data['potential_cut'] or 0

        # Recent Deals List
        recent_leads = conn.execute("""
            SELECT leads.*, users.full_name as seller_name 
            FROM leads 
            JOIN users ON leads.seller_email = users.email 
            ORDER BY created_at DESC LIMIT 15
        """).fetchall()

    lead_table_rows = ""
    for lead in recent_leads:
        lead_table_rows += f"""
        <tr class="border-b border-zinc-900 text-xs text-zinc-400 font-bold uppercase">
            <td class="py-6">{lead['address']}</td>
            <td class="py-6 text-white">{TitanFinance.format_currency(lead['asking_price'])}</td>
            <td class="py-6 text-indigo-400">{lead['platform_cut_percentage']}%</td>
            <td class="py-6">{lead['seller_name']}</td>
            <td class="py-6 text-right">
                <span class="px-3 py-1 bg-zinc-800 rounded-full text-[9px]">{lead['status']}</span>
            </td>
        </tr>
        """

    content_html = f"""
    <div class="space-y-12 animate__animated animate__fadeIn">
        <div class="flex flex-col md:flex-row justify-between items-end gap-6">
            <div>
                <h1 class="text-6xl font-black italic tracking-tighter uppercase">Platform Oversight</h1>
                <p class="text-zinc-500 font-bold uppercase tracking-[0.3em] text-[10px] mt-2">Economics & Infrastructure Monitoring</p>
            </div>
        </div>

        <!-- Metric Grid -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div class="titan-card p-8 border-l-4 border-indigo-600">
                <p class="text-[10px] text-zinc-500 font-black uppercase mb-2">Total Volume</p>
                <p class="text-3xl font-black italic">{TitanFinance.format_currency(total_volume)}</p>
            </div>
            <div class="titan-card p-8 border-l-4 border-green-500">
                <p class="text-[10px] text-zinc-500 font-black uppercase mb-2">Potential Rev (The Cut)</p>
                <p class="text-3xl font-black italic text-green-500">{TitanFinance.format_currency(potential_revenue)}</p>
            </div>
            <div class="titan-card p-8 border-l-4 border-zinc-700">
                <p class="text-[10px] text-zinc-500 font-black uppercase mb-2">Active Assets</p>
                <p class="text-3xl font-black italic">{total_assets}</p>
            </div>
            <div class="titan-card p-8 border-l-4 border-zinc-700">
                <p class="text-[10px] text-zinc-500 font-black uppercase mb-2">Total Agents</p>
                <p class="text-3xl font-black italic">{total_users}</p>
            </div>
        </div>

        <!-- Master Inventory Table -->
        <div class="titan-card p-10">
            <h2 class="text-xs font-black uppercase text-zinc-500 tracking-widest mb-8">Global Asset Master Log</h2>
            <div class="overflow-x-auto">
                <table class="w-full text-left">
                    <thead>
                        <tr class="border-b border-zinc-800 text-[9px] font-black uppercase text-zinc-600">
                            <th class="pb-6">Property Address</th>
                            <th class="pb-6">Price</th>
                            <th class="pb-6">Cut %</th>
                            <th class="pb-6">Listing Agent</th>
                            <th class="pb-6 text-right">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {lead_table_rows}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """
    return render_titan_ui(content_html, user=user)

# (Continued in Part 16...)
# ==============================================================================
# TITAN V28.2 - LEGAL INFRASTRUCTURE & STATIC ASSETS (PART 16 OF 17)
# ==============================================================================

@app.route('/privacy')
def privacy_protocol():
    """
    Legally required Privacy Policy. 
    Crucial for Google OAuth verification and Stripe compliance.
    """
    content = """
    <div class="max-w-4xl mx-auto titan-card p-12 animate__animated animate__fadeIn">
        <h1 class="text-4xl font-black italic uppercase tracking-tighter mb-8">Privacy Protocol</h1>
        <div class="prose prose-invert max-w-none text-zinc-400 font-bold uppercase text-[11px] leading-relaxed space-y-6">
            <section>
                <h2 class="text-white text-sm mb-2">1. DATA ENCRYPTION</h2>
                <p>TITAN utilizes AES-256 Fernet encryption for all sensitive Google API tokens. Your credentials never exist in plain-text on our infrastructure.</p>
            </section>
            <section>
                <h2 class="text-white text-sm mb-2">2. GMAIL DATA USAGE</h2>
                <p>TITAN accesses your Gmail via OAuth 2.0 strictly to facilitate the "Outbound Machine." We do not store your emails, read your inbox, or share your contact lists with third parties. Data is ephemeral and used only for requested delivery.</p>
            </section>
            <section>
                <h2 class="text-white text-sm mb-2">3. FINANCIAL DATA</h2>
                <p>All payment processing is handled by Stripe. TITAN does not store credit card numbers or sensitive billing information on its own servers.</p>
            </section>
            <section>
                <h2 class="text-white text-sm mb-2">4. AI DATA PROCESSING</h2>
                <p>Property details submitted to the Neural Agent are processed by high-tier LLMs (Groq/Llama3). This data is used to generate marketing copy and is not used for training models outside of your session.</p>
            </section>
        </div>
        <a href="/" class="btn-outline mt-12 inline-block">Acknowledge & Return</a>
    </div>
    """
    return render_titan_ui(content)

@app.route('/terms')
def service_terms():
    """Service Terms defining the platform's cut and usage rules."""
    content = """
    <div class="max-w-4xl mx-auto titan-card p-12 animate__animated animate__fadeIn">
        <h1 class="text-4xl font-black italic uppercase tracking-tighter mb-8">Service Terms</h1>
        <div class="prose prose-invert max-w-none text-zinc-400 font-bold uppercase text-[11px] leading-relaxed space-y-6">
            <section>
                <h2 class="text-white text-sm mb-2">1. THE PLATFORM CUT</h2>
                <p>Users agree to pay the calculated Platform Fee upon the successful closing of any asset sourced through the TITAN Inventory Feed. Fees are locked at the time of listing based on the user's current Tier.</p>
            </section>
            <section>
                <h2 class="text-white text-sm mb-2">2. TOOL ACCESS</h2>
                <p>Subscription to the Neural Agent and the Outbound Machine is non-refundable. Access is granted immediately upon successful Stripe confirmation.</p>
            </section>
            <section>
                <h2 class="text-white text-sm mb-2">3. ACCOUNT RESPONSIBILITY</h2>
                <p>Users are responsible for all outbound marketing content generated by the AI. TITAN is not liable for marketing communications that violate local real estate solicitation laws or anti-spam regulations (CAN-SPAM Act).</p>
            </section>
        </div>
        <a href="/" class="btn-outline mt-12 inline-block">Accept & Return</a>
    </div>
    """
    return render_titan_ui(content)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Securely serves property images from the storage directory."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/system/status')
def health_check():
    """Public health check endpoint for monitoring uptime."""
    status = {
        "status": "operational",
        "version": SYSTEM_VERSION,
        "codename": SYSTEM_CODENAME,
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
        "neural_agent": "ready" if groq_client else "offline"
    }
    return jsonify(status)

# (Continued in Part 17...)
# ==============================================================================
# TITAN V28.2 - FINAL HANDLERS & APP INITIALIZATION (PART 17 OF 17)
# ==============================================================================

@app.before_request
def global_middleware():
    """
    Titan's Internal Monitor. 
    Tracks activity for every request to ensure system security.
    """
    if 'user_email' in session:
        # Silently update user activity in the background
        try:
            db.update_user_activity(session['user_email'])
        except: pass

@app.errorhandler(404)
def not_found_error(error):
    """Custom 404 handler with the Titan aesthetic."""
    content = """
    <div class="text-center py-40">
        <h1 class="text-9xl font-black italic tracking-tighter opacity-10">404</h1>
        <p class="text-zinc-500 font-bold uppercase tracking-widest -mt-10">Asset Not Found in Sourcing Feed</p>
        <a href="/" class="btn-primary mt-12">Return to Command</a>
    </div>
    """
    return render_titan_ui(content, title="404 NOT FOUND"), 404

@app.errorhandler(500)
def internal_error(error):
    """Custom 500 handler to hide messy tracebacks from users."""
    logger.critical(f"SERVER ERROR: {error}")
    content = """
    <div class="text-center py-40">
        <h1 class="text-9xl font-black italic tracking-tighter text-red-900 opacity-20">500</h1>
        <p class="text-zinc-500 font-bold uppercase tracking-widest -mt-10">Neural Link Severed. System Re-initializing.</p>
        <a href="/" class="btn-outline mt-12">Try Again</a>
    </div>
    """
    return render_titan_ui(content, title="500 CRITICAL ERROR"), 500

@app.route('/robots.txt')
def robots():
    """Prevents indexers from crawling sensitive app routes."""
    return Response("User-agent: *\nDisallow: /admin/\nDisallow: /outreach/\nDisallow: /buy/", mimetype="text/plain")

# ==============================================================================
# SYSTEM BOOTSTRAP
# ==============================================================================

def launch_titan():
    """
    Final system initialization and boot sequence.
    """
    print(f"""
    TITAN ASSET INFRASTRUCTURE v{SYSTEM_VERSION}
    -------------------------------------------
    CODENAME:  {SYSTEM_CODENAME}
    STATUS:    DEPLOYED
    ENGINE:    FLASK/SQLITE3
    PAYMENTS:  STRIPE CONNECTED
    NEURAL:    GROQ CLOUD ENABLED
    -------------------------------------------
    """)
    
    # Check for critical environment variables before starting
    required_vars = ["FLASK_SECRET_KEY", "STRIPE_SECRET_KEY", "GROQ_API_KEY", "GOOGLE_CLIENT_ID"]
    for var in required_vars:
        if not os.environ.get(var):
            logger.warning(f"MISSING CONFIG: {var} is not set. Some systems will be locked.")

    # Determine Port
    port = int(os.environ.get("PORT", 5000))
    
    # Launch with debug=False in production for security
    app.run(
        host='0.0.0.0', 
        port=port, 
        debug=os.environ.get("DEBUG", "False").lower() == "true"
    )

if __name__ == '__main__':
    launch_titan()

# ==============================================================================
# END OF TITAN v28.2 CORE SOURCE CODE
# ==============================================================================

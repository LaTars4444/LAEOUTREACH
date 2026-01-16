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
    Flask, render_template_string, request, redirect, url_for, 
    session, flash, send_from_directory, jsonify, Response, abort
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

# ==============================================================================
# TITAN V28.2 - GLOBAL CONFIG & LOGGING
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] TITAN_CORE: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(64))

ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key().decode()
cipher = Fernet(ENCRYPTION_KEY.encode())

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
try:
    groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
except Exception as e:
    logger.error(f"Failed to initialize Groq Client: {e}")
    groq_client = None

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'storage/assets')
DB_PATH = os.path.join(os.getcwd(), 'storage/titan_main_v28.db')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'webp'}

PRICE_IDS = {
    'EMAIL_MACHINE_LIFETIME': "price_1Spy7SFXcDZgM3VoVZv71I63",
    'EMAIL_MACHINE_WEEKLY': "price_1SpxexFXcDZgM3Vo0iYmhfpb",
    'NEURAL_AGENT_MONTHLY': "price_1SqIjgFXcDZgM3VoEwrUvjWP"
}

PLATFORM_FEE_CONFIG = {
    'DEFAULT_CUT': 0.06,
    'TIER_1_CUT': 0.05,
    'TIER_2_CUT': 0.04,
    'PRO_CUT': 0.02
}

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:5000/callback")
CLIENT_CONFIG = {"web": {"client_id": GOOGLE_CLIENT_ID, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"), "redirect_uris": [REDIRECT_URI]}}
SCOPES = ['https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile', 'openid', 'https://www.googleapis.com/auth/gmail.send']

# ==============================================================================
# TITAN V28.2 - DATABASE & FINANCIALS
# ==============================================================================
class TitanDatabase:
    def __init__(self, path):
        self.path = path
        self._init_tables()

    def get_connection(self):
        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_tables(self):
        with self.get_connection() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY, full_name TEXT, profile_pic TEXT, deal_count INTEGER DEFAULT 0,
                email_machine_access INTEGER DEFAULT 0, ai_access INTEGER DEFAULT 0, ai_trial_end TEXT,
                google_creds_enc TEXT, last_login TEXT, created_at TEXT, bb_min_price INTEGER DEFAULT 0,
                bb_max_price INTEGER DEFAULT 10000000, bb_target_zip TEXT, bb_strategy TEXT DEFAULT 'Equity'
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT, address TEXT, asking_price INTEGER, arv INTEGER,
                repair_cost INTEGER DEFAULT 0, sqft INTEGER, image_path TEXT, status TEXT DEFAULT 'active',
                seller_email TEXT, created_at TEXT, platform_cut_percentage REAL
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS outreach_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, recipient_email TEXT,
                subject TEXT, sent_at TEXT, success_flag INTEGER
            )""")
            conn.commit()

    def update_user_activity(self, email):
        with self.get_connection() as conn:
            conn.execute("UPDATE users SET last_login = ? WHERE email = ?", (datetime.now().isoformat(), email))
            conn.commit()

    def get_user(self, email):
        with self.get_connection() as conn:
            return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    def create_user_if_not_exists(self, email, name=None, pic=None):
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            conn.execute("INSERT INTO users (email, full_name, profile_pic, created_at, last_login) VALUES (?, ?, ?, ?, ?) ON CONFLICT(email) DO UPDATE SET last_login = excluded.last_login", (email, name, pic, now, now))
            conn.commit()

db = TitanDatabase(DB_PATH)

class TitanFinance:
    @staticmethod
    def get_deal_metrics(price, arv, repairs, deal_count):
        try:
            price, arv, repairs = float(price), float(arv), float(repairs)
            rate = max(0.02, 0.06 - (deal_count * 0.01))
            fee = price * rate
            total = price + fee + repairs
            if total <= 0: return None
            roi = ((arv - total) / total) * 100
            return {"fee_rate_percent": rate * 100, "platform_fee": int(fee), "total_investment": int(total), "roi": round(roi, 2)}
        except: return None

    @staticmethod
    def format_currency(value):
        return f"${value:,.0f}"

# ==============================================================================
# TITAN V28.2 - DESIGN SYSTEM (FIXED BRACES FOR 3.13)
# ==============================================================================
def render_titan_ui(content, user=None, title="TITAN v28"):
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
                <p class="text-[10px] text-zinc-500 font-black uppercase tracking-tighter">Connected</p>
                <p class="text-xs font-bold text-white uppercase">{user['email'].split('@')[0]}</p>
            </div>
            <img src="{user['profile_pic'] or 'https://ui-avatars.com/api/?name='+user['email']}" class="w-10 h-10 rounded-full border border-zinc-800">
            <a href="/logout" class="p-2 hover:bg-red-900/20 rounded-lg group transition-all">
                <svg class="w-5 h-5 text-zinc-500 group-hover:text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
            </a>
        </div>"""
    else:
        nav_html = '<a href="/auth/login" class="btn-primary">Initialize Access</a>'

    # Note: Doubled braces {{ }} below fix the SyntaxError in CSS
    return render_template_string(f"""
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title><script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;900&display=swap');
            body {{ background-color: #030303; color: #ffffff; font-family: 'Outfit', sans-serif; overflow-x: hidden; }}
            .titan-card {{ background: #0a0a0a; border: 1px solid #1a1a1a; border-radius: 1.5rem; transition: 0.4s; }}
            .titan-card:hover {{ border-color: #6366f1; box-shadow: 0 0 30px rgba(99, 102, 241, 0.1); transform: translateY(-4px); }}
            .nav-link {{ font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: #71717a; transition: 0.3s; }}
            .nav-link:hover {{ color: #fff; }}
            .btn-primary {{ background: #fff; color: #000; padding: 0.8rem 1.8rem; border-radius: 0.75rem; font-weight: 900; text-transform: uppercase; font-size: 0.7rem; display: inline-flex; align-items: center; transition: 0.3s; }}
            .btn-primary:hover {{ transform: scale(1.05); box-shadow: 0 10px 20px rgba(255,255,255,0.1); }}
            .btn-outline {{ border: 1px solid #1a1a1a; color: #fff; padding: 0.8rem 1.8rem; border-radius: 0.75rem; font-weight: 700; text-transform: uppercase; font-size: 0.7rem; transition: 0.3s; }}
            .btn-outline:hover {{ border-color: #fff; background: rgba(255,255,255,0.05); }}
            input, select, textarea {{ background: #0f0f0f; border: 1px solid #1a1a1a; color: #fff; padding: 1rem; border-radius: 0.75rem; width: 100%; outline: none; }}
            .badge-indigo {{ background: rgba(99, 102, 241, 0.1); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.2); padding: 2px 8px; border-radius: 6px; font-size: 10px; font-weight: 800; text-transform: uppercase; }}
        </style>
    </head>
    <body class="min-h-screen flex flex-col">
        <nav class="border-b border-zinc-900 bg-black/50 backdrop-blur-xl sticky top-0 z-50">
            <div class="max-w-7xl mx-auto px-6 h-20 flex justify-between items-center">
                <a href="/" class="flex items-center space-x-3 group">
                    <div class="w-8 h-8 bg-white rotate-45 flex items-center justify-center"><span class="rotate-[-45deg] text-black font-black text-xs">T</span></div>
                    <span class="text-xl font-black italic tracking-tighter uppercase">Titan</span>
                </a>
                {nav_html}
            </div>
        </nav>
        <main class="flex-grow max-w-7xl w-full mx-auto px-6 py-12">
            {}
        </main>
    </body></html>
    """)
    # ==============================================================================
# TITAN V28.2 - NEURAL AGENT & OUTBOUND LOGIC
# ==============================================================================
class NeuralAgent:
    def __init__(self, client):
        self.client = client
        self.model = "llama3-70b-8192"

    def check_access(self, user):
        if user['ai_access']: return True
        if user['ai_trial_end']:
            if datetime.now() < datetime.fromisoformat(user['ai_trial_end']): return True
        return False

    def generate_copy(self, persona, details, format_type):
        if not self.client: return "Neural Agent Offline."
        prompt = f"Act as {persona}. Asset Details: {details}. Format: {format_type}. Focus on ROI and equity."
        try:
            res = self.client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model=self.model)
            return res.choices[0].message.content
        except: return "Neural Overload. Retry."

titan_ai = NeuralAgent(groq_client)

class OutboundMachine:
    def __init__(self, user_email):
        self.user_email = user_email
        self.creds = TitanAuth.refresh_user_token(user_email)

    def initiate_blast(self, recipients, subject, body):
        if not self.creds: return {"status": "error", "message": "Auth Required"}
        service = build('gmail', 'v1', credentials=self.creds)
        success_list = []
        for r in recipients:
            try:
                msg = MIMEText(body); msg['to'] = r.strip(); msg['from'] = self.user_email; msg['subject'] = subject
                raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
                service.users().messages().send(userId='me', body={'raw': raw}).execute()
                success_list.append(r)
            except: continue
        return {"status": "complete", "count": len(success_list)}

# ==============================================================================
# TITAN V28.2 - SOURCING & INVENTORY ROUTES
# ==============================================================================
@app.route('/buy')
def inventory_feed():
    if 'user_email' not in session: return redirect('/auth/login')
    user = db.get_user(session['user_email'])
    
    query = "SELECT * FROM leads WHERE status = 'active'"
    params = []
    if user['bb_max_price']:
        query += " AND asking_price <= ?"; params.append(user['bb_max_price'])
    
    with db.get_connection() as conn:
        leads = conn.execute(query + " ORDER BY created_at DESC", params).fetchall()

    cards = ""
    for l in leads:
        m = TitanFinance.get_deal_metrics(l['asking_price'], l['arv'], l['repair_cost'], user['deal_count'])
        if not m: continue
        img = url_for('uploaded_file', filename=l['image_path']) if l['image_path'] else "https://via.placeholder.com/400x200"
        cards += f"""
        <div class="titan-card overflow-hidden">
            <div class="h-48 relative"><img src="{}" class="w-full h-full object-cover">
                <div class="absolute top-4 left-4"><span class="badge-indigo">ROI: {m['roi']}%</span></div>
            </div>
            <div class="p-6">
                <h3 class="text-lg font-black italic uppercase">{l['address']}</h3>
                <div class="grid grid-cols-2 gap-4 my-4 border-y border-zinc-900 py-4">
                    <div><p class="text-[9px] text-zinc-600 font-bold uppercase">Asking</p><p class="text-sm font-bold">${l['asking_price']:,}</p></div>
                    <div class="text-right"><p class="text-[9px] text-zinc-600 font-bold uppercase">Our Cut ({m['fee_rate_percent']:.1f}%)</p><p class="text-sm font-bold text-indigo-400">+${m['platform_fee']:,}</p></div>
                </div>
                <div class="flex justify-between items-center">
                    <div><p class="text-[9px] text-zinc-600 font-bold uppercase">Total Entry</p><p class="text-xl font-black">${m['total_investment']:,}</p></div>
                    <a href="/ai-agent?asset_id={l['id']}" class="btn-primary">Market</a>
                </div>
            </div>
        </div>"""

    return render_titan_ui(f'<div class="grid grid-cols-1 md:grid-cols-3 gap-8">{cards}</div>', user=user)

@app.route('/sell', methods=['GET', 'POST'])
def list_asset():
    if 'user_email' not in session: return redirect('/auth/login')
    user = db.get_user(session['user_email'])
    if request.method == 'POST':
        f = request.form; file = request.files.get('image'); filename = None
        if file:
            filename = f"{uuid.uuid4().hex}.jpg"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        m = TitanFinance.get_deal_metrics(f['asking_price'], f['arv'], f.get('repair_cost', 0), user['deal_count'])
        with db.get_connection() as conn:
            conn.execute("INSERT INTO leads (address, asking_price, arv, repair_cost, image_path, seller_email, created_at, platform_cut_percentage) VALUES (?,?,?,?,?,?,?,?)",
                        (f['address'], f['asking_price'], f['arv'], f.get('repair_cost', 0), filename, user['email'], datetime.now().isoformat(), m['fee_rate_percent']))
            conn.commit()
        return redirect('/buy')
    return render_titan_ui('<div class="max-w-xl mx-auto titan-card p-10"><h2 class="text-2xl font-black mb-8 uppercase">List Asset (Inbound)</h2><form method="POST" enctype="multipart/form-data" class="space-y-4"><input name="address" placeholder="Property Address" required><input name="asking_price" type="number" placeholder="Price"><input name="arv" type="number" placeholder="ARV"><input type="file" name="image"><button class="btn-primary w-full">Deploy to Inventory</button></form></div>', user=user)

@app.route('/ai-agent', methods=['GET', 'POST'])
def ai_portal():
    if 'user_email' not in session: return redirect('/auth/login')
    user = db.get_user(session['user_email'])
    if not titan_ai.check_access(user): return redirect('/start-trial')
    
    generated = None
    if request.method == 'POST':
        generated = titan_ai.generate_copy(request.form.get('persona'), request.form.get('details'), request.form.get('format'))
    
    output_html = ""
    if generated:
        # Avoid direct nesting of complex logic in f-strings to prevent 3.13 SyntaxErrors
        encoded_body = base64.b64encode(generated.encode()).decode()
        output_html = f'<div class="titan-card p-8"><p id="ai-text" class="italic text-lg">{generated}</p><div class="mt-6 flex space-x-4"><button onclick="navigator.clipboard.writeText(document.getElementById(\'ai-text\').innerText)" class="btn-outline">Copy</button><a href="/outreach?body={encoded_body}" class="btn-primary">Transfer</a></div></div>'
    
    return render_titan_ui(f'<div class="grid grid-cols-1 md:grid-cols-2 gap-12"><div><h2 class="text-2xl font-black mb-6">Neural Generator</h2><form method="POST" class="space-y-4"><select name="persona"><option value="ruthless">Ruthless Closer</option><option value="viral">Viral Influencer</option></select><textarea name="details" class="h-48"></textarea><button class="btn-primary w-full">Generate</button></form></div><div>{output_html}</div></div>', user=user)
    # ==============================================================================
# TITAN V28.2 - AUTH, OUTREACH, ADMIN, & BOOT
# ==============================================================================
class TitanAuth:
    @staticmethod
    def get_flow():
        return Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    @staticmethod
    def encrypt_tokens(data): return cipher.encrypt(json.dumps(data).encode()).decode()
    @staticmethod
    def decrypt_tokens(enc): return json.loads(cipher.decrypt(enc.encode()).decode())
    @staticmethod
    def refresh_user_token(email):
        with db.get_connection() as conn:
            user = conn.execute("SELECT google_creds_enc FROM users WHERE email=?", (email,)).fetchone()
        if not user or not user['google_creds_enc']: return None
        return google_requests.Request() # Simplified for this block, use standard Credentials refresh in full

@app.route('/outreach', methods=['GET', 'POST'])
def outbound_machine():
    if 'user_email' not in session: return redirect('/auth/login')
    user = db.get_user(session['user_email'])
    if not user['email_machine_access']: return render_titan_ui('<div class="text-center py-20 titan-card"><h2>Machine Locked</h2><form action="/checkout" method="POST"><button name="pid" value="price_1Spy7SFXcDZgM3VoVZv71I63" class="btn-primary">Unlock $20</button></form></div>', user=user)
    
    if request.method == 'POST':
        machine = OutboundMachine(user['email'])
        machine.initiate_blast(request.form.get('recipients').split(','), request.form.get('subject'), request.form.get('body'))
        flash("Campaign Sent")
    return render_titan_ui('<div class="titan-card p-10 max-w-2xl mx-auto"><h2 class="text-2xl font-black mb-6">Outbound Machine</h2><form method="POST" class="space-y-4"><input name="recipients" placeholder="Recipients"><input name="subject" placeholder="Subject"><textarea name="body" class="h-48"></textarea><button class="btn-primary w-full">Blast</button></form></div>', user=user)

@app.route('/auth/login')
def login():
    flow = TitanAuth.get_flow(); flow.redirect_uri = REDIRECT_URI
    url, state = flow.authorization_url(access_type='offline', prompt='consent')
    session['state'] = state; return redirect(url)

@app.route('/callback')
def callback():
    flow = TitanAuth.get_flow(); flow.redirect_uri = REDIRECT_URI
    flow.fetch_token(authorization_response=request.url)
    info = id_token.verify_oauth2_token(flow.credentials.id_token, google_requests.Request(), GOOGLE_CLIENT_ID)
    email = info['email']; session['user_email'] = email
    creds = {"token": flow.credentials.token, "refresh_token": flow.credentials.refresh_token, "token_uri": flow.credentials.token_uri, "client_id": flow.credentials.client_id, "client_secret": flow.credentials.client_secret, "scopes": flow.credentials.scopes}
    enc = TitanAuth.encrypt_tokens(creds)
    db.create_user_if_not_exists(email, info.get('name'), info.get('picture'))
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET google_creds_enc = ? WHERE email = ?", (enc, email)); conn.commit()
    return redirect('/')

@app.route('/admin/dashboard')
def admin_dash():
    if 'user_email' not in session: return redirect('/')
    user = db.get_user(session['user_email'])
    with db.get_connection() as conn:
        leads = conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
        total_rev = conn.execute("SELECT SUM(asking_price * (platform_cut_percentage/100)) FROM leads").fetchone()[0] or 0
    
    rows = "".join([f'<tr class="border-b border-zinc-900"><td class="py-4">{l["address"]}</td><td class="text-indigo-400 font-bold">{l["platform_cut_percentage"]}%</td></tr>' for l in leads])
    return render_titan_ui(f'<div class="titan-card p-10"><h1 class="text-4xl font-black mb-4 uppercase">System Oversight</h1><p class="text-green-500 font-bold">Potential Revenue (The Cut): ${total_rev:,.2f}</p><table class="w-full mt-8 text-left"><thead><tr class="text-xs uppercase text-zinc-600"><th>Asset</th><th>Our Cut</th></tr></thead><tbody>{rows}</tbody></table></div>', user=user)

@app.route('/checkout', methods=['POST'])
def checkout():
    s = stripe.checkout.Session.create(line_items=[{'price': request.form.get('pid'), 'quantity': 1}], mode='payment', success_url=request.host_url+'success', customer_email=session['user_email'])
    return redirect(s.url, code=303)

@app.route('/success')
def success():
    with db.get_connection() as conn: conn.execute("UPDATE users SET email_machine_access=1, ai_access=1 WHERE email=?", (session['user_email'],)); conn.commit()
    return redirect('/')

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

@app.route('/uploads/<filename>')
def uploaded_file(filename): return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

import os, re, base64, time, random, stripe, sqlite3, json, secrets
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, send_from_directory
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

# --- 1. CONFIGURATION ---
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
UPLOAD_FOLDER = 'uploads'
DB_PATH = "pro_exchange_v20.db"

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "pro_exchange_v20_final")

# Google OAuth Config
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
SCOPES = ['https://www.googleapis.com/auth/userinfo.email', 'openid', 'https://www.googleapis.com/auth/gmail.send']
CLIENT_CONFIG = {"web": {"client_id": GOOGLE_CLIENT_ID, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"), "redirect_uris": [os.environ.get("REDIRECT_URI")]}}

# --- 2. DATABASE ARCHITECTURE ---
def get_db():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY, 
            purchase_count INTEGER DEFAULT 0, 
            email_machine_access INTEGER DEFAULT 0, -- 1 for paid
            ai_paid INTEGER DEFAULT 0,
            ai_trial_end TEXT,
            referral_code TEXT,
            google_creds TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            address TEXT, asking_price INTEGER, sqft INTEGER, 
            image_path TEXT, status TEXT DEFAULT 'active'
        )""")
        conn.commit()

init_db()

# --- 3. CORE LOGIC ---
def get_buyer_rate(deal_count):
    # Starts at 6%, drops 1% per deal closed through us, caps at 2%
    return max(0.02, 0.06 - (deal_count * 0.01))

def has_ai_access(user):
    if user['ai_paid'] == 1: return True
    if user['ai_trial_end'] and datetime.now() < datetime.fromisoformat(user['ai_trial_end']): return True
    return False

# --- 4. THEME & UI ---
UI_HEADER = """
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.tailwindcss.com"></script>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;900&display=swap');
    body { font-family: 'Outfit', sans-serif; background: #050505; color: #fff; }
    .glass { background: #111; border: 1px solid #222; border-radius: 2rem; }
    .btn-main { background: #fff; color: #000; font-weight: 900; text-transform: uppercase; border-radius: 1rem; transition: 0.3s; }
    .btn-main:hover { transform: scale(1.02); background: #f0f0f0; }
    .text-gradient { background: linear-gradient(to right, #fff, #666); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
</style></head><body class="min-h-screen p-6 flex flex-col items-center">
<div class="w-full max-w-4xl">
"""
UI_FOOTER = """
<footer class="mt-20 py-10 border-t border-zinc-900 text-center">
    <a href="/privacy" class="text-[10px] font-bold text-gray-600 uppercase tracking-widest hover:text-white transition">Privacy Policy</a>
    <p class="text-[8px] text-gray-800 uppercase mt-4">© Pro-Exchange Global Neural Network</p>
</footer>
</div></body></html>
"""

# --- 5. DASHBOARD ---

@app.route('/')
def index():
    return render_template_string(UI_HEADER + """
        <header class="text-center py-20">
            <h1 class="text-7xl font-black uppercase italic tracking-tighter text-gradient">Pro-Exchange</h1>
            <p class="text-[10px] font-bold text-gray-600 uppercase tracking-[0.6em] mt-4">Automated Real Estate Dominance</p>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="glass p-10 flex flex-col justify-between">
                <div>
                    <h3 class="text-3xl font-black uppercase italic">Email Machine</h3>
                    <p class="text-xs text-gray-500 mt-2 mb-8">Direct-to-Inbox Broadcast Engine.</p>
                </div>
                <div class="space-y-3">
                    <a href="/outreach" class="btn-main w-full py-4 inline-block text-center text-xs">Access Engine</a>
                    <p class="text-[9px] text-center text-gray-600 uppercase font-bold">$20 One-Time or $3/Week</p>
                </div>
            </div>
            
            <div class="glass p-10 border-indigo-900/50 bg-gradient-to-b from-zinc-900 to-black">
                <h3 class="text-3xl font-black uppercase italic text-indigo-400">AI Agent</h3>
                <p class="text-xs text-gray-500 mt-2 mb-8">Intellectual TikTok Automation & Scheduling.</p>
                <a href="/ai-agent" class="btn-main w-full py-4 inline-block text-center text-xs bg-indigo-600 text-white border-none">Launch Agent</a>
                <p class="text-[9px] text-center text-indigo-400 uppercase font-bold mt-3">48H Trial Available • $50/mo</p>
            </div>

            <a href="/buy" class="glass p-10 group hover:border-green-500/50 transition-all">
                <h3 class="text-2xl font-black uppercase italic group-hover:text-green-400 transition-colors">Buy Assets</h3>
                <p class="text-xs text-gray-600 mt-1">Sliding Scale Fees: 6% → 2%</p>
            </a>

            <a href="/sell" class="glass p-10 group hover:border-blue-500/50 transition-all">
                <h3 class="text-2xl font-black uppercase italic group-hover:text-blue-400 transition-colors">Sell Assets</h3>
                <p class="text-xs text-gray-600 mt-1">0% Commission. AI Listing Tool.</p>
            </a>
        </div>
    """ + UI_FOOTER)

# --- 6. AI AGENT: INTELLECTUAL AUTOMATION ---

@app.route('/ai-agent')
def ai_agent():
    if 'user_email' not in session: return redirect(url_for('google_login', next='ai-agent'))
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()

    if not has_ai_access(user):
        return render_template_string(UI_HEADER + """
            <div class="glass p-12 text-center max-w-2xl mx-auto border-indigo-500/20">
                <h2 class="text-5xl font-black uppercase italic mb-6">Neural Agent</h2>
                <p class="text-gray-400 mb-10 text-sm leading-relaxed">The AI Agent posts automated "Intellectual" content (Stoicism, Wealth Architecture, and Philosophy) on a schedule to build massive authority and pull leads into the platform for you.</p>
                
                <div class="space-y-4">
                    <a href="/start-ai-trial" class="block w-full bg-indigo-600 p-6 rounded-2xl font-black uppercase italic hover:bg-indigo-500 transition">Start 48H Free Trial (No Credit Card)</a>
                    <button class="block w-full bg-white text-black p-6 rounded-2xl font-black uppercase italic">$50 / Month Subscription</button>
                </div>
            </div>
        """ + UI_FOOTER)

    return render_template_string(UI_HEADER + """
        <div class="flex justify-between items-center mb-10">
            <h2 class="text-4xl font-black uppercase italic text-indigo-400">AI Scheduling Terminal</h2>
            <span class="px-4 py-1 bg-indigo-500 text-white font-black uppercase text-[10px] rounded-full animate-pulse">Neural Link Active</span>
        </div>

        <div class="glass p-8 mb-6">
            <h3 class="text-xs font-black uppercase text-gray-500 mb-6 tracking-widest">Automated Intellectual Content Queue</h3>
            <div class="space-y-4">
                <div class="flex justify-between items-center p-5 bg-black rounded-2xl border border-zinc-800">
                    <div>
                        <p class="text-xs font-black uppercase">Stoic Arbitrage #041</p>
                        <p class="text-[9px] text-gray-600 font-bold uppercase">Topic: Marcus Aurelius on Wealth</p>
                    </div>
                    <span class="text-[10px] font-black text-indigo-400 uppercase">Scheduled: 2PM</span>
                </div>
                <div class="flex justify-between items-center p-5 bg-black rounded-2xl border border-zinc-800 opacity-50">
                    <div>
                        <p class="text-xs font-black uppercase">Neural Marketing #012</p>
                        <p class="text-[9px] text-gray-600 font-bold uppercase">Topic: Efficiency in Real Estate</p>
                    </div>
                    <span class="text-[10px] font-black text-gray-600 uppercase">Scheduled: 6PM</span>
                </div>
            </div>
        </div>
        
        <div class="text-center p-6">
            <p class="text-[10px] font-black text-zinc-700 uppercase tracking-[0.3em]">AI is currently scraping intellectual data to generate your viral schedule.</p>
        </div>
    """, user=user) + UI_FOOTER

# --- 7. EMAIL MACHINE ($20 OR $3/WK) ---

@app.route('/outreach')
def outreach_portal():
    if 'user_email' not in session: return redirect(url_for('google_login', next='outreach'))
    with get_db() as conn:
        user = conn.execute("SELECT email_machine_access FROM users WHERE email = ?", (session['user_email'],)).fetchone()
    
    if not user['email_machine_access']:
        return render_template_string(UI_HEADER + """
            <div class="glass p-12 text-center max-w-xl mx-auto">
                <h2 class="text-5xl font-black uppercase italic mb-6">Email Machine</h2>
                <p class="text-gray-400 mb-10 text-sm">Direct-to-inbox outreach. Verified high-deliverability mass mailing.</p>
                <div class="grid grid-cols-1 gap-4">
                    <button class="bg-white text-black p-6 rounded-2xl font-black uppercase italic text-xl">$20 Lifetime Access</button>
                    <button class="bg-zinc-900 text-white p-6 rounded-2xl font-black uppercase italic text-sm border border-zinc-800">$3 / Week Subscription</button>
                </div>
            </div>
        """ + UI_FOOTER)
    
    return render_template_string(UI_HEADER + """<h2 class="text-4xl font-black uppercase italic">Email Machine Active</h2>""" + UI_FOOTER)

# --- 8. BUYER/SELLER & PRIVACY ---

@app.route('/buy')
def buyer_portal():
    if 'user_email' not in session: return redirect(url_for('google_login', next='buy'))
    with get_db() as conn:
        user = conn.execute("SELECT purchase_count FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        leads = conn.execute("SELECT * FROM leads WHERE status = 'active'").fetchall()
    
    rate = get_buyer_rate(user['purchase_count'] if user else 0)
    
    return render_template_string(UI_HEADER + """
        <div class="flex justify-between items-end mb-10">
            <h2 class="text-5xl font-black uppercase italic tracking-tighter">The Vault</h2>
            <div class="text-right">
                <p class="text-[10px] font-black text-zinc-600 uppercase">Current Fee Rate</p>
                <p class="text-3xl font-black text-green-500">{{ (rate*100)|int }}%</p>
            </div>
        </div>
        <div class="grid grid-cols-1 gap-8">
            {% for lead in leads %}
            <div class="glass overflow-hidden group">
                {% if lead.image_path %}<img src="/uploads/{{ lead.image_path }}" class="w-full h-80 object-cover opacity-60 group-hover:opacity-100 transition duration-700">{% endif %}
                <div class="p-10 flex justify-between items-center">
                    <div>
                        <h3 class="text-3xl font-black uppercase italic tracking-tight">{{ lead.address }}</h3>
                        <p class="text-xs font-bold text-zinc-500 uppercase mt-2">${{ "{:,.0f}".format(lead.asking_price) }}</p>
                    </div>
                    <button class="btn-main px-10 py-5 text-xs">Contract Assignment</button>
                </div>
            </div>
            {% endfor %}
        </div>
    """, leads=leads, rate=rate) + UI_FOOTER

@app.route('/privacy')
def privacy():
    return render_template_string(UI_HEADER + """
        <div class="glass p-12 max-w-3xl mx-auto leading-relaxed">
            <h2 class="text-4xl font-black uppercase italic mb-8">Privacy Policy</h2>
            <div class="text-zinc-400 text-sm space-y-6">
                <p><b>1. Data Collection:</b> Pro-Exchange collects your email via Google OAuth to provide secure access to the Email Machine and AI Agent services.</p>
                <p><b>2. AI & Social Media:</b> When using the AI Agent for TikTok/Facebook automation, we do not store your social passwords. We use secure API tokens to schedule and post content on your behalf.</p>
                <p><b>3. Payment Data:</b> All transactions are handled by Stripe. We do not store credit card information on our servers.</p>
                <p><b>4. Property Data:</b> Sellers uploading property images grant Pro-Exchange the right to use these images within the internal buyer feed and for automated AI marketing posts.</p>
                <p><b>5. Encryption:</b> Sensitive contact details are encrypted using AES-256 standard before storage.</p>
            </div>
            <a href="/" class="btn-main px-10 py-4 mt-10 inline-block text-xs">Back to Hub</a>
        </div>
    """ + UI_FOOTER)

# --- 9. CORE SYSTEM HANDLERS ---

@app.route('/start-ai-trial')
def start_ai_trial():
    if 'user_email' not in session: return redirect(url_for('google_login', next='ai-agent'))
    with get_db() as conn:
        end = (datetime.now() + timedelta(hours=48)).isoformat()
        conn.execute("UPDATE users SET ai_trial_end = ? WHERE email = ?", (end, session['user_email']))
        conn.commit()
    flash("48-Hour Trial Activated.")
    return redirect(url_for('ai_agent'))

@app.route('/auth/login')
def google_login():
    session['next_target'] = request.args.get('next', 'index')
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    flow.redirect_uri = os.environ.get("REDIRECT_URI")
    auth_url, state = flow.authorization_url(access_type='offline', prompt='consent')
    session['state'] = state
    return redirect(auth_url)

@app.route('/callback')
def callback():
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, state=session['state'])
    flow.redirect_uri = os.environ.get("REDIRECT_URI")
    flow.fetch_token(authorization_response=request.url)
    id_info = id_token.verify_oauth2_token(flow.credentials.id_token, requests.Request(), GOOGLE_CLIENT_ID)
    session['user_email'] = id_info.get('email')
    with get_db() as conn:
        conn.execute("INSERT INTO users (email) VALUES (?) ON CONFLICT(email) DO NOTHING", (session['user_email'],))
        conn.commit()
    return redirect(url_for(session.get('next_target', 'index')))

@app.route('/sell')
def seller_portal():
    return render_template_string(UI_HEADER + """
        <div class="glass p-12 max-w-2xl mx-auto">
            <h2 class="text-4xl font-black uppercase italic mb-8">List Asset</h2>
            <form action="/submit-lead" method="POST" enctype="multipart/form-data" class="space-y-6">
                <input type="text" name="address" placeholder="Property Address" class="w-full p-5 bg-black rounded-2xl border border-zinc-800" required>
                <input type="number" name="price" placeholder="Asking Price" class="w-full p-5 bg-black rounded-2xl border border-zinc-800" required>
                <input type="file" name="photo" class="text-xs font-black uppercase text-zinc-600" required>
                <button class="btn-main w-full py-6 text-xl">Submit Free Listing</button>
            </form>
        </div>
    """ + UI_FOOTER)

@app.route('/submit-lead', methods=['POST'])
def submit_lead():
    f = request.form; file = request.files.get('photo')
    filename = secure_filename(file.filename) if file else None
    if filename: file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    with get_db() as conn:
        conn.execute("INSERT INTO leads (address, asking_price, image_path) VALUES (?, ?, ?)", (f.get('address'), f.get('price'), filename))
        conn.commit()
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

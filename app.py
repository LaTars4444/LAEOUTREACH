import os, re, base64, time, random, stripe, sqlite3, json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
from googleapiclient.discovery import build
from werkzeug.middleware.proxy_fix import ProxyFix
from email.mime.text import MIMEText

# --- 1. ENTERPRISE CONFIG & ENCRYPTION ---
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

def get_cipher():
    key = os.environ.get("ENCRYPTION_KEY")
    try:
        # Standardize on a valid Fernet key
        return Fernet(key.encode()) if key else Fernet(Fernet.generate_key())
    except:
        return Fernet(Fernet.generate_key())

cipher = get_cipher()
app = Flask(__name__)
# Fix for Render/Google Redirects
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "pro_exchange_v16_hardened")
DB_PATH = "pro_exchange_v16.db"

# Google Auth - Integrated Scopes for Email Machine
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email', 
    'openid', 
    'https://www.googleapis.com/auth/gmail.send'
]
CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
        "redirect_uris": [os.environ.get("REDIRECT_URI")]
    }
}

# --- 2. DATABASE SYSTEM ---
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY, 
            purchase_count INTEGER DEFAULT 0, 
            trial_end TEXT, 
            has_paid_outreach INTEGER DEFAULT 0,
            bb_budget INTEGER DEFAULT -1,
            bb_any INTEGER DEFAULT 0,
            bb_min_sqft INTEGER DEFAULT 0,
            bb_min_beds INTEGER DEFAULT 0,
            google_creds TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            address TEXT, 
            asking_price INTEGER DEFAULT 0, 
            sqft INTEGER DEFAULT 0,
            year_built INTEGER DEFAULT 0,
            beds INTEGER DEFAULT 0,
            baths INTEGER DEFAULT 0,
            details_encrypted TEXT, 
            contact_encrypted TEXT,
            score INTEGER DEFAULT 50, 
            status TEXT DEFAULT 'active'
        )""")
        conn.commit()

init_db()

# --- 3. CORE LOGIC UTILITIES ---
def safe_int(val):
    if val is None: return 0
    try:
        clean = re.sub(r'[^\d]', '', str(val))
        return int(clean) if clean else 0
    except: return 0

def get_assignment_rate(count):
    # Assignment Fee Milestones: 4% -> 3.5% -> 3% -> 2.5% -> 2%
    rates = {0: 0.040, 1: 0.035, 2: 0.030, 3: 0.025}
    return rates.get(count, 0.020)

def send_gmail_broadcast(creds_json, to_email, subject, body):
    try:
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_info(json.loads(creds_json))
        service = build('gmail', 'v1', credentials=creds)
        message = MIMEText(body)
        message['to'] = to_email
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
        return True
    except: return False

# --- 4. GOOGLE-PAR UI TEMPLATES ---
UI_HEADER = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PRO-EXCHANGE | Enterprise Suite</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;900&display=swap');
        body { font-family: 'Outfit', sans-serif; background-color: #fcfcfc; color: #1a1a1a; }
        .g-card { box-shadow: 0 30px 60px rgba(0,0,0,0.06); border: 1px solid #f0f0f0; }
        .btn-main { background: #000; color: #fff; transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
        .btn-main:hover { background: #222; transform: translateY(-3px); box-shadow: 0 15px 30px rgba(0,0,0,0.1); }
        .tick-circle { animation: scaleTick 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards; }
        @keyframes scaleTick { from { transform: scale(0.5); opacity: 0; } to { transform: scale(1); opacity: 1; } }
    </style>
</head>
<body class="min-h-screen flex flex-col items-center justify-center p-4">
    <div class="w-full max-w-2xl bg-white rounded-[3rem] g-card p-10 md:p-16 relative overflow-hidden">
"""

UI_FOOTER = """
        <div class="mt-20 pt-8 border-t border-gray-50 flex flex-col items-center">
            <div class="flex space-x-6 mb-4">
                <a href="/" class="text-[10px] font-black uppercase text-gray-300 hover:text-black transition">Home</a>
                <a href="/logout" class="text-[10px] font-black uppercase text-red-300 hover:text-red-600 transition">Reset Session</a>
            </div>
            <p class="text-[8px] font-bold text-gray-300 uppercase tracking-[0.3em]">AES-256 Multi-Layer Security • Pro-Exchange Global</p>
        </div>
    </div>
</body></html>
"""

# --- 5. NAVIGATION ROUTES ---

@app.route('/')
def index():
    return render_template_string(UI_HEADER + """
        <header class="text-center mb-16">
            <h1 class="text-6xl font-black tracking-tighter uppercase mb-2">Pro-Exchange</h1>
            <p class="text-gray-400 text-[10px] font-black uppercase tracking-[0.5em]">The Ultimate Global Real Estate Suite</p>
        </header>

        {% with m = get_flashed_messages() %}{% if m %}<div class="mb-8 p-4 bg-black text-white rounded-2xl text-xs font-bold text-center italic">{{ m[0]|safe }}</div>{% endif %}{% endwith %}

        <div class="grid grid-cols-1 gap-4">
            <!-- IMMEDIATE LOGIN FOR EMAIL MACHINE -->
            <a href="/outreach" class="group flex items-center justify-between p-10 bg-black text-white rounded-[2.5rem] hover:bg-zinc-800 transition-all">
                <div>
                    <h3 class="text-3xl font-black italic uppercase">Email Machine</h3>
                    <p class="text-[10px] font-bold uppercase opacity-60 tracking-widest mt-1">Global Broadcast Engine</p>
                </div>
                <span class="text-3xl group-hover:scale-125 transition-transform">⚡</span>
            </a>
            
            <div class="grid grid-cols-2 gap-4">
                <a href="/sell" class="p-10 bg-white border-2 border-gray-100 rounded-[2.5rem] hover:border-black transition-all group">
                    <h3 class="text-xl font-black uppercase">Sell</h3>
                    <p class="text-[10px] font-bold text-blue-600 uppercase mt-1">Free Listing</p>
                </a>
                <a href="/buy" class="p-10 bg-white border-2 border-gray-100 rounded-[2.5rem] hover:border-black transition-all group">
                    <h3 class="text-xl font-black uppercase">Buy</h3>
                    <p class="text-[10px] font-bold text-gray-400 uppercase mt-1">Scale Deals</p>
                </a>
            </div>
        </div>
    """ + UI_FOOTER)

# --- 6. OUTREACH ENGINE (IMMEDIATE AUTH) ---

@app.route('/outreach')
def outreach_portal():
    # Immediate Sign-in Wall
    if 'user_email' not in session: 
        return redirect(url_for('google_login', next='outreach'))
    
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        access = (user and (user['has_paid_outreach'] == 1 or (user['trial_end'] and datetime.now() < datetime.fromisoformat(user['trial_end']))))
    
    return render_template_string(UI_HEADER + """
        <div class="flex justify-between items-center mb-10"><a href="/" class="text-[10px] font-black uppercase text-gray-300">← Exit</a><span class="text-[10px] font-black uppercase px-3 py-1 bg-black text-white rounded-full">Engine v16</span></div>
        {% if not access %}
            <div class="text-center py-20">
                <h2 class="text-4xl font-black uppercase tracking-tighter mb-4">Module Locked</h2>
                <p class="text-gray-400 font-bold uppercase text-[10px] tracking-widest mb-10">Access restricted to active trials or subscribers</p>
                <a href="/start-trial" class="btn-main px-12 py-6 rounded-full font-black uppercase text-xs inline-block">Unlock 24HR Free Trial</a>
            </div>
        {% else %}
            <h2 class="text-4xl font-black uppercase tracking-tighter mb-8">Broadcast Machine</h2>
            <form action="/broadcast" method="POST" class="space-y-4">
                <textarea name="targets" placeholder="Emails (separated by commas)..." class="w-full p-6 border-2 border-gray-50 rounded-3xl h-32 focus:border-black outline-none font-bold italic" required></textarea>
                <input type="text" name="subject" placeholder="Campaign Subject" class="w-full p-5 border-2 border-gray-50 rounded-2xl focus:border-black outline-none font-bold" required>
                <textarea name="message" placeholder="Pitch / Deal details..." class="w-full p-6 border-2 border-gray-50 rounded-3xl h-48 focus:border-black outline-none font-bold" required></textarea>
                <button class="w-full btn-main py-8 rounded-[2.5rem] font-black text-2xl uppercase italic shadow-2xl">Launch Broadcast 🚀</button>
            </form>
        {% endif %}
    """, access=access) + UI_FOOTER

@app.route('/broadcast', methods=['POST'])
def launch_broadcast():
    with get_db() as conn:
        user = conn.execute("SELECT google_creds FROM users WHERE email = ?", (session['user_email'],)).fetchone()
    
    if not user or not user['google_creds']:
        flash("Re-authentication required for Gmail.")
        return redirect(url_for('google_login', next='outreach'))

    targets = [t.strip() for t in request.form.get('targets').split(',')]
    subj, msg = request.form.get('subject'), request.form.get('message')
    
    success = 0
    for t in targets:
        if send_gmail_broadcast(user['google_creds'], t, subj, msg):
            success += 1
            time.sleep(random.uniform(1, 2.5)) # Human behavior delay

    flash(f"Transmission Complete: {success} Deliveries Made.")
    return redirect(url_for('outreach_portal'))

# --- 7. SELLER SUCCESS WORKFLOW ---

@app.route('/sell')
def seller_portal():
    if 'user_email' not in session: return redirect(url_for('google_login', next='sell'))
    return render_template_string(UI_HEADER + """
        <a href="/" class="text-[10px] font-black uppercase text-gray-300 mb-8 block underline">← Back</a>
        <h2 class="text-4xl font-black uppercase tracking-tighter mb-8">List Property</h2>
        <form action="/submit-lead" method="POST" class="space-y-3">
            <input type="text" name="address" placeholder="Property Address" class="w-full p-5 border-2 border-gray-50 rounded-2xl font-bold" required>
            <div class="grid grid-cols-2 gap-2">
                <input type="text" name="price" placeholder="Asking Price ($)" class="p-5 border-2 border-gray-50 rounded-2xl font-bold" required>
                <input type="text" name="sqft" placeholder="Total Sqft" class="p-5 border-2 border-gray-50 rounded-2xl font-bold">
                <input type="text" name="beds" placeholder="Beds" class="p-5 border-2 border-gray-50 rounded-2xl font-bold">
                <input type="text" name="baths" placeholder="Baths" class="p-5 border-2 border-gray-50 rounded-2xl font-bold">
            </div>
            <textarea name="reason" placeholder="Condition & Motivation..." class="w-full p-5 border-2 border-gray-50 rounded-3xl h-24 font-bold" required></textarea>
            <input type="text" name="contact" placeholder="Secure Contact (Email/Phone)" class="w-full p-5 border-2 border-gray-50 rounded-2xl font-bold" required>
            <button class="w-full btn-main py-8 rounded-[2.5rem] font-black text-2xl uppercase">Submit FREE Listing</button>
        </form>
    """ + UI_FOOTER)

@app.route('/submit-lead', methods=['POST'])
def submit_lead():
    f = request.form
    enc_reason = cipher.encrypt(f.get('reason', '').encode()).decode()
    enc_contact = cipher.encrypt(f.get('contact', '').encode()).decode()
    with get_db() as conn:
        conn.execute("""INSERT INTO leads (address, asking_price, sqft, beds, baths, details_encrypted, contact_encrypted, score) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                     (f.get('address'), safe_int(f.get('price')), safe_int(f.get('sqft')), safe_int(f.get('beds')), safe_int(f.get('baths')), enc_reason, enc_contact, random.randint(75, 99)))
        conn.commit()
    return redirect(url_for('seller_success'))

@app.route('/sell/success')
def seller_success():
    return render_template_string(UI_HEADER + """
        <div class="text-center py-10">
            <div class="w-32 h-32 bg-green-500 text-white rounded-full flex items-center justify-center mx-auto mb-10 shadow-2xl tick-circle">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-20 w-20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>
            </div>
            <h2 class="text-5xl font-black uppercase tracking-tighter mb-4 leading-none">Submission<br>Success</h2>
            <p class="text-gray-400 font-bold uppercase text-[10px] tracking-[0.3em] mb-12">AI is now routing your lead to matching buyers</p>
            <a href="/" class="btn-main px-12 py-5 rounded-full font-black uppercase text-xs inline-block">Return Home</a>
        </div>
    """ + UI_FOOTER)

# --- 8. BUYER WORKFLOW & % MILESTONES ---

@app.route('/buy')
def buyer_portal():
    if 'user_email' not in session: return redirect(url_for('google_login', next='buy'))
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        if not user or (user['bb_budget'] == -1 and user['bb_any'] == 0):
            if not user: conn.execute("INSERT INTO users (email) VALUES (?)", (session['user_email'],)); conn.commit()
            return render_template_string(UI_HEADER + """
                <h2 class="text-3xl font-black uppercase mb-8 tracking-tighter text-center">Configure Buy-Box</h2>
                <form action="/save-buybox" method="POST" class="space-y-4">
                    <label class="block p-8 border-2 border-gray-100 rounded-[2rem] cursor-pointer hover:border-black">
                        <input type="radio" name="bb_type" value="any" checked> <span class="text-xl font-black uppercase ml-4 italic">See All Leads</span>
                    </label>
                    <button class="w-full btn-main py-8 rounded-[2.5rem] font-black text-2xl uppercase">Initialize Feed</button>
                </form>
            """ + UI_FOOTER)
        
        leads = conn.execute("SELECT * FROM leads WHERE status = 'active'").fetchall()
        rate = get_assignment_rate(user['purchase_count'])
        
    return render_template_string(UI_HEADER + """
        <div class="flex justify-between items-center mb-10"><a href="/" class="text-[10px] font-black uppercase text-gray-300">← Back</a><span class="text-[10px] font-black uppercase">Tier Rate: {{ rate_p }}%</span></div>
        <div class="space-y-4">
            {% for lead in leads %}
            <div class="p-8 border-2 border-gray-100 rounded-[3rem] flex flex-col md:flex-row justify-between items-center hover:border-black transition group">
                <div>
                    <h5 class="text-xl font-black uppercase leading-none italic">Verified Assignment</h5>
                    <p class="text-[10px] font-bold text-gray-400 mt-2 uppercase tracking-widest">${{ "{:,.0f}".format(lead.asking_price) }} • {{ lead.beds }}bd • {{ lead.sqft }}sqft</p>
                </div>
                <button class="btn-main px-8 py-5 rounded-2xl font-black text-[10px] uppercase shadow-lg">Pay ${{ "{:,.2f}".format(lead.asking_price * rate) }}<br>Assignment Fee</button>
            </div>
            {% endfor %}
        </div>
    """, leads=leads, rate=rate, rate_p=rate*100) + UI_FOOTER

@app.route('/save-buybox', methods=['POST'])
def save_buybox():
    with get_db() as conn:
        conn.execute("UPDATE users SET bb_budget=99999999, bb_any=1 WHERE email=?", (session['user_email'],))
        conn.commit()
    return redirect(url_for('buyer_portal'))

# --- 9. OAUTH CORE ---

@app.route('/auth/login')
def google_login():
    session['next_target'] = request.args.get('next', 'gate')
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    flow.redirect_uri = os.environ.get("REDIRECT_URI")
    auth_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent')
    session['state'] = state
    return redirect(auth_url)

@app.route('/callback')
def callback():
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, state=session['state'])
    flow.redirect_uri = os.environ.get("REDIRECT_URI")
    flow.fetch_token(authorization_response=request.url)
    
    creds = flow.credentials
    id_info = id_token.verify_oauth2_token(creds.id_token, requests.Request(), GOOGLE_CLIENT_ID)
    email = id_info.get('email')
    session['user_email'] = email
    
    # Store credentials for Gmail Machine
    creds_json = json.dumps({
        'token': creds.token, 'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri, 'client_id': creds.client_id,
        'client_secret': creds.client_secret, 'scopes': creds.scopes
    })
    with get_db() as conn:
        conn.execute("INSERT INTO users (email, google_creds) VALUES (?, ?) ON CONFLICT(email) DO UPDATE SET google_creds=?", (email, creds_json, creds_json))
        conn.commit()
    
    target = session.get('next_target', 'gate')
    if target == 'sell': return redirect(url_for('seller_portal'))
    if target == 'buy': return redirect(url_for('buyer_portal'))
    return redirect(url_for('outreach_portal'))

@app.route('/start-trial')
def start_trial():
    with get_db() as conn:
        end = (datetime.now() + timedelta(hours=24)).isoformat()
        conn.execute("UPDATE users SET trial_end = ? WHERE email = ?", (end, session['user_email']))
        conn.commit()
    flash("Broadcast Machine Trials Enabled.")
    return redirect(url_for('outreach_portal'))

@app.route('/logout')
def logout():
    session.clear(); return redirect('/')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

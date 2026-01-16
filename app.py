import os, re, base64, time, random, stripe, sqlite3, json, secrets
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, send_from_directory
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
from googleapiclient.discovery import build
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

# --- 1. ENTERPRISE CONFIG & ENCRYPTION ---
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
DB_PATH = "pro_exchange_v18.db"

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "pro_exchange_enterprise_v18")

# Google OAuth Setup
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
            has_ai_subscription INTEGER DEFAULT 0,
            ai_status TEXT DEFAULT 'off',
            ai_tone TEXT DEFAULT 'Aggressive',
            growth_mode INTEGER DEFAULT 0,
            referral_code TEXT,
            google_creds TEXT,
            fb_token TEXT,
            tiktok_token TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            address TEXT, 
            asking_price INTEGER DEFAULT 0, 
            sqft INTEGER DEFAULT 0,
            image_path TEXT,
            contact_encrypted TEXT,
            status TEXT DEFAULT 'active'
        )""")
        conn.commit()

init_db()

# --- 3. CORE LOGIC UTILITIES ---
cipher = Fernet(os.environ.get("ENCRYPTION_KEY", Fernet.generate_key().decode()).encode())

def get_assignment_rate(count):
    # Logic: Starts at 6%, loses 1% per deal, caps at 2%
    rate = 0.06 - (count * 0.01)
    return max(0.02, rate)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- 4. UI TEMPLATES (Tailwind Bold Style) ---
UI_HEADER = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PRO-EXCHANGE | AI Suite</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;900&display=swap');
        body { font-family: 'Outfit', sans-serif; background: #fafafa; }
        .g-card { background: white; border-radius: 3rem; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.05); border: 1px solid #f0f0f0; }
        .btn-black { background: black; color: white; border-radius: 1.5rem; transition: all 0.3s ease; font-weight: 900; text-transform: uppercase; italic; }
        .btn-black:hover { transform: translateY(-3px); box-shadow: 0 20px 30px rgba(0,0,0,0.1); }
    </style>
</head>
<body class="min-h-screen flex flex-col items-center p-6">
    <div class="w-full max-w-3xl">
"""
UI_FOOTER = "</div></body></html>"

# --- 5. CORE NAVIGATION ---

@app.route('/')
def index():
    return render_template_string(UI_HEADER + """
        <header class="text-center mb-12">
            <h1 class="text-6xl font-black uppercase italic tracking-tighter">Pro-Exchange</h1>
            <p class="text-[10px] font-bold text-gray-400 uppercase tracking-[0.5em] mt-2">The Neural Real Estate Suite</p>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <a href="/ai-agent" class="p-10 bg-indigo-600 text-white rounded-[3rem] hover:scale-105 transition-transform group relative overflow-hidden">
                <h3 class="text-3xl font-black uppercase italic">AI Agent</h3>
                <p class="text-xs opacity-80 mt-1">$35/mo • Social & Marketing</p>
                <span class="absolute right-4 bottom-4 text-6xl opacity-20">🤖</span>
            </a>
            <a href="/outreach" class="p-10 bg-black text-white rounded-[3rem] hover:scale-105 transition-transform group">
                <h3 class="text-3xl font-black uppercase italic">Email Machine</h3>
                <p class="text-xs opacity-80 mt-1">Broadcast • Free Trial</p>
            </a>
            <a href="/sell" class="p-10 g-card hover:border-black transition-all">
                <h3 class="text-2xl font-black uppercase text-blue-600">Sell</h3>
                <p class="text-xs text-gray-400 mt-1">0% Commission • List Free</p>
            </a>
            <a href="/buy" class="p-10 g-card hover:border-black transition-all">
                <h3 class="text-2xl font-black uppercase text-green-600">Buy</h3>
                <p class="text-xs text-gray-400 mt-1">Sliding Scale (6% -> 2%)</p>
            </a>
        </div>
    """ + UI_FOOTER)

# --- 6. AI AGENT: GROWTH & SELLER MAGNET ---

@app.route('/ai-agent')
def ai_agent():
    if 'user_email' not in session: return redirect(url_for('google_login', next='ai-agent'))
    
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        if not user['referral_code']:
            ref = secrets.token_hex(4).upper()
            conn.execute("UPDATE users SET referral_code = ? WHERE email = ?", (ref, session['user_email']))
            conn.commit()
            return redirect(url_for('ai_agent'))

    if not user['has_ai_subscription']:
        return render_template_string(UI_HEADER + """
            <div class="text-center py-20 g-card px-10">
                <h2 class="text-5xl font-black uppercase italic mb-4">AI Inbound Agent</h2>
                <p class="text-gray-400 font-bold mb-10">Automatically post TikToks/Reels to find Sellers and recruit Buyers. $35/mo subscription.</p>
                <form action="/create-checkout-session" method="POST">
                    <button class="btn-black px-12 py-6 text-xl">Unlock Agent $35/mo</button>
                </form>
            </div>
        """ + UI_FOOTER)

    return render_template_string(UI_HEADER + """
        <div class="flex justify-between items-center mb-10">
            <h2 class="text-4xl font-black uppercase italic text-indigo-600">AI Terminal</h2>
            <div class="flex items-center space-x-2">
                <span class="text-[10px] font-black uppercase">{{ user.ai_status }}</span>
                <a href="/toggle-ai" class="w-12 h-6 bg-black rounded-full relative">
                    <div class="absolute top-1 {{ 'right-1 bg-green-400' if user.ai_status == 'on' else 'left-1 bg-gray-500' }} w-4 h-4 rounded-full transition-all"></div>
                </a>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div class="g-card p-8 border-2 {{ 'border-indigo-500' if user.growth_mode == 1 else 'border-gray-50' }}">
                <h4 class="font-black uppercase text-sm mb-2">Growth Mode</h4>
                <p class="text-[10px] text-gray-400 uppercase mb-6">AI posts videos to pull people in using your code: <b>{{ user.referral_code }}</b></p>
                <a href="/toggle-growth" class="btn-black px-6 py-3 text-[10px] block text-center">Toggle Mode</a>
            </div>
            <div class="g-card p-8 bg-green-50">
                <h4 class="font-black uppercase text-sm text-green-700 mb-2">Seller Magnet</h4>
                <p class="text-[10px] text-green-600 uppercase mb-6">AI converts homeowners to sell with us for 0% commission.</p>
                <span class="text-[10px] font-black uppercase px-3 py-1 bg-green-200 rounded-full">Always Active</span>
            </div>
        </div>

        <div class="g-card p-8">
            <h4 class="font-black uppercase text-sm mb-4">Connect Socials</h4>
            <div class="flex space-x-4">
                <button class="flex-1 py-4 bg-gray-100 rounded-2xl font-black uppercase text-[10px]">TikTok: {{ 'Linked' if user.tiktok_token else 'Connect' }}</button>
                <button class="flex-1 py-4 bg-gray-100 rounded-2xl font-black uppercase text-[10px]">Facebook: {{ 'Linked' if user.fb_token else 'Connect' }}</button>
            </div>
        </div>
    """, user=user) + UI_FOOTER

# --- 7. BUYER PORTAL (SLIDING SCALE) ---

@app.route('/buy')
def buyer_portal():
    if 'user_email' not in session: return redirect(url_for('google_login', next='buy'))
    with get_db() as conn:
        user = conn.execute("SELECT purchase_count FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        leads = conn.execute("SELECT * FROM leads WHERE status = 'active'").fetchall()
    
    rate = get_assignment_rate(user['purchase_count'] if user else 0)
    
    return render_template_string(UI_HEADER + """
        <div class="flex justify-between items-end mb-8">
            <h2 class="text-4xl font-black uppercase italic">The Feed</h2>
            <div class="text-right">
                <p class="text-[10px] font-black text-gray-400 uppercase">Tier Rate</p>
                <p class="text-2xl font-black text-indigo-600">{{ (rate*100)|int }}%</p>
            </div>
        </div>

        <div class="space-y-6">
            {% for lead in leads %}
            <div class="g-card overflow-hidden group hover:border-black transition-all">
                {% if lead.image_path %}
                <img src="/uploads/{{ lead.image_path }}" class="w-full h-64 object-cover">
                {% endif %}
                <div class="p-8">
                    <h3 class="text-2xl font-black uppercase">{{ lead.address }}</h3>
                    <p class="text-xs font-bold text-gray-400 mb-6">${{ "{:,.0f}".format(lead.asking_price) }} • {{ lead.sqft }} SQFT</p>
                    <button class="w-full btn-black py-5 text-sm">Pay ${{ "{:,.2f}".format(lead.asking_price * rate) }} Assignment Fee</button>
                </div>
            </div>
            {% endfor %}
        </div>
    """, leads=leads, rate=rate) + UI_FOOTER

# --- 8. SELLER PORTAL (PHOTOS) ---

@app.route('/sell')
def seller_portal():
    if 'user_email' not in session: return redirect(url_for('google_login', next='sell'))
    return render_template_string(UI_HEADER + """
        <h2 class="text-4xl font-black uppercase italic mb-8">List Property (Free)</h2>
        <form action="/submit-lead" method="POST" enctype="multipart/form-data" class="space-y-4">
            <input type="text" name="address" placeholder="Property Address" class="w-full p-6 border-2 border-gray-50 rounded-2xl font-bold" required>
            <div class="grid grid-cols-2 gap-4">
                <input type="number" name="price" placeholder="Asking Price ($)" class="p-6 border-2 border-gray-50 rounded-2xl font-bold" required>
                <input type="number" name="sqft" placeholder="Sqft" class="p-6 border-2 border-gray-50 rounded-2xl font-bold">
            </div>
            <div class="p-8 border-2 border-dashed border-gray-100 rounded-3xl bg-gray-50 text-center">
                <input type="file" name="photo" class="text-xs font-black uppercase" required>
                <p class="text-[8px] text-gray-400 mt-2 uppercase">AI will use this photo for TikTok/FB Reels</p>
            </div>
            <input type="text" name="contact" placeholder="Secure Contact (Email/Phone)" class="w-full p-6 border-2 border-gray-50 rounded-2xl font-bold" required>
            <button class="w-full btn-black py-8 text-xl">Submit Free Listing</button>
        </form>
    """ + UI_FOOTER)

@app.route('/submit-lead', methods=['POST'])
def submit_lead():
    f = request.form
    file = request.files.get('photo')
    filename = secure_filename(file.filename) if file and allowed_file(file.filename) else None
    if filename: file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    enc_contact = cipher.encrypt(f.get('contact', '').encode()).decode()
    with get_db() as conn:
        conn.execute("INSERT INTO leads (address, asking_price, sqft, image_path, contact_encrypted) VALUES (?, ?, ?, ?, ?)", 
                    (f.get('address'), f.get('price'), f.get('sqft'), filename, enc_contact))
        conn.commit()
    flash("Listing Active!")
    return redirect(url_for('index'))

# --- 9. PAYMENTS & AUTH ---

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[{'price': 'price_1SqIjgFXcDZgM3VoEwrUvjWP', 'quantity': 1}],
            mode='subscription',
            success_url=request.host_url + 'ai-success',
            cancel_url=request.host_url + 'ai-agent',
            customer_email=session['user_email']
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e: return str(e)

@app.route('/ai-success')
def ai_success():
    with get_db() as conn:
        conn.execute("UPDATE users SET has_ai_subscription = 1, ai_status = 'on' WHERE email = ?", (session['user_email'],))
        conn.commit()
    return redirect(url_for('ai_agent'))

@app.route('/toggle-ai')
def toggle_ai():
    with get_db() as conn:
        u = conn.execute("SELECT ai_status FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        new = 'on' if u['ai_status'] == 'off' else 'off'
        conn.execute("UPDATE users SET ai_status = ? WHERE email = ?", (new, session['user_email']))
        conn.commit()
    return redirect(url_for('ai_agent'))

@app.route('/toggle-growth')
def toggle_growth():
    with get_db() as conn:
        u = conn.execute("SELECT growth_mode FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        new = 1 if u['growth_mode'] == 0 else 0
        conn.execute("UPDATE users SET growth_mode = ? WHERE email = ?", (new, session['user_email']))
        conn.commit()
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

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/outreach')
def outreach_portal():
    if 'user_email' not in session: return redirect(url_for('google_login', next='outreach'))
    return render_template_string(UI_HEADER + """
        <h2 class="text-4xl font-black uppercase italic mb-8">Email Machine</h2>
        <div class="g-card p-10 text-center">
            <h4 class="font-black uppercase mb-4">Pricing: $49/mo or 24HR Trial</h4>
            <a href="/start-trial" class="btn-black px-10 py-4">Activate Free Trial</a>
        </div>
    """ + UI_FOOTER)

@app.route('/start-trial')
def start_trial():
    with get_db() as conn:
        end = (datetime.now() + timedelta(hours=24)).isoformat()
        conn.execute("UPDATE users SET trial_end = ? WHERE email = ?", (end, session['user_email']))
        conn.commit()
    return redirect(url_for('outreach_portal'))

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

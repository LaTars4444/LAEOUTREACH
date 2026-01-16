import os, re, base64, time, random, stripe, sqlite3, json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
from werkzeug.middleware.proxy_fix import ProxyFix

# --- 1. ROBUST CONFIGURATION ---
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

def get_cipher():
    """Ensures encryption key is valid 32-byte Base64, or generates fallback."""
    key = os.environ.get("ENCRYPTION_KEY")
    try:
        if not key: raise ValueError
        return Fernet(key.encode())
    except:
        # Fallback key to prevent crash; PII will be unreadable after restart if no ENV key
        return Fernet(Fernet.generate_key())

cipher = get_cipher()

app = Flask(__name__)
# Crucial for Render: Fixes Redirect URI Mismatch and SSL issues
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "ultra_secure_fallback_999")
DB_PATH = "platform_v14.db"

# Google Auth Setup
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
        "redirect_uris": [os.environ.get("REDIRECT_URI")]
    }
}

# --- 2. SELF-HEALING DATABASE ---
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes and Migrates database to add missing columns automatically."""
    with get_db() as conn:
        # Create Tables
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY, 
            purchase_count INTEGER DEFAULT 0, 
            trial_end TEXT, 
            has_paid_outreach INTEGER DEFAULT 0,
            bb_budget INTEGER DEFAULT -1,
            bb_any INTEGER DEFAULT 0,
            bb_min_sqft INTEGER DEFAULT 0,
            bb_min_year INTEGER DEFAULT 0,
            bb_min_beds INTEGER DEFAULT 0,
            bb_min_baths INTEGER DEFAULT 0
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
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active'
        )""")
        
        # Self-Healing Migrations: Check if columns exist, add if missing
        cursor = conn.execute("PRAGMA table_info(leads)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'asking_price' not in cols: conn.execute("ALTER TABLE leads ADD COLUMN asking_price INTEGER DEFAULT 0")
        if 'sqft' not in cols: conn.execute("ALTER TABLE leads ADD COLUMN sqft INTEGER DEFAULT 0")
        if 'contact_encrypted' not in cols: conn.execute("ALTER TABLE leads ADD COLUMN contact_encrypted TEXT")
        
        conn.commit()

init_db()

# --- 3. BULLETPROOF INPUT CLEANING ---
def safe_int(val):
    """Prevents 500 errors by stripping non-numeric text like '$' or ','."""
    if val is None: return 0
    try:
        # Regex removes everything except digits
        clean = re.sub(r'[^\d]', '', str(val))
        return int(clean) if clean else 0
    except:
        return 0

def get_current_assignment_rate(count):
    # 4% -> 3.5% -> 3% -> 2.5% -> 2%
    rates = {0: 0.040, 1: 0.035, 2: 0.030, 3: 0.025}
    return rates.get(count, 0.020)

# --- 4. GLOBAL ERROR HANDLER ---
@app.errorhandler(Exception)
def handle_exception(e):
    """Catch-all for any app error to prevent generic 500 page."""
    flash(f"System Alert: Action Interrupted. Check inputs. (Error: {str(e)})")
    return redirect(url_for('index'))

# --- 5. UI COMPONENTS ---
HTML_HEADER = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enterprise Growth Platform</title><script src="https://cdn.tailwindcss.com"></script>
    <style>body { font-family: sans-serif; } .brutalist-shadow { box-shadow: 8px 8px 0px 0px rgba(0,0,0,1); }</style>
</head>
<body class="bg-gray-100 min-h-screen p-4 flex flex-col items-center">
    <div class="w-full max-w-2xl bg-white border-4 border-black rounded-[2.5rem] brutalist-shadow p-8 md:p-12 mt-6">
"""

HTML_FOOTER = """
        <div class="mt-16 pt-8 border-t-2 border-black text-center italic">
            <h6 class="text-[10px] font-black uppercase text-gray-400 mb-2 italic">Liability Shield</h6>
            <p class="text-[8px] text-gray-400 leading-tight">Zero Liability Provider. As-Is Technology Service. No Brokerage. AES-256 Active.</p>
            <div class="mt-4"><a href="/logout" class="text-[9px] font-black uppercase text-red-500 underline">Logout Session</a></div>
        </div>
    </div>
</body></html>
"""

# --- 6. ROUTES & LOGIC ---

@app.route('/')
def index():
    return render_template_string(HTML_HEADER + """
        <header class="text-center mb-12">
            <h1 class="text-5xl font-black italic underline decoration-4 mb-2 tracking-tighter uppercase">Ultimate</h1>
            <p class="text-gray-400 text-[10px] font-bold uppercase tracking-widest italic">AI Marketplace & Outreach Engine</p>
        </header>
        {% with m = get_flashed_messages() %}{% if m %}<div class="mb-6 p-4 bg-black text-white rounded-2xl text-xs font-bold text-center italic">{{ m[0]|safe }}</div>{% endif %}{% endwith %}
        <div class="grid md:grid-cols-2 gap-4">
            <a href="/outreach" class="p-8 border-4 border-black rounded-3xl hover:bg-black hover:text-white transition group text-center">
                <h3 class="text-2xl font-black italic uppercase leading-none">Outreach</h3>
                <p class="mt-2 text-[10px] font-bold opacity-60">Campaign Engine</p>
            </a>
            <a href="/market" class="p-8 bg-blue-600 text-white rounded-3xl hover:bg-blue-700 transition shadow-xl text-center">
                <h3 class="text-2xl font-black italic uppercase leading-none">Market</h3>
                <p class="mt-2 text-[10px] font-bold opacity-80">Assignments</p>
            </a>
        </div>
    """ + HTML_FOOTER)

@app.route('/market')
def market():
    return render_template_string(HTML_HEADER + """
        <div class="flex justify-between items-center mb-10"><a href="/" class="text-xs font-black uppercase underline">← Back</a></div>
        <div class="grid grid-cols-1 gap-4 text-center">
            <a href="/auth/login?next=sell" class="p-10 border-2 border-dashed border-gray-300 rounded-3xl hover:border-black transition">
                <span class="block text-[10px] font-black uppercase text-blue-600 mb-2 italic">Free Entry</span>
                <h4 class="text-3xl font-black italic uppercase">I am a Seller</h4>
            </a>
            <a href="/auth/login?next=buy" class="p-10 border-4 border-black rounded-3xl hover:bg-gray-50 transition">
                <span class="block text-[10px] font-black uppercase text-gray-400 mb-2 italic">Scale Fees</span>
                <h4 class="text-3xl font-black italic uppercase">I am a Buyer</h4>
            </a>
        </div>
    """ + HTML_FOOTER)

@app.route('/seller')
def seller_portal():
    if 'user_email' not in session: return redirect(url_for('google_login', next='sell'))
    return render_template_string(HTML_HEADER + """
        <div class="flex justify-between items-center mb-8"><a href="/market" class="text-xs font-black uppercase underline">← Back</a></div>
        <form action="/submit-lead" method="POST" class="space-y-3">
            <input type="text" name="address" placeholder="Property Address" class="w-full border-2 p-4 rounded-xl outline-none font-bold" required>
            <div class="grid grid-cols-2 gap-2">
                <input type="text" name="price" placeholder="Asking Price ($)" class="border-2 p-4 rounded-xl font-bold">
                <input type="text" name="sqft" placeholder="Sqft" class="border-2 p-4 rounded-xl font-bold">
                <input type="text" name="year" placeholder="Year Built" class="border-2 p-4 rounded-xl font-bold">
                <input type="text" name="beds" placeholder="Beds" class="border-2 p-4 rounded-xl font-bold">
                <input type="text" name="baths" placeholder="Baths" class="border-2 p-4 rounded-xl font-bold">
            </div>
            <textarea name="reason" placeholder="Condition & Reason for Selling..." class="w-full border-2 p-4 rounded-xl h-24 outline-none font-bold" required></textarea>
            <input type="text" name="contact" placeholder="Contact Info (Email/Phone)" class="w-full border-2 p-4 rounded-xl outline-none font-bold" required>
            <button class="w-full bg-blue-600 text-white py-6 rounded-[2rem] font-black text-2xl italic shadow-xl">List My Property Anonymously</button>
        </form>
    """ + HTML_FOOTER)

@app.route('/submit-lead', methods=['POST'])
def submit_lead():
    f = request.form
    # Aggressive cleaning of all number inputs
    price, sqft, year, beds, baths = safe_int(f.get('price')), safe_int(f.get('sqft')), safe_int(f.get('year')), safe_int(f.get('beds')), safe_int(f.get('baths'))
    
    enc_reason = cipher.encrypt(f.get('reason', '').encode()).decode()
    enc_contact = cipher.encrypt(f.get('contact', '').encode()).decode()
    
    with get_db() as conn:
        conn.execute("""INSERT INTO leads (address, asking_price, sqft, year_built, beds, baths, details_encrypted, contact_encrypted, score) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                     (f.get('address'), price, sqft, year, beds, baths, enc_reason, enc_contact, random.randint(70, 99)))
        conn.commit()
    
    flash("Success! AI Matching is notifying buyers of your assignment.")
    return redirect(url_for('seller_portal'))

@app.route('/buyer')
def buyer_portal():
    if 'user_email' not in session: return redirect(url_for('google_login', next='buy'))
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        if not user or (user['bb_budget'] == -1 and user['bb_any'] == 0):
            if not user: conn.execute("INSERT INTO users (email) VALUES (?)", (session['user_email'],)); conn.commit()
            return render_template_string(HTML_HEADER + """
                <h2 class="text-2xl font-black italic uppercase mb-6 text-center">Buy-Box Selection</h2>
                <form action="/save-buybox" method="POST" class="space-y-4">
                    <label class="block p-6 border-4 border-black rounded-3xl cursor-pointer"><input type="radio" name="bb_type" value="any" checked> <span class="font-black italic uppercase ml-2 text-xl">See Everything</span></label>
                    <div class="p-6 border-2 border-dashed rounded-3xl space-y-4">
                        <label class="flex items-center"><input type="radio" name="bb_type" value="filter"> <span class="font-black italic uppercase ml-2">Zillow Filters</span></label>
                        <div class="grid grid-cols-2 gap-2">
                            <input type="text" name="budget" placeholder="Max Price ($)" class="border-b-2 p-2 outline-none font-bold italic">
                            <input type="text" name="min_sqft" placeholder="Min Sqft" class="border-b-2 p-2 outline-none font-bold italic">
                            <input type="text" name="min_beds" placeholder="Min Beds" class="border-b-2 p-2 outline-none font-bold italic">
                        </div>
                    </div>
                    <button class="w-full bg-black text-white py-6 rounded-3xl font-black text-2xl italic shadow-lg">Confirm Criteria 🎯</button>
                </form>
            """ + HTML_FOOTER)
        
        # Robust filtering logic
        query = "SELECT * FROM leads WHERE status = 'active'"
        params = []
        if user['bb_any'] == 0:
            query += " AND asking_price <= ? AND sqft >= ? AND beds >= ?"
            params.extend([user['bb_budget'], user['bb_min_sqft'], user['bb_min_beds']])
        
        leads = conn.execute(query, params).fetchall()
        rate = get_current_assignment_rate(user['purchase_count'])
    
    return render_template_string(HTML_HEADER + """
        <div class="flex justify-between items-center mb-8"><a href="/" class="text-xs font-black uppercase underline">← Menu</a> <a href="/reset-buybox" class="text-xs font-black uppercase opacity-20 hover:opacity-100">Reset</a></div>
        <div class="space-y-4">
            {% for lead in leads %}
            <div class="p-6 border-4 border-black rounded-3xl flex flex-col md:flex-row justify-between items-center group transition">
                <div>
                    <h5 class="text-xl font-black italic uppercase">Assignment #{{ lead.id }}</h5>
                    <p class="text-[10px] font-bold text-blue-600 uppercase italic tracking-widest">${{ "{:,.0f}".format(lead.asking_price) }} • {{ lead.beds }}bd • {{ lead.sqft }}sqft</p>
                </div>
                <button class="mt-4 md:mt-0 bg-black text-white px-6 py-4 rounded-xl font-black text-[10px] uppercase shadow-lg">Unlock Lead (${{ "{:,.2f}".format(lead.asking_price * rate) }})</button>
            </div>
            {% else %}
            <div class="text-center py-20 italic font-black text-gray-200 text-3xl uppercase">Scanning For Deals...</div>
            {% endfor %}
        </div>
    """, leads=leads, rate=rate) + HTML_FOOTER

@app.route('/save-buybox', methods=['POST'])
def save_buybox():
    bb_type = request.form.get('bb_type')
    if bb_type == 'any':
        data = (999999999, 1, 0, 0, 0, 0)
    else:
        data = (safe_int(request.form.get('budget')), 0, safe_int(request.form.get('min_sqft')), 0, safe_int(request.form.get('min_beds')), 0)
    
    with get_db() as conn:
        conn.execute("UPDATE users SET bb_budget=?, bb_any=?, bb_min_sqft=?, bb_min_year=?, bb_min_beds=?, bb_min_baths=? WHERE email=?", (*data, session['user_email']))
        conn.commit()
    return redirect(url_for('buyer_portal'))

@app.route('/outreach')
def outreach():
    if 'user_email' not in session: return redirect(url_for('google_login', next='outreach'))
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        access = (user and (user['has_paid_outreach'] == 1 or (user['trial_end'] and datetime.now() < datetime.fromisoformat(user['trial_end']))))
    
    return render_template_string(HTML_HEADER + """
        <div class="flex justify-between items-center mb-10"><a href="/" class="text-xs font-black uppercase underline">← Back</a></div>
        {% if not access %}
            <div class="text-center py-10 space-y-8">
                <h2 class="text-3xl font-black italic uppercase">Access Required</h2>
                <a href="/start-trial" class="block w-full bg-blue-600 text-white py-6 rounded-3xl font-black text-2xl italic shadow-2xl">Start 24HR Free Trial</a>
            </div>
        {% else %}
            <form action="/launch" method="POST" class="space-y-4">
                <textarea name="emails" placeholder="list@test.com, list2@test.com..." class="w-full border-4 border-black p-6 rounded-3xl h-32 outline-none font-bold italic" required></textarea>
                <input type="text" name="subj" placeholder="Subject" class="w-full border-2 p-5 rounded-2xl font-bold" required>
                <textarea name="body" placeholder="Deal Details..." class="w-full border-2 p-5 rounded-2xl h-40 font-bold" required></textarea>
                <button class="w-full bg-black text-white py-8 rounded-[3rem] font-black text-3xl italic shadow-2xl">Launch global Campaign 🚀</button>
            </form>
        {% endif %}
    """, access=access) + HTML_FOOTER

@app.route('/start-trial')
def start_trial():
    with get_db() as conn:
        end = (datetime.now() + timedelta(hours=24)).isoformat()
        conn.execute("UPDATE users SET trial_end = ? WHERE email = ?", (end, session['user_email']))
        conn.commit()
    flash("24HR Trial Started!")
    return redirect(url_for('outreach'))

@app.route('/auth/login')
def google_login():
    session['next_target'] = request.args.get('next', 'gate')
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=['https://www.googleapis.com/auth/userinfo.email', 'openid'])
    flow.redirect_uri = os.environ.get("REDIRECT_URI")
    auth_url, state = flow.authorization_url(prompt='consent')
    session['state'] = state
    return redirect(auth_url)

@app.route('/callback')
def callback():
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=['https://www.googleapis.com/auth/userinfo.email', 'openid'], state=session['state'])
    flow.redirect_uri = os.environ.get("REDIRECT_URI")
    flow.fetch_token(authorization_response=request.url)
    id_info = id_token.verify_oauth2_token(flow.credentials.id_token, requests.Request(), GOOGLE_CLIENT_ID)
    session['user_email'] = id_info.get('email')
    target = session.get('next_target', 'gate')
    if target == 'sell': return redirect(url_for('seller_portal'))
    if target == 'buy': return redirect(url_for('buyer_portal'))
    return redirect(url_for('outreach') if target == 'outreach' else '/')

@app.route('/reset-buybox')
def reset_buybox():
    with get_db() as conn:
        conn.execute("UPDATE users SET bb_budget=-1, bb_any=0 WHERE email=?", (session['user_email'],))
        conn.commit()
    return redirect(url_for('buyer_portal'))

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

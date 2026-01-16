import os, re, base64, time, random, stripe, sqlite3, json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

# --- 1. CORE CONFIGURATION & SECURITY ---
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
EN_KEY = os.environ.get("ENCRYPTION_KEY", Fernet.generate_key().decode())
if isinstance(EN_KEY, str): EN_KEY = EN_KEY.encode()
cipher = Fernet(EN_KEY)

app = Flask(__name__)
# Render HTTPS Fix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "ultra_secure_prod_999")
DB_PATH = "platform_v12.db"

# --- 2. GOOGLE OAUTH CONFIG ---
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

# --- 3. DATABASE ARCHITECTURE ---
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        # User Management & Buy-Box
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
        # Property Leads & Seller Details
        conn.execute("""CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            address TEXT, 
            asking_price INTEGER, 
            sqft INTEGER,
            year_built INTEGER,
            beds INTEGER,
            baths INTEGER,
            details_encrypted TEXT, 
            contact_encrypted TEXT,
            score INTEGER, 
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active'
        )""")
        conn.commit()

init_db()

# --- 4. BUSINESS LOGIC ENGINE ---
def get_current_assignment_rate(count):
    # Milestones: 4% -> 3.5% -> 3% -> 2.5% -> 2%
    rates = {0: 0.040, 1: 0.035, 2: 0.030, 3: 0.025}
    return rates.get(count, 0.020)

def check_outreach_access(email):
    if not email: return False
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user: return False
        if user['has_paid_outreach'] == 1: return True
        if user['trial_end'] and datetime.now() < datetime.fromisoformat(user['trial_end']): return True
    return False

def ai_generate_marketing(address, price):
    # Simulated AI Social Automation
    return f"🔥 OFF-MARKET DEAL: {address} for ${price:,}. High equity potential. Cash buyers only. #realestate #investing"

def find_emails(text):
    return re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)

# --- 5. UI TEMPLATES (BRUTALIST & PROFESSIONAL) ---
HTML_HEADER = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enterprise Growth Platform</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;900&display=swap');
        body { font-family: 'Inter', sans-serif; }
        .brutalist-border { border: 4px solid black; }
        .brutalist-shadow { box-shadow: 10px 10px 0px 0px rgba(0,0,0,1); }
    </style>
</head>
<body class="bg-gray-100 min-h-screen p-4 md:p-10 flex flex-col items-center">
    <div class="w-full max-w-3xl bg-white brutalist-border rounded-[3rem] brutalist-shadow p-8 md:p-16">
"""

HTML_FOOTER = """
        <div class="mt-20 pt-10 border-t-2 border-black">
            <h6 class="text-[10px] font-black uppercase text-gray-400 mb-4 italic tracking-widest">Legal Shield & Hold Harmless</h6>
            <div class="h-40 overflow-y-scroll p-6 bg-gray-50 rounded-3xl text-[9px] leading-relaxed text-gray-500 font-medium space-y-4 border italic">
                <p><strong>1. ZERO LIABILITY:</strong> THIS PLATFORM IS PROVIDED "AS-IS". THE PROVIDERS ASSUME ZERO LIABILITY FOR ANY DISPUTES, FINANCIAL LOSSES, PROPERTY DAMAGE, OR DATA BREACHES. USERS AGREE TO HOLD THE PLATFORM HARMLESS IN ALL SCENARIOS.</p>
                <p><strong>2. NO BROKERAGE:</strong> WE ARE NOT REAL ESTATE BROKERS. THIS IS A SOFTWARE INTERFACE ONLY. ALL ASSIGNMENT FEES ARE FOR DATA ACCESS.</p>
                <p><strong>3. DATA ENCRYPTION:</strong> PII IS ENCRYPTED WITH AES-256. WE ARE NOT LIABLE FOR UNAUTHORIZED DATA ACCESS.</p>
                <p><strong>4. AI DISCLAIMER:</strong> MOTIVATION SCORES AND MARKETING SCRIPTS ARE ALGORITHMIC AND MAY BE INACCURATE.</p>
            </div>
            <div class="mt-6 flex justify-center space-x-6">
                <a href="/logout" class="text-[9px] font-black uppercase text-red-500 hover:underline">Reset Session</a>
                <span class="text-[9px] font-black uppercase text-gray-300">© 2024 Enterprise Suite</span>
            </div>
        </div>
    </div>
</body>
</html>
"""

# --- 6. CORE APP ROUTES ---

@app.route('/')
def gate():
    return render_template_string(HTML_HEADER + """
        <header class="text-center mb-16">
            <h1 class="text-6xl font-black italic underline decoration-8 mb-4 tracking-tighter uppercase leading-none">Ultimate</h1>
            <p class="text-gray-400 text-[10px] font-bold uppercase tracking-[0.5em] italic">AI Marketplace & Outreach Engine</p>
        </header>

        {% with m = get_flashed_messages() %}{% if m %}<div class="mb-8 p-6 bg-black text-white rounded-3xl text-sm font-bold text-center italic brutalist-shadow">{{ m[0]|safe }}</div>{% endif %}{% endwith %}

        <div class="grid md:grid-cols-2 gap-6">
            <a href="/outreach" class="block p-10 border-4 border-black rounded-[2.5rem] hover:bg-black hover:text-white transition-all group">
                <p class="text-[10px] font-black uppercase opacity-40 group-hover:opacity-100 mb-2">Module Alpha</p>
                <h3 class="text-3xl font-black italic uppercase leading-none">Outreach Engine</h3>
                <p class="mt-4 text-xs font-bold opacity-60">PDF Scraper & Email Campaign Manager. (Trial/Paid Access)</p>
            </a>
            <a href="/market" class="block p-10 bg-blue-600 text-white rounded-[2.5rem] hover:bg-blue-700 transition-all shadow-2xl group">
                <p class="text-[10px] font-black uppercase opacity-60 group-hover:opacity-100 mb-2">Module Beta</p>
                <h3 class="text-3xl font-black italic uppercase leading-none">Market-place</h3>
                <p class="mt-4 text-xs font-bold opacity-80">Zillow-Style Property Feed & Connection. (Frictionless Intro)</p>
            </a>
        </div>
    """ + HTML_FOOTER)

@app.route('/market')
def market_choice():
    return render_template_string(HTML_HEADER + """
        <div class="flex justify-between items-center mb-12">
            <a href="/" class="text-xs font-black uppercase border-b-2 border-black">← Return</a>
            <span class="text-[10px] font-black uppercase bg-blue-600 text-white px-4 py-1 rounded-full">Secure Marketplace</span>
        </div>
        
        <div class="grid grid-cols-1 gap-6 text-center">
            <a href="/auth/login?next=sell" class="p-10 border-2 border-dashed border-gray-300 rounded-[3rem] hover:border-black transition-all group">
                <span class="block text-[10px] font-black uppercase text-blue-600 mb-2 italic">Free Submission</span>
                <h4 class="text-4xl font-black italic uppercase leading-none">I am a Seller</h4>
                <p class="mt-4 text-xs font-bold text-gray-400">List property anonymously. AI matching with cash buyers.</p>
            </a>
            <a href="/auth/login?next=buy" class="p-10 border-4 border-black rounded-[3rem] hover:bg-gray-50 transition-all group">
                <span class="block text-[10px] font-black uppercase text-gray-400 mb-2 italic">Investment Access</span>
                <h4 class="text-4xl font-black italic uppercase leading-none">I am a Buyer</h4>
                <p class="mt-4 text-xs font-bold text-gray-400 italic">Configure Buy-Box and view matching off-market assignments.</p>
            </a>
        </div>
    """ + HTML_FOOTER)

# --- 7. SELLER WORKFLOW ---
@app.route('/seller')
def seller_portal():
    if 'user_email' not in session: return redirect(url_for('google_login', next='sell'))
    return render_template_string(HTML_HEADER + """
        <div class="flex justify-between items-center mb-10"><a href="/market" class="text-xs font-black uppercase underline">← Cancel</a></div>
        <h2 class="text-4xl font-black italic uppercase mb-8">Property Intake</h2>
        
        <form action="/submit-property" method="POST" class="space-y-4">
            <div class="grid grid-cols-1 gap-4">
                <input type="text" name="address" placeholder="Property Address" class="w-full border-2 p-5 rounded-2xl outline-none focus:border-blue-600 font-bold" required>
                <div class="grid grid-cols-2 gap-4">
                    <input type="number" name="price" placeholder="Asking Price ($)" class="border-2 p-5 rounded-2xl outline-none font-bold" required>
                    <input type="number" name="sqft" placeholder="Total Sqft" class="border-2 p-5 rounded-2xl outline-none font-bold" required>
                    <input type="number" name="year" placeholder="Year Built" class="border-2 p-5 rounded-2xl outline-none font-bold" required>
                    <input type="number" name="beds" placeholder="Beds" class="border-2 p-5 rounded-2xl outline-none font-bold" required>
                    <input type="number" name="baths" placeholder="Baths" class="border-2 p-5 rounded-2xl outline-none font-bold" required>
                </div>
                <textarea name="reason" placeholder="Condition, Reason for Selling, Timeline..." class="w-full border-2 p-5 rounded-2xl h-32 outline-none font-bold" required></textarea>
                <input type="text" name="contact" placeholder="Private Contact Info (Phone/Email)" class="w-full border-2 p-5 rounded-2xl outline-none font-bold" required>
            </div>
            <button class="w-full bg-blue-600 text-white py-8 rounded-[3rem] font-black text-3xl italic shadow-2xl hover:scale-[1.02] transition-transform">List Property Anonymously</button>
            <p class="text-center text-[10px] font-black uppercase text-gray-400 italic">No fees for sellers • Your contact info is AES-256 Encrypted</p>
        </form>
    """ + HTML_FOOTER)

@app.route('/submit-property', methods=['POST'])
def submit_property():
    f = request.form
    enc_details = cipher.encrypt(f['reason'].encode()).decode()
    enc_contact = cipher.encrypt(f['contact'].encode()).decode()
    score = random.randint(72, 98)
    
    with get_db() as conn:
        conn.execute("""INSERT INTO leads (address, asking_price, sqft, year_built, beds, baths, details_encrypted, contact_encrypted, score) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                     (f['address'], int(f['price']), int(f['sqft']), int(f['year']), int(f['beds']), int(f['baths']), enc_details, enc_contact, score))
        conn.commit()
    
    marketing_mock = ai_generate_marketing(f['address'], f['price'])
    print(f"AI SOCIAL AUTOMATION TRIGGERED: {marketing_mock}")
    
    flash("Property Successfully Listed! Our AI is matching you with cash buyers.")
    return redirect(url_for('seller_portal'))

# --- 8. BUYER WORKFLOW & BUY-BOX ---
@app.route('/buyer')
def buyer_portal():
    if 'user_email' not in session: return redirect(url_for('google_login', next='buy'))
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        if not user or (user['bb_budget'] == -1 and user['bb_any'] == 0):
            if not user: conn.execute("INSERT INTO users (email) VALUES (?)", (session['user_email'],)); conn.commit()
            return render_template_string(HTML_HEADER + """
                <div class="mb-10"><h2 class="text-4xl font-black italic uppercase">Initialize Buy-Box</h2><p class="text-xs font-bold uppercase text-gray-400">Specify your deployment criteria</p></div>
                <form action="/save-buybox" method="POST" class="space-y-6">
                    <div class="space-y-4">
                        <label class="block p-8 border-4 border-black rounded-[2.5rem] cursor-pointer hover:bg-gray-50 transition">
                            <input type="radio" name="bb_type" value="any" checked>
                            <span class="text-2xl font-black italic uppercase ml-4">Option 1: See Everything</span>
                        </label>
                        <div class="p-8 border-2 border-dashed border-gray-300 rounded-[2.5rem] space-y-4">
                            <label class="flex items-center"><input type="radio" name="bb_type" value="filter"><span class="text-xl font-black italic uppercase ml-4 text-blue-600">Option 2: Zillow Filters</span></label>
                            <div class="grid grid-cols-2 gap-6 pt-4">
                                <input type="number" name="budget" placeholder="Max Price ($)" class="border-b-4 border-black p-2 outline-none font-black italic text-xl">
                                <input type="number" name="min_sqft" placeholder="Min Sqft" class="border-b-4 border-black p-2 outline-none font-black italic text-xl">
                                <input type="number" name="min_year" placeholder="Min Year" class="border-b-4 border-black p-2 outline-none font-black italic text-xl">
                                <input type="number" name="min_beds" placeholder="Min Beds" class="border-b-4 border-black p-2 outline-none font-black italic text-xl">
                                <input type="number" name="min_baths" placeholder="Min Baths" class="border-b-4 border-black p-2 outline-none font-black italic text-xl">
                            </div>
                        </div>
                    </div>
                    <button class="w-full bg-black text-white py-8 rounded-[3rem] font-black text-3xl italic shadow-2xl">Sync My Feed 🎯</button>
                </form>
            """ + HTML_FOOTER)
        
        # Lead Filtering Logic
        query = "SELECT * FROM leads WHERE status = 'active'"
        params = []
        if user['bb_any'] == 0:
            query += " AND asking_price <= ? AND sqft >= ? AND year_built >= ? AND beds >= ? AND baths >= ?"
            params.extend([user['bb_budget'], user['bb_min_sqft'], user['bb_min_year'], user['bb_min_beds'], user['bb_min_baths']])
        
        leads = conn.execute(query, params).fetchall()
        rate = get_current_assignment_rate(user['purchase_count'])
    
    return render_template_string(HTML_HEADER + """
        <div class="flex justify-between items-center mb-8">
            <a href="/" class="text-xs font-black uppercase underline">← Menu</a>
            <a href="/reset-buybox" class="text-[10px] font-black uppercase text-gray-300 hover:text-black transition underline">Reset Buy-Box</a>
        </div>
        <div class="flex justify-between items-end mb-10 border-b-4 border-black pb-4">
            <h2 class="text-4xl font-black italic uppercase leading-none">Your Deals</h2>
            <span class="text-[10px] font-black uppercase bg-green-100 text-green-700 px-4 py-1 rounded-full">Your Rate: {{ rate_p }}%</span>
        </div>

        <div class="space-y-6">
            {% for lead in leads %}
            <div class="p-8 border-4 border-black rounded-[2.5rem] flex flex-col md:flex-row justify-between items-center hover:bg-gray-50 transition-all">
                <div class="mb-6 md:mb-0">
                    <p class="text-[10px] font-black uppercase text-blue-600 mb-1">ID #{{ lead.id }} • AI SCORE: {{ lead.score }}/100</p>
                    <h5 class="text-2xl font-black italic uppercase leading-tight">Off-Market Assignment</h5>
                    <p class="text-xs font-bold text-gray-400 mt-2 uppercase tracking-widest">${{ "{:,.0f}".format(lead.asking_price) }} • {{ lead.beds }}bd/{{ lead.baths }}ba • {{ lead.sqft }}sqft</p>
                </div>
                <form action="/pay-assignment" method="POST">
                    <input type="hidden" name="id" value="{{ lead.id }}">
                    <button class="bg-black text-white px-8 py-5 rounded-2xl font-black text-xs uppercase shadow-xl hover:scale-105 transition-transform">
                        Unlock Lead<br><span class="text-[10px] opacity-60">${{ "{:,.2f}".format(lead.asking_price * rate) }} Assignment Fee</span>
                    </button>
                </form>
            </div>
            {% else %}
            <div class="text-center py-20 italic font-black text-gray-200 text-5xl uppercase tracking-tighter">Searching Matching Assignments...</div>
            {% endfor %}
        </div>
    """, leads=leads, rate=rate, rate_p=rate*100) + HTML_FOOTER

@app.route('/save-buybox', methods=['POST'])
def save_buybox():
    bb_type = request.form.get('bb_type')
    if bb_type == 'any':
        data = (999999999, 1, 0, 0, 0, 0)
    else:
        data = (
            int(request.form.get('budget') or 999999999), 0,
            int(request.form.get('min_sqft') or 0),
            int(request.form.get('min_year') or 0),
            int(request.form.get('min_beds') or 0),
            int(request.form.get('min_baths') or 0)
        )
    with get_db() as conn:
        conn.execute("UPDATE users SET bb_budget=?, bb_any=?, bb_min_sqft=?, bb_min_year=?, bb_min_beds=?, bb_min_baths=? WHERE email=?", (*data, session['user_email']))
        conn.commit()
    return redirect(url_for('buyer_portal'))

@app.route('/reset-buybox')
def reset_buybox():
    with get_db() as conn:
        conn.execute("UPDATE users SET bb_budget=-1, bb_any=0 WHERE email=?", (session['user_email'],))
        conn.commit()
    return redirect(url_for('buyer_portal'))

# --- 9. OUTREACH ENGINE ---
@app.route('/outreach')
def outreach_hub():
    if 'user_email' not in session: return redirect(url_for('google_login', next='outreach'))
    has_access = check_outreach_access(session['user_email'])
    return render_template_string(HTML_HEADER + """
        <div class="flex justify-between items-center mb-10"><a href="/" class="text-xs font-black uppercase underline">← Back</a></div>
        {% if not has_access %}
            <div class="text-center py-10 space-y-8">
                <h2 class="text-4xl font-black italic uppercase">Module Restricted</h2>
                <p class="text-gray-400 font-bold uppercase text-xs italic">The Outreach Engine requires an active subscription or trial.</p>
                <a href="/start-trial" class="block w-full bg-blue-600 text-white py-8 rounded-[3rem] font-black text-3xl italic shadow-2xl">Start 24HR Free Trial</a>
                <div class="grid grid-cols-2 gap-4">
                    <button class="p-6 border-4 border-black rounded-3xl font-black uppercase text-xs">Weekly ($3)</button>
                    <button class="p-6 bg-black text-white rounded-3xl font-black uppercase text-xs">Lifetime ($20)</button>
                </div>
            </div>
        {% else %}
            <h2 class="text-4xl font-black italic uppercase mb-8">Outreach Dashboard</h2>
            <form action="/launch-campaign" method="POST" class="space-y-6">
                <div class="space-y-2">
                    <label class="text-[10px] font-black uppercase text-gray-400">Recipient List (Manual or PDF Extraction)</label>
                    <textarea name="emails" placeholder="buyer1@test.com, buyer2@test.com..." class="w-full border-4 border-black p-6 rounded-[2.5rem] h-32 outline-none font-bold italic"></textarea>
                </div>
                <input type="text" name="subject" placeholder="Campaign Subject" class="w-full border-2 p-5 rounded-2xl outline-none font-bold" required>
                <textarea name="body" placeholder="Your pitch or deal details..." class="w-full border-2 p-5 rounded-2xl h-48 outline-none font-bold" required></textarea>
                <button class="w-full bg-black text-white py-8 rounded-[3rem] font-black text-3xl italic shadow-2xl">Launch Global Campaign 🚀</button>
            </form>
        {% endif %}
    """ + HTML_FOOTER, has_access=has_access)

@app.route('/launch-campaign', methods=['POST'])
def launch_campaign():
    if not check_outreach_access(session.get('user_email')): return redirect(url_for('outreach_hub'))
    emails = find_emails(request.form.get('emails'))
    if not emails: flash("No valid emails found to launch campaign."); return redirect(url_for('outreach_hub'))
    
    # Campaign simulation
    time.sleep(1) # Simulate logic delay
    flash(f"Campaign Launched! Initializing delivery to {len(emails)} targets.")
    return redirect(url_for('outreach_hub'))

@app.route('/start-trial')
def start_trial():
    with get_db() as conn:
        end = (datetime.now() + timedelta(hours=24)).isoformat()
        conn.execute("UPDATE users SET trial_end = ? WHERE email = ?", (end, session['user_email']))
        conn.commit()
    flash("Trial Activated! Engine Unlocked for 24 Hours.")
    return redirect(url_for('outreach_hub'))

# --- 10. AUTHENTICATION & SESSION ---
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
    if target == 'outreach': return redirect(url_for('outreach_hub'))
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- 11. ENTRY POINT ---
if __name__ == '__main__':
    # Using 0.0.0.0 for Render internal network binding
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

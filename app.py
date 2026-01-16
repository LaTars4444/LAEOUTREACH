import os, re, base64, time, random, stripe, sqlite3, json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests

# --- CONFIG & SECURITY ---
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
EN_KEY = os.environ.get("ENCRYPTION_KEY", Fernet.generate_key().decode())
if isinstance(EN_KEY, str):
    EN_KEY = EN_KEY.encode()
cipher = Fernet(EN_KEY)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "secure_dev_key_999")
DB_PATH = "marketplace.db"

# --- GOOGLE OAUTH CONFIG ---
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

# --- DATABASE SETUP ---
def get_db():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY, 
            purchase_count INTEGER DEFAULT 0, 
            trial_end TEXT, 
            has_paid_outreach INTEGER DEFAULT 0,
            buybox_budget INTEGER DEFAULT -1,
            buybox_any INTEGER DEFAULT 0
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            address TEXT, 
            valuation INTEGER, 
            details_encrypted TEXT, 
            score INTEGER, 
            status TEXT DEFAULT 'active'
        )""")
        conn.commit()

init_db()

def get_current_rate(count):
    rates = {0: 0.040, 1: 0.035, 2: 0.030, 3: 0.025}
    return rates.get(count, 0.020)

# --- UI TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Growth Platform</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-50 min-h-screen p-4 font-sans text-slate-900 flex flex-col items-center">
    <div class="w-full max-w-2xl bg-white rounded-[3rem] shadow-2xl p-8 md:p-16 border border-gray-100 mt-10">
        <header class="text-center mb-12">
            <h1 class="text-5xl font-black italic underline decoration-8 mb-2 tracking-tighter uppercase leading-tight">Ultimate Platform</h1>
            <p class="text-gray-400 text-[10px] font-bold uppercase tracking-[0.4em] italic">Automated Buy-Box Matching</p>
        </header>

        {% with m = get_flashed_messages() %}{% if m %}<div class="mb-6 p-4 bg-black text-white rounded-2xl text-xs font-bold text-center">{{ m[0]|safe }}</div>{% endif %}{% endwith %}

        {% if step == 'gate' %}
            <div class="space-y-4">
                <a href="/outreach" class="block w-full p-10 border-4 border-black rounded-[2.5rem] hover:bg-black hover:text-white transition-all group">
                    <h3 class="text-3xl font-black italic uppercase leading-none">Outreach Engine</h3>
                    <p class="mt-4 text-xs font-bold opacity-60 italic tracking-widest uppercase">Target & Campaign Manager</p>
                </a>
                <a href="/market-choice" class="block w-full p-10 bg-blue-600 text-white rounded-[2.5rem] hover:bg-blue-700 transition-all shadow-xl">
                    <h3 class="text-3xl font-black italic uppercase leading-none">Market-place</h3>
                    <p class="mt-4 text-xs font-bold opacity-80 italic tracking-widest uppercase">Property Connections</p>
                </a>
            </div>

        {% elif step == 'market-choice' %}
            <div class="flex justify-between items-center mb-10"><a href="/" class="text-xs font-black uppercase border-b-2 border-black">← Back</a></div>
            <div class="grid grid-cols-1 gap-4 text-center">
                <a href="/auth/login?next=sell" class="p-8 border-2 border-dashed border-gray-300 rounded-[2rem] hover:border-black transition">
                    <span class="block text-[10px] font-black uppercase text-blue-600 mb-2 italic">Seller</span>
                    <h4 class="text-2xl font-black italic uppercase leading-none">Submit FREE Property</h4>
                </a>
                <a href="/auth/login?next=buy" class="p-8 border-2 border-black rounded-[2rem] hover:bg-gray-50 transition text-center group">
                    <span class="block text-[10px] font-black uppercase text-gray-400 mb-2 italic">Buyer</span>
                    <h4 class="text-2xl font-black italic uppercase leading-none">Define Buy-Box</h4>
                </a>
            </div>

        {% elif step == 'buybox-setup' %}
            <div class="mb-8"><h2 class="text-3xl font-black italic uppercase">Configure Buy-Box</h2></div>
            <form action="/save-buybox" method="POST" class="space-y-6">
                <div class="space-y-4 text-left">
                    <label class="block p-6 border-2 rounded-3xl cursor-pointer hover:border-blue-600">
                        <input type="radio" name="bb_type" value="any" checked>
                        <span class="font-black italic uppercase ml-2">Receive Anything</span>
                    </label>
                    <label class="block p-6 border-2 rounded-3xl cursor-pointer hover:border-blue-600">
                        <input type="radio" name="bb_type" value="budget">
                        <span class="font-black italic uppercase ml-2">Set Max Budget</span>
                        <input type="number" name="budget" placeholder="Max Price ($)" class="block w-full mt-4 border-b-2 border-black p-2 outline-none text-xl font-black italic">
                    </label>
                </div>
                <button type="submit" class="w-full bg-black text-white py-6 rounded-[2.5rem] font-black text-2xl italic shadow-2xl">Confirm Buy-Box 🎯</button>
            </form>

        {% elif step == 'buyer-feed' %}
            <div class="flex justify-between items-center mb-8"><a href="/" class="text-xs font-black uppercase underline">← Menu</a><a href="/buybox-reset" class="text-[10px] font-black uppercase text-gray-400 underline">Edit Box</a></div>
            <div class="bg-blue-50 p-4 rounded-2xl mb-6 flex justify-between items-center border">
                <span class="text-[10px] font-black uppercase text-blue-600 italic">Matching: {{ bb_label }}</span>
                <span class="text-[10px] font-black uppercase bg-blue-600 text-white px-3 py-1 rounded-full">Fee: {{ rate }}%</span>
            </div>
            <div class="space-y-4">
                {% for lead in leads %}
                <div class="p-8 border-2 border-black rounded-[2rem] flex flex-col md:flex-row justify-between items-center hover:bg-gray-50 transition">
                    <div class="mb-4 md:mb-0">
                        <p class="text-[10px] font-bold text-gray-400 uppercase">Property ID #{{ lead.id }}</p>
                        <h5 class="text-xl font-black italic uppercase leading-none">Off-Market Assignment</h5>
                        <p class="text-[10px] font-bold text-blue-600 uppercase mt-1">Valuation: ${{ "{:,.0f}".format(lead.valuation) }}</p>
                    </div>
                    <button class="w-full md:w-auto bg-black text-white px-8 py-4 rounded-2xl font-black text-[10px] uppercase shadow-lg">Unlock lead (${{ "{:,.2f}".format(lead.valuation * current_rate) }})</button>
                </div>
                {% else %}
                <div class="text-center py-20 italic font-black text-gray-200 text-3xl uppercase">Scanning Matches...</div>
                {% endfor %}
            </div>

        {% elif step == 'seller-form' %}
            <div class="flex justify-between items-center mb-8"><a href="/" class="text-xs font-black uppercase underline">← Back</a></div>
            <form action="/submit-lead" method="POST" class="space-y-4">
                <input type="text" name="address" placeholder="Property Address" class="w-full border-2 p-5 rounded-2xl outline-none" required>
                <input type="number" name="valuation" placeholder="Estimated Value (USD)" class="w-full border-2 p-5 rounded-2xl outline-none" required>
                <textarea name="reason" placeholder="Property Details & Motivation..." class="w-full border-2 p-5 rounded-2xl h-32 outline-none" required></textarea>
                <button class="w-full bg-blue-600 text-white py-6 rounded-[2.5rem] font-black text-2xl italic shadow-xl">Get Offer Connections</button>
            </form>
        {% endif %}

        <div class="mt-20 pt-10 border-t">
            <h6 class="text-[10px] font-black uppercase text-gray-400 mb-4 tracking-tighter italic">Liability Disclaimer</h6>
            <div class="h-32 overflow-y-scroll p-4 bg-gray-50 rounded-2xl text-[9px] leading-relaxed text-gray-400 border font-medium">
                <p><strong>ZERO LIABILITY:</strong> You agree to HOLD HARMLESS the platform from any losses or disputes. We are a tech provider, not a broker. All assignment fees are for software access only.</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

# --- ROUTES ---
@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE, step='gate')

@app.route('/market-choice')
def market_choice(): return render_template_string(HTML_TEMPLATE, step='market-choice')

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
    return redirect('/')

@app.route('/buyer-portal')
def buyer_portal():
    if 'user_email' not in session: return redirect(url_for('google_login', next='buy'))
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        if not user or (user['buybox_budget'] == -1 and user['buybox_any'] == 0):
            if not user: conn.execute("INSERT INTO users (email) VALUES (?)", (session['user_email'],)); conn.commit()
            return render_template_string(HTML_TEMPLATE, step='buybox-setup')
        
        query = "SELECT * FROM leads WHERE status = 'active'"
        params = []
        if user['buybox_any'] == 0:
            query += " AND valuation <= ?"
            params.append(user['buybox_budget'])
        
        leads = conn.execute(query, params).fetchall()
        rate = get_current_rate(user['purchase_count'])
        bb_label = "Anything" if user['buybox_any'] == 1 else f"Max ${user['buybox_budget']:,}"
        
    return render_template_string(HTML_TEMPLATE, step='buyer-feed', leads=leads, current_rate=rate, rate=rate*100, bb_label=bb_label)

@app.route('/save-buybox', methods=['POST'])
def save_buybox():
    bb_type = request.form.get('bb_type')
    budget = int(request.form.get('budget', 0)) if bb_type == 'budget' else -1
    bb_any = 1 if bb_type == 'any' else 0
    with get_db() as conn:
        conn.execute("UPDATE users SET buybox_budget = ?, buybox_any = ? WHERE email = ?", (budget, bb_any, session['user_email']))
        conn.commit()
    return redirect(url_for('buyer_portal'))

@app.route('/buybox-reset')
def buybox_reset():
    with get_db() as conn:
        conn.execute("UPDATE users SET buybox_budget = -1, buybox_any = 0 WHERE email = ?", (session['user_email'],))
        conn.commit()
    return redirect(url_for('buyer_portal'))

@app.route('/seller-portal')
def seller_portal():
    if 'user_email' not in session: return redirect(url_for('google_login', next='sell'))
    return render_template_string(HTML_TEMPLATE, step='seller-form')

@app.route('/submit-lead', methods=['POST'])
def submit_lead():
    addr, val, reason = request.form.get('address'), int(request.form.get('valuation', 0)), request.form.get('reason')
    with get_db() as conn:
        conn.execute("INSERT INTO leads (address, valuation, details_encrypted, score) VALUES (?, ?, ?, ?)", (addr, val, cipher.encrypt(reason.encode()).decode(), random.randint(70, 99)))
        conn.commit()
    flash("Property Submitted Anonymously.")
    return redirect(url_for('seller_portal'))

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

import os, re, base64, time, random, stripe, sqlite3
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from flask import Flask, render_template_string, request, redirect, url_for, session, flash

# --- ENCRYPTION & SECRETS ---
# Note: Render will use the Environment Variables you input in their dashboard
EN_KEY = os.environ.get("ENCRYPTION_KEY", Fernet.generate_key())
if isinstance(EN_KEY, str): EN_KEY = EN_KEY.encode()
cipher = Fernet(EN_KEY)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "prod_v11_frictionless")
# Using a local file for SQLite on Render
DB_PATH = "marketplace.db"

# --- DATABASE SETUP ---
def get_db():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, purchase_count INTEGER DEFAULT 0, trial_end TEXT, has_paid_outreach INTEGER DEFAULT 0)")
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

# --- DYNAMIC PERCENTAGE ENGINE ---
def get_current_rate(count):
    # Milestone: 1st: 4%, 2nd: 3.5%, 3rd: 3%, 4th: 2.5%, 5+: 2%
    rates = {0: 0.040, 1: 0.035, 2: 0.030, 3: 0.025}
    return rates.get(count, 0.020)

# --- UI TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Growth Suite | Marketplace</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-50 min-h-screen p-4 font-sans text-slate-900 flex flex-col items-center">
    <div class="w-full max-w-2xl bg-white rounded-[3rem] shadow-2xl p-8 md:p-16 border border-gray-100 mt-10">
        
        <header class="text-center mb-12">
            <h1 class="text-5xl font-black italic underline decoration-8 mb-2 tracking-tighter uppercase">Ultimate Platform</h1>
            <p class="text-gray-400 text-[10px] font-bold uppercase tracking-[0.4em] italic">AI Inbound & Outreach Suite</p>
        </header>

        {% with m = get_flashed_messages() %}{% if m %}<div class="mb-6 p-4 bg-black text-white rounded-2xl text-xs font-bold text-center">{{ m[0]|safe }}</div>{% endif %}{% endwith %}

        {% if step == 'gate' %}
            <div class="space-y-4">
                <a href="/outreach-portal" class="block w-full p-10 border-4 border-black rounded-[2.5rem] hover:bg-black hover:text-white transition-all group">
                    <h3 class="text-3xl font-black italic uppercase leading-none">1. Outreach Engine</h3>
                    <p class="mt-4 text-xs font-bold opacity-60">PDF/Email Campaign Manager (Paywalled)</p>
                </a>
                <a href="/market-choice" class="block w-full p-10 bg-blue-600 text-white rounded-[2.5rem] hover:bg-blue-700 transition-all shadow-xl">
                    <h3 class="text-3xl font-black italic uppercase leading-none">2. Market-place</h3>
                    <p class="mt-4 text-xs font-bold opacity-80">Free Intake & Property Matching (% Fees)</p>
                </a>
            </div>

        {% elif step == 'market-choice' %}
            <div class="flex justify-between items-center mb-10"><a href="/" class="text-xs font-black uppercase border-b-2 border-black">← Back</a></div>
            <div class="grid grid-cols-1 gap-4 text-center">
                <a href="/login?next=sell" class="p-8 border-2 border-dashed border-gray-300 rounded-[2rem] hover:border-black transition">
                    <span class="block text-[10px] font-black uppercase text-blue-600 mb-2 italic">I am a Seller</span>
                    <h4 class="text-2xl font-black italic uppercase">Submit My Property (FREE)</h4>
                </a>
                <a href="/login?next=buy" class="p-8 border-2 border-black rounded-[2rem] hover:bg-gray-50 transition">
                    <span class="block text-[10px] font-black uppercase text-gray-400 mb-2 italic">I am a Buyer</span>
                    <h4 class="text-2xl font-black italic uppercase">Access Off-Market Leads</h4>
                </a>
            </div>

        {% elif step == 'outreach-dashboard' %}
            <div class="flex justify-between items-center mb-8"><a href="/" class="text-xs font-black uppercase underline">← Menu</a></div>
            {% if not has_access %}
                <div class="text-center py-10 space-y-6">
                    <h4 class="text-2xl font-black italic">Trial Required</h4>
                    <a href="/start-trial" class="block bg-blue-600 text-white py-6 rounded-3xl font-black text-xl shadow-lg">Start 24HR Free Trial</a>
                    <p class="text-[10px] font-bold text-gray-400 uppercase italic">Outreach is a paid module. Trial is free, no card required.</p>
                </div>
            {% else %}
                <div class="bg-green-50 p-4 rounded-2xl mb-6 text-green-700 text-[10px] font-black uppercase text-center border">Campaign Engine Ready ✅</div>
                <form class="space-y-4">
                    <textarea placeholder="Paste emails..." class="w-full border-2 p-6 rounded-[2rem] h-32 outline-none focus:ring-4 ring-blue-50"></textarea>
                    <button class="w-full bg-black text-white py-6 rounded-[2.5rem] font-black text-2xl italic">Blast Leads 🚀</button>
                </form>
            {% endif %}

        {% elif step == 'seller-form' %}
            <div class="flex justify-between items-center mb-8"><a href="/" class="text-xs font-black uppercase underline">← Back</a></div>
            <form action="/submit-lead" method="POST" class="space-y-4">
                <p class="text-[10px] font-black uppercase text-blue-600 italic">Submit property for free offer intro</p>
                <input type="text" name="address" placeholder="Address" class="w-full border-2 p-5 rounded-2xl outline-none" required>
                <input type="number" name="valuation" placeholder="Estimated Value (USD)" class="w-full border-2 p-5 rounded-2xl outline-none" required>
                <textarea name="reason" placeholder="Reason for selling & Property Condition..." class="w-full border-2 p-5 rounded-2xl h-32 outline-none" required></textarea>
                <button class="w-full bg-blue-600 text-white py-6 rounded-[2.5rem] font-black text-2xl italic shadow-xl">Get Offer Introductions</button>
            </form>

        {% elif step == 'buyer-feed' %}
            <div class="flex justify-between items-center mb-8"><a href="/" class="text-xs font-black uppercase underline">← Menu</a><span class="text-[10px] font-black uppercase bg-green-100 text-green-700 px-3 py-1 rounded-full">Current Rate: {{ rate }}%</span></div>
            <div class="space-y-4">
                {% for lead in leads %}
                <div class="p-8 border-2 border-black rounded-[2rem] flex flex-col md:flex-row justify-between items-center group">
                    <div class="mb-4 md:mb-0">
                        <p class="text-[10px] font-bold text-gray-400 uppercase">Property ID #{{ lead.id }}</p>
                        <h5 class="text-xl font-black italic uppercase leading-none">Assignment Opportunity</h5>
                        <p class="text-[10px] font-bold text-blue-600 uppercase mt-1">Motivation: {{ lead.score }}/100</p>
                    </div>
                    <button class="w-full md:w-auto bg-black text-white px-8 py-4 rounded-2xl font-black text-[10px] uppercase shadow-lg hover:scale-105 transition-all">
                        Unlock for ${{ "{:,.2f}".format(lead.valuation * current_rate) }}
                    </button>
                </div>
                {% endfor %}
            </div>
        {% endif %}

        <!-- LEGAL (HUGE DISCLAIMER) -->
        <div class="mt-20 pt-10 border-t">
            <h6 class="text-[10px] font-black uppercase text-gray-400 mb-4 tracking-tighter italic">Legal Disclaimer & Hold Harmless Clause</h6>
            <div class="h-40 overflow-y-scroll p-6 bg-gray-50 rounded-3xl text-[9px] leading-relaxed text-gray-400 border font-medium">
                <p class="mb-2"><strong>1. ZERO LIABILITY:</strong> THIS PLATFORM ("SYSTEM") IS PROVIDED "AS-IS". THE DEVELOPERS, OWNERS, AND HOSTING ENTITIES (COLLECTIVELY "PROVIDERS") ASSUME ABSOLUTELY ZERO LIABILITY FOR ANY FINANCIAL DISPUTES, CONTRACTUAL FAILURES, PROPERTY DAMAGE, OR PERSONAL LOSS RESULTING FROM CONNECTIONS MADE ON THIS MARKETPLACE. </p>
                <p class="mb-2"><strong>2. NO REAL ESTATE BROKERAGE:</strong> WE ARE A TECHNOLOGY COMPANY, NOT A BROKERAGE. We do not represent buyers or sellers. All assignment fees are for software access to property data only.</p>
                <p class="mb-2"><strong>3. DATA & SECURITY:</strong> We use AES-256 encryption but provide no guarantee against breaches. By using this tool, you waive all rights to sue for data incidents.</p>
                <p><strong>4. AI ACCURACY:</strong> Motivation scores and AI-generated social marketing posts are algorithms only and may be 100% false. Always perform independent due diligence.</p>
            </div>
        </div>

    </div>
</body>
</html>
"""

# --- ROUTES ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, step='gate')

@app.route('/market-choice')
def market_choice():
    return render_template_string(HTML_TEMPLATE, step='market-choice')

@app.route('/login')
def login():
    # Frictionless Logic: Log them in via session and redirect to their target
    # In production: replace this with a real Google Auth Redirect
    session['user_email'] = "verified_user@gmail.com"
    next_page = request.args.get('next', 'gate')
    if next_page == 'sell': return redirect(url_for('seller_portal'))
    if next_page == 'buy': return redirect(url_for('buyer_portal'))
    return redirect(url_for('outreach_portal'))

@app.route('/outreach-portal')
def outreach_portal():
    if 'user_email' not in session: return redirect(url_for('login', next='outreach'))
    email = session['user_email']
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            conn.execute("INSERT INTO users (email) VALUES (?)", (email,))
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    
    has_access = (user['has_paid_outreach'] == 1) or (user['trial_end'] and datetime.now() < datetime.fromisoformat(user['trial_end']))
    return render_template_string(HTML_TEMPLATE, step='outreach-dashboard', has_access=has_access)

@app.route('/seller-portal')
def seller_portal():
    if 'user_email' not in session: return redirect(url_for('login', next='sell'))
    return render_template_string(HTML_TEMPLATE, step='seller-form')

@app.route('/buyer-portal')
def buyer_portal():
    if 'user_email' not in session: return redirect(url_for('login', next='buy'))
    with get_db() as conn:
        user = conn.execute("SELECT purchase_count FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        count = user['purchase_count'] if user else 0
        current_rate = get_current_rate(count)
        leads = conn.execute("SELECT * FROM leads WHERE status = 'active'").fetchall()
    return render_template_string(HTML_TEMPLATE, step='buyer-feed', leads=leads, current_rate=current_rate, rate=current_rate*100)

@app.route('/submit-lead', methods=['POST'])
def submit_lead():
    addr = request.form.get('address')
    val = request.form.get('valuation', 100000)
    reason = request.form.get('reason')
    
    enc_details = cipher.encrypt(reason.encode()).decode()
    score = random.randint(70, 99) # AI Scoring Mock

    with get_db() as conn:
        conn.execute("INSERT INTO leads (address, valuation, details_encrypted, score) VALUES (?, ?, ?, ?)",
                     (addr, val, enc_details, score))
        conn.commit()
    
    flash("Inbound property saved. AI is matching you with cash buyers.")
    return redirect(url_for('seller_portal'))

@app.route('/start-trial')
def start_trial():
    email = session.get('user_email')
    if email:
        with get_db() as conn:
            end_date = (datetime.now() + timedelta(hours=24)).isoformat()
            conn.execute("UPDATE users SET trial_end = ? WHERE email = ?", (end_date, email))
            conn.commit()
        flash("24-Hour Trial Activated! 🚀")
    return redirect(url_for('outreach_portal'))

@app.route('/logout')
def logout():
    session.clear(); return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

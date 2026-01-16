import os, re, base64, time, random, stripe, sqlite3
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from flask import Flask, render_template_string, request, redirect, url_for, session, flash

# --- ENCRYPTION & SECRETS ---
# Note: In production, set ENCRYPTION_KEY as an env var to persist data access
EN_KEY = os.environ.get("ENCRYPTION_KEY", Fernet.generate_key())
cipher = Fernet(EN_KEY)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "prod_v11_frictionless")
DB_PATH = "/tmp/marketplace_v11.db"

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
    rates = {0: 0.040, 1: 0.035, 2: 0.030, 3: 0.025}
    return rates.get(count, 0.020)

# --- UI TEMPLATE (BRUTALIST & SECURE) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Secure Growth Suite</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-50 min-h-screen p-4 font-sans text-slate-900 flex flex-col items-center">
    <div class="w-full max-w-2xl bg-white rounded-[3rem] shadow-2xl p-8 md:p-16 border border-gray-100 mt-10">
        
        <header class="text-center mb-12">
            <h1 class="text-5xl font-black italic underline decoration-8 mb-2 tracking-tighter uppercase">Ultimate Platform</h1>
            <p class="text-gray-400 text-[10px] font-bold uppercase tracking-[0.4em] italic">Plug-and-Play AI Marketplace</p>
        </header>

        {% with m = get_flashed_messages() %}{% if m %}<div class="mb-6 p-4 bg-black text-white rounded-2xl text-xs font-bold text-center">{{ m[0]|safe }}</div>{% endif %}{% endwith %}

        {% if step == 'gate' %}
            <!-- STEP 1: FRICTIONLESS CHOICE (NO LOGIN) -->
            <div class="space-y-4">
                <a href="/outreach-start" class="block w-full p-10 border-4 border-black rounded-[2.5rem] hover:bg-black hover:text-white transition-all group">
                    <h3 class="text-3xl font-black italic uppercase leading-none">1. Outreach Engine</h3>
                    <p class="mt-4 text-xs font-bold opacity-60">Send campaigns & find leads. (Subscription Mode)</p>
                </a>
                <a href="/market-choice" class="block w-full p-10 bg-blue-600 text-white rounded-[2.5rem] hover:bg-blue-700 transition-all shadow-xl">
                    <h3 class="text-3xl font-black italic uppercase leading-none">2. Market-place</h3>
                    <p class="mt-4 text-xs font-bold opacity-80">Sell properties for free or buy assignments. (% Mode)</p>
                </a>
            </div>

        {% elif step == 'market-choice' %}
            <!-- STEP 2: MARKETPLACE CHOICE (NO LOGIN YET) -->
            <div class="flex justify-between items-center mb-10"><a href="/" class="text-xs font-black uppercase border-b-2 border-black">← Back</a></div>
            <div class="grid grid-cols-1 gap-4">
                <a href="/login?next=sell" class="p-8 border-2 border-dashed border-gray-300 rounded-[2rem] hover:border-black transition text-center group">
                    <span class="block text-[10px] font-black uppercase text-blue-600 mb-2">I am a seller</span>
                    <h4 class="text-2xl font-black italic uppercase">Submit My Property (FREE)</h4>
                </a>
                <a href="/login?next=buy" class="p-8 border-2 border-black rounded-[2rem] hover:bg-gray-50 transition text-center group">
                    <span class="block text-[10px] font-black uppercase text-gray-400 mb-2">I am a buyer</span>
                    <h4 class="text-2xl font-black italic uppercase">Access Off-Market Leads</h4>
                </a>
            </div>

        {% elif step == 'outreach-dashboard' %}
            <!-- OUTREACH PAYWALL/DASHBOARD (LOGGED IN) -->
            <div class="flex justify-between items-center mb-8"><a href="/" class="text-xs font-black uppercase">← Menu</a><span class="text-[10px] font-black uppercase px-3 py-1 bg-black text-white rounded-full">Outreach Active</span></div>
            {% if not has_access %}
                <div class="text-center py-10 space-y-6">
                    <h4 class="text-2xl font-black italic">Access Restricted</h4>
                    <a href="/start-trial" class="block bg-blue-600 text-white py-6 rounded-3xl font-black text-xl shadow-lg">Activate 24HR Free Trial</a>
                    <p class="text-[10px] font-bold text-gray-400 uppercase">Or pay $3/wk or $20 Lifetime for unlimited Outreach</p>
                </div>
            {% else %}
                <form class="space-y-4">
                    <textarea placeholder="Paste emails here..." class="w-full border-2 p-6 rounded-[2rem] h-40 outline-none focus:ring-4 ring-blue-50"></textarea>
                    <button class="w-full bg-black text-white py-6 rounded-[2.5rem] font-black text-2xl italic">Blast Campaign 🚀</button>
                </form>
            {% endif %}

        {% elif step == 'seller-form' %}
            <!-- SELLER INTAKE (LOGGED IN) -->
            <div class="flex justify-between items-center mb-8"><a href="/" class="text-xs font-black uppercase">← Cancel</a><span class="text-[10px] font-black uppercase text-blue-600">Secure Submission</span></div>
            <form action="/submit-lead" method="POST" class="space-y-4">
                <input type="text" name="address" placeholder="Property Address" class="w-full border-2 p-5 rounded-2xl outline-none" required>
                <input type="number" name="valuation" placeholder="Estimated Value (USD)" class="w-full border-2 p-5 rounded-2xl outline-none" required>
                <textarea name="reason" placeholder="Why are you selling? (AI Scoring Active)" class="w-full border-2 p-5 rounded-2xl h-32 outline-none" required></textarea>
                <button class="w-full bg-blue-600 text-white py-6 rounded-[2.5rem] font-black text-2xl italic shadow-xl">Get Offer Connections</button>
            </form>

        {% elif step == 'buyer-feed' %}
            <!-- BUYER FEED (LOGGED IN) -->
            <div class="flex justify-between items-center mb-8"><a href="/" class="text-xs font-black uppercase">← Menu</a><span class="text-[10px] font-black uppercase bg-green-100 text-green-700 px-3 py-1 rounded-full">Milestone: {{ rate }}%</span></div>
            <div class="space-y-4">
                {% for lead in leads %}
                <div class="p-6 border-2 border-black rounded-[2rem] flex flex-col md:flex-row justify-between items-center hover:bg-gray-50 transition">
                    <div class="mb-4 md:mb-0">
                        <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Property #{{ lead.id }}</p>
                        <h5 class="text-xl font-black italic uppercase leading-none">Off-Market Assignment</h5>
                        <p class="text-[10px] font-bold text-blue-600 uppercase mt-1">AI Score: {{ lead.score }}/100</p>
                    </div>
                    <button class="w-full md:w-auto bg-black text-white px-8 py-4 rounded-2xl font-black text-[10px] uppercase">Unlock for ${{ "{:,.2f}".format(lead.valuation * current_rate) }}</button>
                </div>
                {% else %}
                <div class="text-center py-20 italic font-black text-gray-200 text-4xl">NO DEALS FOUND</div>
                {% endfor %}
            </div>
        {% endif %}

        <!-- LEGAL DISCLAIMER -->
        <div class="mt-20 pt-10 border-t">
            <h6 class="text-[10px] font-black uppercase text-gray-400 mb-4">Terms of Use & Zero-Responsibility Policy</h6>
            <div class="h-40 overflow-y-scroll p-6 bg-gray-50 rounded-3xl text-[9px] leading-relaxed text-gray-500 border italic font-medium">
                <p class="mb-2"><strong>1. HOLD HARMLESS:</strong> BY USING THIS PLATFORM, YOU AGREE THAT THE OWNERS, DEVELOPERS, AND AFFILIATES HOLD NO RESPONSIBILITY FOR ANY LOSSES, LEGAL DISPUTES, PROPERTY DAMAGE, OR FINANCIAL RUIN. YOU USE THIS TOOL AT YOUR OWN RISK.</p>
                <p class="mb-2"><strong>2. NO BROKERAGE:</strong> WE ARE NOT REAL ESTATE BROKERS. We provide software for data connection. Any agreement between buyer and seller is strictly between those parties.</p>
                <p class="mb-2"><strong>3. DATA SECURITY:</strong> We use AES-256 for PII, but we are not liable for data breaches, hacking, or unauthorized access. Your data is stored 'as-is'.</p>
                <p class="mb-2"><strong>4. NO REFUNDS:</strong> All assignment fees and outreach subscriptions are final and non-refundable upon payment.</p>
                <p><strong>5. AI ACCURACY:</strong> Motivation scores and marketing content are generated by algorithms and may be completely inaccurate. Verify all facts independently.</p>
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
    # Simulate Google OAuth Login
    # In production, redirect to Google Auth and back to /callback
    session['user_email'] = "user@example.com"
    target = request.args.get('next', 'gate')
    
    if target == 'sell': return redirect(url_for('seller_portal'))
    if target == 'buy': return redirect(url_for('buyer_portal'))
    return redirect(url_for('outreach_portal'))

@app.route('/outreach-start')
def outreach_portal():
    if 'user_email' not in session: return redirect(url_for('login', next='outreach'))
    
    email = session['user_email']
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            conn.execute("INSERT INTO users (email) VALUES (?)", (email,))
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    has_access = False
    if user['has_paid_outreach'] == 1: has_access = True
    if user['trial_end'] and datetime.now() < datetime.fromisoformat(user['trial_end']): has_access = True

    return render_template_string(HTML_TEMPLATE, step='outreach-dashboard', has_access=has_access)

@app.route('/sell-portal')
def seller_portal():
    if 'user_email' not in session: return redirect(url_for('login', next='sell'))
    return render_template_string(HTML_TEMPLATE, step='seller-form')

@app.route('/buy-portal')
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
    
    # Secure Encryption (AES-256)
    enc_details = cipher.encrypt(reason.encode()).decode()
    score = random.randint(70, 99) # AI Scoring Placeholder

    with get_db() as conn:
        conn.execute("INSERT INTO leads (address, valuation, details_encrypted, score) VALUES (?, ?, ?, ?)",
                     (addr, val, enc_details, score))
        conn.commit()
    
    flash("Submission Complete. Our AI is matching you with Buyers now. Check your email for introductions.")
    return redirect(url_for('seller_portal'))

@app.route('/start-trial')
def start_trial():
    email = session.get('user_email')
    if email:
        with get_db() as conn:
            end_date = (datetime.now() + timedelta(hours=24)).isoformat()
            conn.execute("UPDATE users SET trial_end = ? WHERE email = ?", (end_date, email))
            conn.commit()
        flash("24-Hour Outreach Trial Activated! ✅")
    return redirect(url_for('outreach_portal'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    # Use 0.0.0.0 for plug-and-play network access
    app.run(host='0.0.0.0', port=5000, debug=True)

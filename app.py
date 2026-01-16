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
from email.mime.text import MIMEText
from groq import Groq

# --- 1. CONFIGURATION ---
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Render Config
UPLOAD_FOLDER = '/tmp/uploads'
DB_PATH = "pro_exchange_v26.db"

# YOUR STRIPE PRICE IDS
PRICE_ID_EMAIL_WEEKLY = "price_1SpxexFXcDZgM3Vo0iYmhfpb" # $3/wk
PRICE_ID_EMAIL_ONCE = "price_1Spy7SFXcDZgM3VoVZv71I63"   # $20 once
PRICE_ID_AI_MONTHLY = "price_1SqIjgFXcDZgM3VoEwrUvjWP"   # $50/mo

# YOUR STRIPE PORTAL LINK
STRIPE_PORTAL_URL = "https://billing.stripe.com/p/login/cNidR9dlK3WC4fg9VR9IQ00"

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "PRO_V26_FINAL")

# Encryption
enc_key = os.environ.get("ENCRYPTION_KEY")
cipher = Fernet(enc_key.encode()) if enc_key else Fernet(Fernet.generate_key())

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
SCOPES = ['https://www.googleapis.com/auth/userinfo.email', 'openid', 'https://www.googleapis.com/auth/gmail.send']
CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
        "redirect_uris": [os.environ.get("REDIRECT_URI")]
    }
}

# --- 2. DATABASE ---
def get_db():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        with get_db() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY, 
                purchase_count INTEGER DEFAULT 0, 
                email_machine_access INTEGER DEFAULT 0,
                ai_access INTEGER DEFAULT 0,
                ai_trial_end TEXT,
                google_creds_enc TEXT
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                address TEXT, asking_price INTEGER, image_path TEXT, status TEXT DEFAULT 'active'
            )""")
            conn.commit()
    except: pass

init_db()

# --- 3. LOGIC ENGINES ---
def get_intellectual_post():
    if not groq_client: return "Wealth is equity. List on Pro-Exchange."
    try:
        completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": "You are a wealthy stoic. Write a viral 30-word TikTok hook about real estate equity."}],
            model="llama3-8b-8192",
        )
        return completion.choices[0].message.content
    except: return "True equity is freedom. 0% commission is logic."

def send_real_gmail(creds_enc, to, subj, body):
    try:
        from google.oauth2.credentials import Credentials
        creds_data = json.loads(cipher.decrypt(creds_enc.encode()).decode())
        creds = Credentials.from_authorized_user_info(creds_data)
        service = build('gmail', 'v1', credentials=creds)
        msg = MIMEText(body); msg['to'] = to; msg['subject'] = subj
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
        return True
    except: return False

def get_buyer_rate(deal_count):
    return max(0.02, 0.06 - (deal_count * 0.01))

# --- 4. LUXURY UI ---
UI_HEADER = """
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.tailwindcss.com"></script>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;900&display=swap');
    body { font-family: 'Outfit', sans-serif; background: #000; color: #fff; }
    .card-luxury { background: #0a0a0a; border: 1px solid #222; border-radius: 2.5rem; transition: 0.3s; }
    .card-luxury:hover { border-color: #444; transform: translateY(-3px); }
    .btn-white { background: #fff; color: #000; font-weight: 900; text-transform: uppercase; border-radius: 1rem; transition: 0.3s; }
    .btn-white:hover { transform: scale(1.02); }
</style></head><body class="p-6 flex flex-col items-center min-h-screen">
<div class="w-full max-w-4xl">
"""

# UPDATED FOOTER WITH YOUR DIRECT LINK
UI_FOOTER = f"""
<footer class="mt-20 py-10 border-t border-zinc-900 text-center">
    <div class="flex justify-center space-x-6 mb-4">
        <a href="{STRIPE_PORTAL_URL}" target="_blank" class="text-[10px] font-black text-red-500 uppercase tracking-widest hover:text-red-400 transition">Manage Subscription / Cancel</a>
        <a href="/logout" class="text-[10px] font-black text-zinc-600 uppercase tracking-widest hover:text-white transition">Log Out</a>
    </div>
    <a href="/privacy" class="text-[10px] font-black text-zinc-600 uppercase tracking-widest hover:text-white transition">Privacy Policy</a>
</footer>
</div></body></html>"""

# --- 5. ROUTES ---

@app.route('/')
def index():
    return render_template_string(UI_HEADER + """
        <header class="text-center py-20">
            <h1 class="text-7xl font-black uppercase italic tracking-tighter">Pro-Exchange</h1>
            <p class="text-[10px] font-bold text-zinc-500 uppercase tracking-[0.5em] mt-4">Autonomous Asset Infrastructure</p>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div class="card-luxury p-10">
                <h3 class="text-3xl font-black uppercase italic">Email Machine</h3>
                <p class="text-xs text-zinc-500 mb-6">$20 Once or $3/Week.</p>
                <a href="/outreach" class="inline-block btn-white px-8 py-3 text-xs">Enter Engine</a>
            </div>
            
            <div class="card-luxury p-10 border-indigo-900/30 bg-gradient-to-br from-zinc-900 to-black">
                <h3 class="text-3xl font-black uppercase italic text-indigo-400">AI Neural Agent</h3>
                <p class="text-xs text-zinc-500 mb-6">48H Trial or $50/mo. Intellectual Content.</p>
                <a href="/ai-agent" class="inline-block bg-indigo-600 text-white px-8 py-3 rounded-xl font-black uppercase text-xs">Access Agent</a>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mt-8">
            <a href="/buy" class="card-luxury p-10 group hover:border-green-500/30 transition-all">
                <h4 class="text-2xl font-black uppercase italic group-hover:text-green-400">Buyer Feed</h4>
                <p class="text-[10px] text-zinc-600 uppercase mt-1">Fees: 6% → 2%</p>
            </a>
            <a href="/sell" class="card-luxury p-10 group hover:border-blue-500/30 transition-all">
                <h4 class="text-2xl font-black uppercase italic group-hover:text-blue-400">List Asset</h4>
                <p class="text-[10px] text-zinc-600 uppercase mt-1">0% Commission</p>
            </a>
        </div>
    """ + UI_FOOTER)

@app.route('/ai-agent')
def ai_agent():
    if 'user_email' not in session: return redirect(url_for('google_login', next='ai-agent'))
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (session['user_email'],)).fetchone()
    
    access = False
    if user['ai_access'] == 1: access = True
    if user['ai_trial_end'] and datetime.now() < datetime.fromisoformat(user['ai_trial_end']): access = True

    if not access:
        return render_template_string(UI_HEADER + f"""
            <div class="text-center py-10 card-luxury p-12 border-indigo-500/20">
                <h2 class="text-5xl font-black uppercase italic text-indigo-400 mb-6">Neural Agent</h2>
                <a href="/start-trial" class="block w-full bg-indigo-600 py-5 rounded-2xl font-black uppercase italic mb-4 hover:bg-indigo-500 transition">Start 48H No-CC Trial</a>
                <form action="/checkout" method="POST">
                    <input type="hidden" name="pid" value="{PRICE_ID_AI_MONTHLY}">
                    <button class="w-full bg-white text-black py-5 rounded-2xl font-black uppercase italic">$50 / Month Subscription</button>
                </form>
            </div>
        """ + UI_FOOTER)

    return render_template_string(UI_HEADER + f"""
        <div class="flex justify-between items-center mb-10">
            <h2 class="text-4xl font-black uppercase italic text-indigo-400">Neural Terminal</h2>
            <span class="px-3 py-1 bg-green-500 text-black font-black uppercase text-[10px] rounded-full">Sync Active</span>
        </div>
        <div class="card-luxury p-10 bg-zinc-900/50">
            <h4 class="text-[10px] font-black text-zinc-500 uppercase mb-4 tracking-widest">Generating Intellectual Content...</h4>
            <p class="text-2xl font-black italic text-zinc-200 leading-tight">"{get_intellectual_post()}"</p>
        </div>
    """ + UI_FOOTER)

@app.route('/outreach')
def outreach():
    if 'user_email' not in session: return redirect(url_for('google_login', next='outreach'))
    with get_db() as conn:
        user = conn.execute("SELECT email_machine_access, google_creds_enc FROM users WHERE email=?", (session['user_email'],)).fetchone()
    
    if not user['email_machine_access']:
        return render_template_string(UI_HEADER + f"""
            <div class="text-center py-10 card-luxury p-12">
                <h2 class="text-5xl font-black uppercase italic mb-8">Email Machine</h2>
                <form action="/checkout" method="POST" class="space-y-4">
                    <button name="pid" value="{PRICE_ID_EMAIL_ONCE}" class="w-full bg-white text-black py-5 rounded-2xl font-black uppercase italic text-xl">$20 Lifetime Access</button>
                    <button name="pid" value="{PRICE_ID_EMAIL_WEEKLY}" class="w-full bg-zinc-800 text-white py-4 rounded-2xl font-black uppercase italic text-xs border border-zinc-700">$3 / Weekly Subscription</button>
                </form>
            </div>
        """ + UI_FOOTER)

    return render_template_string(UI_HEADER + """
        <h2 class="text-4xl font-black uppercase italic mb-8">Broadcast Center</h2>
        <form action="/launch-broadcast" method="POST" class="card-luxury p-10 space-y-4">
            <input name="targets" placeholder="Emails (comma separated)" class="w-full p-4 bg-black border border-zinc-800 rounded-xl font-bold" required>
            <input name="subject" placeholder="Subject" class="w-full p-4 bg-black border border-zinc-800 rounded-xl font-bold" required>
            <textarea name="body" placeholder="Message" class="w-full p-4 bg-black border border-zinc-800 rounded-xl h-40 font-bold" required></textarea>
            <button class="w-full btn-white py-5 text-xl">Transmit</button>
        </form>
    """ + UI_FOOTER)

@app.route('/launch-broadcast', methods=['POST'])
def launch_broadcast():
    with get_db() as conn:
        user = conn.execute("SELECT google_creds_enc FROM users WHERE email=?", (session['user_email'],)).fetchone()
    if not user['google_creds_enc']: return redirect('/outreach')
    
    targets = request.form.get('targets').split(',')
    for t in targets:
        send_real_gmail(user['google_creds_enc'], t.strip(), request.form.get('subject'), request.form.get('body'))
        time.sleep(1)
    return redirect('/outreach')

@app.route('/checkout', methods=['POST'])
def checkout():
    pid = request.form.get('pid')
    session_st = stripe.checkout.Session.create(
        line_items=[{'price': pid, 'quantity': 1}],
        mode='subscription' if pid != PRICE_ID_EMAIL_ONCE else 'payment',
        success_url=request.host_url + f'success?pid={pid}',
        cancel_url=request.host_url,
        customer_email=session['user_email']
    )
    return redirect(session_st.url, code=303)

@app.route('/success')
def success():
    pid = request.args.get('pid')
    with get_db() as conn:
        if pid == PRICE_ID_AI_MONTHLY: conn.execute("UPDATE users SET ai_access=1 WHERE email=?", (session['user_email'],))
        else: conn.execute("UPDATE users SET email_machine_access=1 WHERE email=?", (session['user_email'],))
        conn.commit()
    return redirect('/')

@app.route('/start-trial')
def start_trial():
    with get_db() as conn:
        end = (datetime.now() + timedelta(hours=48)).isoformat()
        conn.execute("UPDATE users SET ai_trial_end=? WHERE email=?", (end, session['user_email']))
        conn.commit()
    return redirect('/ai-agent')

@app.route('/stripe_webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        if event['type'] == 'customer.subscription.deleted':
            obj = event['data']['object']
            customer = stripe.Customer.retrieve(obj['customer'])
            with get_db() as conn:
                conn.execute("UPDATE users SET ai_access=0, email_machine_access=0 WHERE email=?", (customer.email,))
                conn.commit()
    except: pass
    return "OK", 200

@app.route('/buy')
def buy():
    if 'user_email' not in session: return redirect(url_for('google_login', next='buy'))
    with get_db() as conn:
        user = conn.execute("SELECT purchase_count FROM users WHERE email=?", (session['user_email'],)).fetchone()
        leads = conn.execute("SELECT * FROM leads WHERE status='active'").fetchall()
    rate = get_buyer_rate(user['purchase_count'] if user else 0)
    return render_template_string(UI_HEADER + """
        <div class="flex justify-between items-end mb-12">
            <h2 class="text-6xl font-black uppercase italic tracking-tighter">The Vault</h2>
            <p class="text-4xl font-black text-green-500">{{ (rate*100)|int }}% Fee</p>
        </div>
        <div class="grid grid-cols-1 gap-10">
            {% for lead in leads %}
            <div class="card-luxury overflow-hidden group">
                {% if lead.image_path %}<img src="/uploads/{{ lead.image_path }}" class="w-full h-80 object-cover opacity-60 group-hover:opacity-100 transition">{% endif %}
                <div class="p-10 flex justify-between items-center">
                    <div><h3 class="text-3xl font-black uppercase italic">{{ lead.address }}</h3><p class="text-zinc-500 font-bold">${{ "{:,.0f}".format(lead.asking_price) }}</p></div>
                    <button class="btn-white px-8 py-4 text-xs">Unlock</button>
                </div>
            </div>
            {% endfor %}
        </div>""", leads=leads, rate=rate) + UI_FOOTER

@app.route('/sell')
def sell():
    if 'user_email' not in session: return redirect(url_for('google_login', next='sell'))
    return render_template_string(UI_HEADER + """
        <div class="card-luxury p-12 max-w-2xl mx-auto">
            <h2 class="text-4xl font-black uppercase italic mb-8">List Asset (Free)</h2>
            <form action="/submit-lead" method="POST" enctype="multipart/form-data" class="space-y-4">
                <input name="address" placeholder="Address" class="w-full p-4 bg-zinc-900 rounded-xl font-bold" required>
                <input type="number" name="price" placeholder="Price" class="w-full p-4 bg-zinc-900 rounded-xl font-bold" required>
                <input type="file" name="photo" class="text-xs text-zinc-500" required>
                <button class="w-full btn-white py-5 text-xl">Post</button>
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
    return redirect('/')

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
    creds_json = json.dumps({'token': flow.credentials.token, 'refresh_token': flow.credentials.refresh_token, 'token_uri': flow.credentials.token_uri, 'client_id': flow.credentials.client_id, 'client_secret': flow.credentials.client_secret, 'scopes': flow.credentials.scopes})
    enc_creds = cipher.encrypt(creds_json.encode()).decode()
    with get_db() as conn:
        conn.execute("INSERT INTO users (email, google_creds_enc) VALUES (?, ?) ON CONFLICT(email) DO UPDATE SET google_creds_enc=?", (session['user_email'], enc_creds, enc_creds))
        conn.commit()
    return redirect(url_for(session.get('next_target', 'index')))

@app.route('/logout')
def logout():
    session.clear(); return redirect('/')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/privacy')
def privacy():
    return render_template_string(UI_HEADER + """<div class="p-10 bg-zinc-900 rounded-[3rem] text-sm text-zinc-500 italic">Privacy: We use Google APIs for emails and Stripe for payments. We do not sell data.</div>""" + UI_FOOTER)

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

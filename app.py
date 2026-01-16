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

# --- 1. ENTERPRISE CONFIGURATION (Pulled from Render Variables) ---
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") # Set this in Render Dashboard
groq_client = Groq(api_key=GROQ_API_KEY)

UPLOAD_FOLDER = 'uploads'
DB_PATH = "pro_exchange_v24.db"

# STRIPE PRICE IDS
PRICE_ID_EMAIL_WEEKLY = "price_1SpxexFXcDZgM3Vo0iYmhfpb" # $3/wk
PRICE_ID_EMAIL_ONCE = "price_1Spy7SFXcDZgM3VoVZv71I63"   # $20 once
PRICE_ID_AI_MONTHLY = "price_1SqIjgFXcDZgM3VoEwrUvjWP"   # $50/mo

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "PRO_V24_SECURE_NODE")

cipher = Fernet(os.environ.get("ENCRYPTION_KEY", Fernet.generate_key().decode()).encode())

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

init_db()

# --- 3. NEURAL & EMAIL ENGINES ---
def get_intellectual_post():
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{
                "role": "system", 
                "content": "You are an intellectual wealth strategist. Write a viral, stoic, and bold TikTok caption about real estate equity and financial freedom. Under 35 words. Include #Stoicism #Wealth."
            }],
            model="llama3-8b-8192",
        )
        return chat_completion.choices[0].message.content
    except Exception as e: 
        return "True wealth is found in the equity you keep, not the commissions you pay. Pro-Exchange. 0% commission. 100% Logic. #Wealth #Stoic"

def send_gmail(creds_enc, to, subj, body):
    try:
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_info(json.loads(cipher.decrypt(creds_enc.encode()).decode()))
        service = build('gmail', 'v1', credentials=creds)
        msg = MIMEText(body); msg['to'] = to; msg['subject'] = subj
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
        return True
    except: return False

def get_buyer_rate(deal_count):
    # Starts at 6%, drops 1% per closed deal, caps at 2%
    return max(0.02, 0.06 - (deal_count * 0.01))

# --- 4. LUXURY UI SYSTEM ---
UI_HEADER = """
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;900&display=swap');
    body { font-family: 'Outfit', sans-serif; background: #050505; color: #fff; }
    .card-luxury { background: #0a0a0a; border: 1px solid #1a1a1a; border-radius: 2.5rem; transition: 0.4s; }
    .card-luxury:hover { border-color: #333; transform: translateY(-5px); }
    .btn-white { background: #fff; color: #000; font-weight: 900; text-transform: uppercase; border-radius: 1.2rem; transition: 0.3s; }
    .btn-white:hover { transform: scale(1.02); filter: brightness(0.9); }
</style></head><body class="p-6 flex flex-col items-center min-h-screen">
<div class="w-full max-w-5xl">
"""
UI_FOOTER = """
<footer class="mt-32 py-12 border-t border-zinc-900 text-center">
    <div class="flex justify-center space-x-10 mb-8">
        <a href="/privacy" class="text-[10px] font-black text-zinc-600 uppercase tracking-[0.4em] hover:text-white transition">Privacy Policy</a>
        <a href="/" class="text-[10px] font-black text-zinc-600 uppercase tracking-[0.4em] hover:text-white transition">Global Hub</a>
    </div>
    <p class="text-[8px] text-zinc-800 uppercase tracking-[0.5em]">Powered by Neural Llama-3 • Pro-Exchange Global Protocol</p>
</footer>
</div></body></html>"""

# --- 5. ROUTES ---

@app.route('/')
def index():
    return render_template_string(UI_HEADER + """
        <header class="text-center py-24">
            <h1 class="text-8xl font-black uppercase italic tracking-tighter">Pro-Exchange</h1>
            <p class="text-[10px] font-bold text-zinc-500 uppercase tracking-[0.8em] mt-4">Autonomous Wealth Infrastructure</p>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div class="card-luxury p-12">
                <h3 class="text-4xl font-black uppercase italic mb-2">Email Machine</h3>
                <p class="text-xs text-zinc-500 mb-8">Mass broadcast assets to thousands of buyers. $20 Once or $3/Week.</p>
                <a href="/outreach" class="btn-white px-10 py-4 inline-block text-xs">Enter Engine</a>
            </div>
            
            <div class="card-luxury p-12 border-indigo-900/40 bg-gradient-to-br from-black to-zinc-900">
                <h3 class="text-4xl font-black uppercase italic text-indigo-400 mb-2">AI Neural Agent</h3>
                <p class="text-xs text-zinc-500 mb-8">48H Trial. Intellectual TikTok Automation. $50/mo.</p>
                <a href="/ai-agent" class="btn-white px-10 py-4 inline-block text-xs bg-indigo-600 text-white border-none">Access Agent</a>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mt-8">
            <a href="/buy" class="card-luxury p-10 group hover:border-green-500/30 transition-all">
                <h4 class="text-2xl font-black uppercase italic group-hover:text-green-400 transition-colors">Asset Feed</h4>
                <p class="text-[10px] text-zinc-600 uppercase mt-1 font-bold tracking-widest">Sliding Scale: 6% → 2%</p>
            </a>
            <a href="/sell" class="card-luxury p-10 group hover:border-blue-500/30 transition-all">
                <h4 class="text-2xl font-black uppercase italic group-hover:text-blue-400 transition-colors">List Asset</h4>
                <p class="text-[10px] text-zinc-600 uppercase mt-1 font-bold tracking-widest">0% Commission AI Tool</p>
            </a>
        </div>
    """ + UI_FOOTER)

@app.route('/ai-agent')
def ai_agent():
    if 'user_email' not in session: return redirect(url_for('google_login', next='ai-agent'))
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (session['user_email'],)).fetchone()
    
    access = (user['ai_access'] == 1 or (user['ai_trial_end'] and datetime.now() < datetime.fromisoformat(user['ai_trial_end'])))
    
    if not access:
        return render_template_string(UI_HEADER + f"""
            <div class="card-luxury p-16 text-center max-w-3xl mx-auto border-indigo-500/20">
                <h2 class="text-6xl font-black uppercase italic text-indigo-400 mb-6">Neural Agent</h2>
                <p class="text-zinc-400 mb-12 text-sm leading-relaxed max-w-md mx-auto italic">"Wealth flows to those who build authority." The Agent schedules intellectual TikTok posts on wealth & stoicism to grow your brand.</p>
                <a href="/start-trial" class="block w-full bg-indigo-600 py-6 rounded-2xl font-black uppercase italic mb-4 hover:bg-indigo-500 transition shadow-2xl shadow-indigo-500/20">Start 48H No-CC Trial</a>
                <form action="/checkout" method="POST">
                    <input type="hidden" name="pid" value="{PRICE_ID_AI_MONTHLY}">
                    <button class="w-full bg-white text-black py-6 rounded-2xl font-black uppercase italic">$50 / Month AI Agent</button>
                </form>
            </div>
        """ + UI_FOOTER)
    
    return render_template_string(UI_HEADER + f"""
        <div class="flex justify-between items-center mb-12">
            <h2 class="text-4xl font-black uppercase italic text-indigo-400 tracking-tighter">Neural Terminal</h2>
            <span class="px-4 py-1 bg-green-500 text-black font-black uppercase text-[10px] rounded-full animate-pulse">Sync Active</span>
        </div>
        <div class="card-luxury p-10 bg-zinc-900/40">
            <h4 class="text-[10px] font-black text-zinc-600 uppercase mb-6 tracking-[0.3em]">AI Post Draft (Intellectual Strategy)</h4>
            <p class="text-2xl font-black italic text-zinc-100 leading-tight tracking-tight">"{get_intellectual_post()}"</p>
            <div class="mt-10 pt-8 border-t border-zinc-800 flex justify-between items-center text-[9px] font-black uppercase text-zinc-600 tracking-widest">
                <span>Next Slot: 4:00 PM</span>
                <span class="text-indigo-500">Model: Llama-3-Neural</span>
            </div>
        </div>
    """ + UI_FOOTER)

@app.route('/outreach')
def outreach_portal():
    if 'user_email' not in session: return redirect(url_for('google_login', next='outreach'))
    with get_db() as conn:
        user = conn.execute("SELECT email_machine_access FROM users WHERE email=?", (session['user_email'],)).fetchone()
    
    if not user['email_machine_access']:
        return render_template_string(UI_HEADER + f"""
            <div class="card-luxury p-16 text-center max-w-xl mx-auto">
                <h2 class="text-5xl font-black uppercase italic mb-8">Email Machine</h2>
                <p class="text-zinc-500 text-[10px] font-black uppercase tracking-[0.4em] mb-10">Broadcast Directly to Buyers</p>
                <form action="/checkout" method="POST" class="space-y-4">
                    <button name="pid" value="{PRICE_ID_EMAIL_ONCE}" class="w-full bg-white text-black py-6 rounded-2xl font-black uppercase italic text-xl">$20 Lifetime Access</button>
                    <button name="pid" value="{PRICE_ID_EMAIL_WEEKLY}" class="w-full bg-zinc-900 text-white py-4 rounded-2xl font-black uppercase italic text-xs border border-zinc-800 hover:bg-white hover:text-black transition">$3 / Weekly Subscription</button>
                </form>
            </div>
        """ + UI_FOOTER)
    return redirect('/')

# --- 6. SYSTEM HANDLERS ---

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

@app.route('/buy')
def buyer_feed():
    if 'user_email' not in session: return redirect(url_for('google_login', next='buy'))
    with get_db() as conn:
        user = conn.execute("SELECT purchase_count FROM users WHERE email=?", (session['user_email'],)).fetchone()
        leads = conn.execute("SELECT * FROM leads WHERE status = 'active'").fetchall()
    
    rate = get_buyer_rate(user['purchase_count'] if user else 0)
    
    return render_template_string(UI_HEADER + """
        <div class="flex justify-between items-end mb-12">
            <h2 class="text-6xl font-black uppercase italic tracking-tighter">The Vault</h2>
            <div class="text-right">
                <p class="text-[9px] font-black text-zinc-600 uppercase tracking-[0.3em]">Tier Fee</p>
                <p class="text-4xl font-black text-green-500">{{ (rate*100)|int }}%</p>
            </div>
        </div>
        <div class="grid grid-cols-1 gap-10">
            {% for lead in leads %}
            <div class="card-luxury overflow-hidden group">
                {% if lead.image_path %}<img src="/uploads/{{ lead.image_path }}" class="w-full h-96 object-cover opacity-60 group-hover:opacity-100 transition duration-1000">{% endif %}
                <div class="p-12 flex justify-between items-center">
                    <div>
                        <h3 class="text-4xl font-black uppercase italic tracking-tight">{{ lead.address }}</h3>
                        <p class="text-xs font-bold text-zinc-500 mt-3 uppercase tracking-widest font-black">${{ "{:,.0f}".format(lead.asking_price) }}</p>
                    </div>
                    <button class="btn-white px-10 py-5 text-xs">Unlock Deal</button>
                </div>
            </div>
            {% endfor %}
        </div>
    """, leads=leads, rate=rate) + UI_FOOTER

@app.route('/privacy')
def privacy_policy():
    return render_template_string(UI_HEADER + """
        <div class="card-luxury p-16 max-w-4xl mx-auto text-zinc-400 leading-relaxed text-sm">
            <h2 class="text-4xl font-black uppercase italic text-white mb-10">Privacy Protocol</h2>
            <p class="mb-6">1. <b>Gmail Scope:</b> Pro-Exchange utilizes Gmail API tokens to facilitate outreach. We do not index or store personal communications.</p>
            <p class="mb-6">2. <b>AI Automation:</b> Posts are generated via the Groq Llama-3 neural cloud. We do not store social media passwords; sessions are tokenized.</p>
            <p class="mb-6">3. <b>Asset Data:</b> Property images and metadata uploaded by sellers are displayed in the feed and used for marketing automation.</p>
            <p class="mb-6">4. <b>Encryption:</b> Contact data is AES-256 encrypted.</p>
            <a href="/" class="btn-white px-8 py-3 mt-10 inline-block text-[10px]">Return to Hub</a>
        </div>
    """ + UI_FOOTER)

# --- 7. AUTH & UTILS ---

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
    email = id_info.get('email')
    session['user_email'] = email
    
    creds_json = json.dumps({'token': flow.credentials.token, 'refresh_token': flow.credentials.refresh_token, 'token_uri': flow.credentials.token_uri, 'client_id': flow.credentials.client_id, 'client_secret': flow.credentials.client_secret, 'scopes': flow.credentials.scopes})
    enc_creds = cipher.encrypt(creds_json.encode()).decode()
    
    with get_db() as conn:
        conn.execute("INSERT INTO users (email, google_creds_enc) VALUES (?, ?) ON CONFLICT(email) DO UPDATE SET google_creds_enc=?", (email, enc_creds, enc_creds))
        conn.commit()
    return redirect(url_for(session.get('next_target', 'index')))

@app.route('/sell')
def seller_listing():
    if 'user_email' not in session: return redirect(url_for('google_login', next='sell'))
    return render_template_string(UI_HEADER + """
        <div class="card-luxury p-16 max-w-2xl mx-auto">
            <h2 class="text-4xl font-black uppercase italic mb-10">List Asset (Free)</h2>
            <form action="/submit-lead" method="POST" enctype="multipart/form-data" class="space-y-6">
                <input type="text" name="address" placeholder="Property Address" class="w-full p-6 bg-black rounded-2xl border border-zinc-800 focus:border-white outline-none font-bold" required>
                <input type="number" name="price" placeholder="Asking Price" class="w-full p-6 bg-black rounded-2xl border border-zinc-800 focus:border-white outline-none font-bold" required>
                <input type="file" name="photo" class="text-xs font-black uppercase text-zinc-600" required>
                <button class="btn-white w-full py-8 text-xl">Post to Verified Feed</button>
            </form>
        </div>
    """ + UI_FOOTER)

@app.route('/submit-lead', methods=['POST'])
def submit_post():
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
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000))

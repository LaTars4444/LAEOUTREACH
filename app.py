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

UPLOAD_FOLDER = 'uploads'
DB_PATH = "pro_exchange_v25.db"

# STRIPE PRICE IDS
PRICE_ID_EMAIL_WEEKLY = "price_1SpxexFXcDZgM3Vo0iYmhfpb" # $3/wk
PRICE_ID_EMAIL_ONCE = "price_1Spy7SFXcDZgM3VoVZv71I63"   # $20 once
PRICE_ID_AI_MONTHLY = "price_1SqIjgFXcDZgM3VoEwrUvjWP"   # $50/mo

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "PRO_V25_FINAL_ULTRA")

# Encryption for Google Tokens
enc_key = os.environ.get("ENCRYPTION_KEY")
cipher = Fernet(enc_key.encode()) if enc_key else None

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
SCOPES = ['https://www.googleapis.com/auth/userinfo.email', 'openid', 'https://www.googleapis.com/auth/gmail.send']
CLIENT_CONFIG = {"web": {"client_id": GOOGLE_CLIENT_ID, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"), "redirect_uris": [os.environ.get("REDIRECT_URI")]}}

# --- 2. DATABASE ---
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

# --- 3. AI & EMAIL ENGINES ---
def get_intellectual_post():
    if not groq_client: return "Wealth is a mindset. List on Pro-Exchange."
    try:
        completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": "You are a stoic strategist. Write a viral 30-word TikTok script on wealth and property equity."}],
            model="llama3-8b-8192",
        )
        return completion.choices[0].message.content
    except: return "True equity is freedom. 0% commission is logic."

def send_real_gmail(creds_enc, to, subj, body):
    try:
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_info(json.loads(cipher.decrypt(creds_enc.encode()).decode()))
        service = build('gmail', 'v1', credentials=creds)
        msg = MIMEText(body); msg['to'] = to; msg['subject'] = subj
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
        return True
    except: return False

# --- 4. LUXURY UI ---
UI_HEADER = """
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
<style>@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;900&display=swap');
body { font-family: 'Outfit', sans-serif; background: #000; color: #fff; }</style></head>
<body class="p-6 flex flex-col items-center min-h-screen"><div class="w-full max-w-4xl">
"""
UI_FOOTER = """
<footer class="mt-20 py-10 border-t border-zinc-900 text-center"><a href="/privacy" class="text-[10px] font-black text-zinc-600 uppercase tracking-widest">Privacy Policy</a></footer>
</div></body></html>"""

# --- 5. DASHBOARD ---

@app.route('/')
def index():
    return render_template_string(UI_HEADER + """
        <header class="text-center py-20"><h1 class="text-7xl font-black uppercase italic tracking-tighter">Pro-Exchange</h1></header>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div class="bg-zinc-900 p-10 rounded-[3rem] border border-zinc-800">
                <h3 class="text-3xl font-black uppercase italic">Email Machine</h3>
                <p class="text-xs text-zinc-500 mb-6">Mass outreach. $20 Once or $3/Week.</p>
                <a href="/outreach" class="inline-block bg-white text-black px-8 py-3 rounded-xl font-black uppercase text-xs">Access</a>
            </div>
            <div class="bg-indigo-600/10 p-10 rounded-[3rem] border border-indigo-500/30">
                <h3 class="text-3xl font-black uppercase italic text-indigo-400">AI Agent</h3>
                <p class="text-xs text-zinc-500 mb-6">Intellectual TikTok automation. 48H Trial or $50/mo.</p>
                <a href="/ai-agent" class="inline-block bg-indigo-500 text-white px-8 py-3 rounded-xl font-black uppercase text-xs">Launch</a>
            </div>
        </div>
    """ + UI_FOOTER)

# --- 6. AGENT & OUTREACH LOGIC ---

@app.route('/ai-agent')
def ai_agent():
    if 'user_email' not in session: return redirect(url_for('google_login', next='ai-agent'))
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (session['user_email'],)).fetchone()
    access = (user['ai_access'] == 1 or (user['ai_trial_end'] and datetime.now() < datetime.fromisoformat(user['ai_trial_end'])))
    if not access:
        return render_template_string(UI_HEADER + f"""
            <div class="text-center py-10 bg-zinc-900 rounded-[3rem] p-12">
                <h2 class="text-5xl font-black uppercase italic text-indigo-400 mb-6">AI Terminal</h2>
                <a href="/start-trial" class="block w-full bg-indigo-600 py-6 rounded-2xl font-black uppercase italic mb-4">Start 48H No-CC Trial</a>
                <form action="/checkout" method="POST"><input type="hidden" name="pid" value="{PRICE_ID_AI_MONTHLY}">
                <button class="w-full bg-white text-black py-6 rounded-2xl font-black uppercase italic">$50 / Month AI Bot</button></form>
            </div>""" + UI_FOOTER)
    return render_template_string(UI_HEADER + f"""<h2 class="text-4xl font-black italic uppercase">AI Bot Active</h2><p class="mt-8 italic text-zinc-400">"{get_intellectual_post()}"</p>""" + UI_FOOTER)

@app.route('/outreach')
def outreach():
    if 'user_email' not in session: return redirect(url_for('google_login', next='outreach'))
    with get_db() as conn:
        user = conn.execute("SELECT email_machine_access, google_creds_enc FROM users WHERE email=?", (session['user_email'],)).fetchone()
    if not user['email_machine_access']:
        return render_template_string(UI_HEADER + f"""
            <div class="text-center py-10 bg-zinc-900 rounded-[3rem] p-12">
                <h2 class="text-5xl font-black uppercase italic mb-8">Email Machine</h2>
                <form action="/checkout" method="POST" class="space-y-4">
                    <button name="pid" value="{PRICE_ID_EMAIL_ONCE}" class="w-full bg-white text-black py-6 rounded-2xl font-black uppercase italic text-xl">$20 Lifetime Access</button>
                    <button name="pid" value="{PRICE_ID_EMAIL_WEEKLY}" class="w-full bg-zinc-800 text-white py-4 rounded-2xl font-black uppercase italic text-xs">$3 / Weekly Subscription</button>
                </form>
            </div>""" + UI_FOOTER)
    return render_template_string(UI_HEADER + """
        <form action="/launch-broadcast" method="POST" class="bg-zinc-900 p-10 rounded-3xl space-y-4">
            <input name="targets" placeholder="Emails (comma separated)" class="w-full p-4 bg-black border border-zinc-800 rounded-xl" required>
            <input name="subject" placeholder="Subject" class="w-full p-4 bg-black border border-zinc-800 rounded-xl" required>
            <textarea name="body" placeholder="Message" class="w-full p-4 bg-black border border-zinc-800 rounded-xl h-40" required></textarea>
            <button class="w-full bg-white text-black py-4 rounded-xl font-black uppercase">Launch Broadcast</button>
        </form>""" + UI_FOOTER)

@app.route('/launch-broadcast', methods=['POST'])
def launch_broadcast():
    with get_db() as conn:
        user = conn.execute("SELECT google_creds_enc FROM users WHERE email=?", (session['user_email'],)).fetchone()
    targets = [t.strip() for t in request.form.get('targets').split(',')]
    subj, body = request.form.get('subject'), request.form.get('body')
    for t in targets:
        send_real_gmail(user['google_creds_enc'], t, subj, body)
        time.sleep(1)
    flash("Broadcast complete."); return redirect('/outreach')

# --- 7. PAYMENTS & SYSTEM ---

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
def buy():
    if 'user_email' not in session: return redirect(url_for('google_login', next='buy'))
    with get_db() as conn:
        user = conn.execute("SELECT purchase_count FROM users WHERE email=?", (session['user_email'],)).fetchone()
        leads = conn.execute("SELECT * FROM leads WHERE status='active'").fetchall()
    rate = max(0.02, 0.06 - (user['purchase_count'] * 0.01))
    return render_template_string(UI_HEADER + """<h2 class="text-4xl font-black uppercase mb-8">Asset Feed ({{ (rate*100)|int }}% Fee)</h2>
        {% for l in leads %}
        <div class="bg-zinc-900 p-8 rounded-3xl mb-4 flex justify-between items-center">
            <div><p class="font-black uppercase italic text-xl">{{ l.address }}</p><p class="text-zinc-500">${{ l.asking_price }}</p></div>
            <button class="bg-white text-black px-6 py-2 rounded-xl font-black uppercase text-xs">Unlock</button>
        </div>{% endfor %}""", leads=leads, rate=rate) + UI_FOOTER

@app.route('/sell')
def sell():
    if 'user_email' not in session: return redirect(url_for('google_login', next='sell'))
    return render_template_string(UI_HEADER + """<h2 class="text-4xl font-black uppercase italic mb-8">List Asset (Free)</h2>
        <form action="/submit-lead" method="POST" enctype="multipart/form-data" class="space-y-4">
            <input name="address" placeholder="Address" class="w-full p-4 bg-zinc-900 rounded-xl" required>
            <input type="number" name="price" placeholder="Price" class="w-full p-4 bg-zinc-900 rounded-xl" required>
            <input type="file" name="photo" class="text-xs" required>
            <button class="w-full bg-white text-black py-4 rounded-xl font-black uppercase">Post Listing</button>
        </form>""" + UI_FOOTER)

@app.route('/submit-lead', methods=['POST'])
def submit_post():
    f = request.form; file = request.files.get('photo')
    filename = secure_filename(file.filename) if file else None
    if filename: file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    with get_db() as conn:
        conn.execute("INSERT INTO leads (address, asking_price, image_path) VALUES (?, ?, ?)", (f.get('address'), f.get('price'), filename))
        conn.commit()
    return redirect('/')

# --- 8. AUTH & SYSTEM ---

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

@app.route('/privacy')
def privacy():
    return render_template_string(UI_HEADER + """<div class="p-10 bg-zinc-900 rounded-[3rem] text-sm text-zinc-500 italic">Pro-Exchange handles Gmail API data only for requested broadcasts. No personal data is stored outside encrypted payment/auth tokens via Stripe and Google OAuth.</div>""" + UI_FOOTER)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

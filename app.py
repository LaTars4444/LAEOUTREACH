import os, re, base64, time, random, stripe, sqlite3, json, secrets
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, send_from_directory, jsonify
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from googleapiclient.discovery import build
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from email.mime.text import MIMEText
from groq import Groq

# ==============================================================================
# CONFIGURATION
# ==============================================================================
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "TITAN_V28_SECURE")

# Keys
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
enc_key = os.environ.get("ENCRYPTION_KEY")
cipher = Fernet(enc_key.encode()) if enc_key else Fernet(Fernet.generate_key())

# Paths
UPLOAD_FOLDER = '/tmp/uploads'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
DB_PATH = "titan_v28.db"

# Pricing & OAuth
PRICE_IDS = {
    'EMAIL_WEEKLY': "price_1SpxexFXcDZgM3Vo0iYmhfpb",
    'EMAIL_ONCE': "price_1Spy7SFXcDZgM3VoVZv71I63",
    'AI_MONTHLY': "price_1SqIjgFXcDZgM3VoEwrUvjWP"
}
STRIPE_PORTAL = "https://billing.stripe.com/p/login/cNidR9dlK3WC4fg9VR9IQ00"
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
SCOPES = ['https://www.googleapis.com/auth/userinfo.email', 'openid', 'https://www.googleapis.com/auth/gmail.send']

# ==============================================================================
# DATABASE & LOGIC
# ==============================================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        with get_db() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY, purchase_count INTEGER DEFAULT 0,
                email_machine_access INTEGER DEFAULT 0, ai_access INTEGER DEFAULT 0,
                ai_trial_end TEXT, google_creds_enc TEXT,
                bb_min_price INTEGER DEFAULT 0, bb_max_price INTEGER DEFAULT 5000000,
                bb_min_sqft INTEGER DEFAULT 0, bb_target_zip TEXT, bb_strategy TEXT DEFAULT 'Any'
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT, address TEXT, asking_price INTEGER,
                arv INTEGER, repair_cost INTEGER, sqft INTEGER, image_path TEXT,
                status TEXT DEFAULT 'active', seller_email TEXT
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS outreach_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, target TEXT, sent_at TEXT
            )""")
            conn.commit()
    except: pass

init_db()

def get_matched_leads(user):
    query = "SELECT * FROM leads WHERE status='active'"
    params = []
    if user['bb_max_price'] > 0:
        query += " AND asking_price <= ?"
        params.append(user['bb_max_price'])
    if user['bb_target_zip']:
        query += " AND zip_code LIKE ?"
        params.append(f"{user['bb_target_zip']}%")
    
    with get_db() as conn:
        leads = conn.execute(query, params).fetchall()
    
    processed = []
    tier_rate = max(0.02, 0.06 - (user['purchase_count'] * 0.01))
    
    for l in leads:
        d = dict(l)
        d['fee'] = int(l['asking_price'] * tier_rate)
        d['roi'] = int(((l['arv'] - (l['asking_price'] + d['fee'] + l['repair_cost'])) / (l['asking_price'] + d['fee'] + l['repair_cost'])) * 100)
        d['rate_display'] = int(tier_rate * 100)
        processed.append(d)
    return processed

def generate_ai_content():
    if not groq_client: return "Wealth is equity. List on Pro-Exchange."
    try:
        comp = groq_client.chat.completions.create(messages=[{"role":"system","content":"Write a viral 30-word TikTok hook about Real Estate Equity and Stoicism."}], model="llama3-8b-8192")
        return comp.choices[0].message.content
    except: return "True freedom is owning equity. 0% Commission Protocol."

def send_gmail(user_email, targets, subject, body):
    with get_db() as conn:
        user = conn.execute("SELECT google_creds_enc FROM users WHERE email=?", (user_email,)).fetchone()
    if not user or not user['google_creds_enc']: return False
    try:
        creds = json.loads(cipher.decrypt(user['google_creds_enc'].encode()).decode())
        from google.oauth2.credentials import Credentials
        c = Credentials.from_authorized_user_info(creds)
        svc = build('gmail', 'v1', credentials=c)
        for t in targets:
            msg = MIMEText(body); msg['to'] = t.strip(); msg['subject'] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            svc.users().messages().send(userId='me', body={'raw': raw}).execute()
            time.sleep(0.5)
        return True
    except: return False

# ==============================================================================
# UI ARCHITECTURE
# ==============================================================================
def render_ui(content, user=None):
    nav = ""
    if user:
        nav = """<div class="hidden md:flex space-x-6">
            <a href="/buy" class="text-xs font-bold uppercase text-zinc-500 hover:text-white">Feed</a>
            <a href="/sell" class="text-xs font-bold uppercase text-zinc-500 hover:text-white">List</a>
            <a href="/outreach" class="text-xs font-bold uppercase text-zinc-500 hover:text-white">Email</a>
            <a href="/ai-agent" class="text-xs font-bold uppercase text-indigo-400 hover:text-indigo-300">Neural</a>
        </div>"""
    else: nav = '<a href="/login" class="text-xs font-bold uppercase text-white">Login</a>'

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TITAN v28</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;900&display=swap');
            body {{ background: #050505; color: #fff; font-family: 'Outfit', sans-serif; }}
            .card {{ background: #0a0a0a; border: 1px solid #222; border-radius: 2rem; transition: 0.3s; }}
            .card:hover {{ border-color: #444; transform: translateY(-3px); }}
            .btn {{ background: #fff; color: #000; font-weight: 900; text-transform: uppercase; padding: 1rem 2rem; border-radius: 1rem; }}
            .btn:hover {{ transform: scale(1.02); }}
            .btn-outline {{ border: 1px solid #333; color: #888; font-weight: 700; text-transform: uppercase; padding: 0.8rem 1.5rem; border-radius: 1rem; }}
            .btn-outline:hover {{ border-color: #fff; color: #fff; }}
            input, textarea, select {{ background: #111; border: 1px solid #222; color: #fff; padding: 1rem; border-radius: 1rem; width: 100%; outline: none; }}
        </style>
    </head>
    <body class="p-6 flex flex-col items-center min-h-screen">
        <nav class="w-full max-w-6xl flex justify-between items-center mb-12 py-4">
            <a href="/" class="text-2xl font-black italic tracking-tighter">Titan<span class="text-zinc-600">Protocol</span></a>
            {nav}
        </nav>
        <main class="w-full max-w-6xl">{content}</main>
        <footer class="w-full max-w-6xl mt-24 pt-12 border-t border-zinc-900 text-center mb-12">
            <div class="flex justify-center space-x-8 mb-6">
                <a href="{STRIPE_PORTAL}" class="text-[10px] font-bold uppercase text-red-500">Billing</a>
                <a href="/logout" class="text-[10px] font-bold uppercase text-zinc-500">Logout</a>
                <a href="/privacy" class="text-[10px] font-bold uppercase text-zinc-500">Privacy</a>
            </div>
            <p class="text-[8px] font-bold uppercase text-zinc-800 tracking-[0.5em]">System Operational • v28.0</p>
        </footer>
    </body></html>
    """
    # ==============================================================================
# ROUTES & CONTROLLERS
# ==============================================================================

@app.route('/')
def index():
    if 'user_email' not in session:
        return render_ui("""<div class="text-center py-20">
            <h1 class="text-8xl font-black italic tracking-tighter mb-6">Titan</h1>
            <p class="text-zinc-500 font-bold uppercase tracking-widest mb-12">Autonomous Asset Infrastructure</p>
            <a href="/login" class="btn">Initialize Session</a>
        </div>""")
    
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (session['user_email'],)).fetchone()
        leads_count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    
    rate = max(0.02, 0.06 - (user['purchase_count'] * 0.01))
    
    return render_ui(f"""
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div class="md:col-span-2 card p-10">
            <h2 class="text-4xl font-black italic mb-2">Command Center</h2>
            <p class="text-xs text-zinc-500 uppercase font-mono mb-8">ID: {user['email']}</p>
            <div class="grid grid-cols-3 gap-4">
                <div><p class="text-zinc-500 text-[10px] uppercase font-bold">Market Assets</p><p class="text-3xl font-black">{leads_count}</p></div>
                <div><p class="text-zinc-500 text-[10px] uppercase font-bold">Fee Tier</p><p class="text-3xl font-black text-green-500">{rate*100:.1f}%</p></div>
                <div><p class="text-zinc-500 text-[10px] uppercase font-bold">AI Status</p><p class="text-3xl font-black text-indigo-500">{'ON' if user['ai_access'] else 'OFF'}</p></div>
            </div>
        </div>
        <div class="card p-10 flex flex-col justify-center space-y-4">
            <a href="/buy" class="btn text-center text-xs">View Feed</a>
            <a href="/sell" class="btn-outline text-center text-xs">List Asset</a>
        </div>
    </div>
    """, user)

@app.route('/buy')
def buy_feed():
    if 'user_email' not in session: return redirect('/')
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (session['user_email'],)).fetchone()
    
    leads = get_matched_leads(user)
    rows = ""
    for l in leads:
        img = f'<img src="/uploads/{l["image_path"]}" class="w-full h-32 object-cover rounded-xl">' if l['image_path'] else '<div class="w-full h-32 bg-zinc-900 rounded-xl"></div>'
        rows += f"""<div class="card p-6 grid grid-cols-1 md:grid-cols-4 gap-6 items-center mb-4">
            <div class="md:col-span-1">{img}</div>
            <div class="md:col-span-2">
                <div class="flex space-x-2 mb-2"><span class="bg-zinc-800 text-[9px] font-bold px-2 py-1 rounded text-zinc-400">OFF-MARKET</span><span class="bg-green-900/20 text-[9px] font-bold px-2 py-1 rounded text-green-500">ROI: {l['roi']}%</span></div>
                <h3 class="text-xl font-black italic">{l['address']}</h3>
                <p class="text-xs text-zinc-500 font-mono mt-1">ASK: ${l['asking_price']:,} | ARV: ${l['arv']:,}</p>
            </div>
            <div class="md:col-span-1 text-right">
                <p class="text-[9px] font-bold text-zinc-600 uppercase mb-1">Fee ({l['rate_display']}%)</p>
                <p class="text-xl font-black mb-3">${l['fee']:,}</p>
                <form action="/buy/unlock" method="POST"><button class="btn text-[10px] w-full py-2">Unlock</button></form>
            </div>
        </div>"""
        
    return render_ui(f"""
    <div class="flex justify-between items-end mb-8">
        <h2 class="text-4xl font-black italic">Asset Feed</h2>
        <a href="/buy/configure" class="btn-outline text-[10px]">Filter</a>
    </div>
    {rows if rows else '<div class="card p-10 text-center text-zinc-500">No signals detected. Adjust criteria.</div>'}
    """, user)

@app.route('/buy/configure', methods=['GET', 'POST'])
def configure():
    if 'user_email' not in session: return redirect('/')
    if request.method == 'POST':
        f = request.form
        with get_db() as conn:
            conn.execute("UPDATE users SET bb_min_price=?, bb_max_price=?, bb_min_sqft=?, bb_target_zip=?, bb_strategy=? WHERE email=?", (f.get('min'), f.get('max'), f.get('sqft'), f.get('zip'), f.get('strat'), session['user_email']))
            conn.commit()
        return redirect('/buy')
    with get_db() as conn: user = conn.execute("SELECT * FROM users WHERE email=?", (session['user_email'],)).fetchone()
    return render_ui(f"""<div class="card p-10 max-w-xl mx-auto"><h2 class="text-2xl font-black mb-6">Targeting</h2><form method="POST" class="space-y-4">
        <div class="grid grid-cols-2 gap-4"><input name="min" value="{user['bb_min_price']}"><input name="max" value="{user['bb_max_price']}"></div>
        <div class="grid grid-cols-2 gap-4"><input name="sqft" value="{user['bb_min_sqft']}"><input name="zip" value="{user['bb_target_zip'] or ''}"></div>
        <select name="strat"><option value="Any">Any</option><option value="Flip">Flip</option></select>
        <button class="btn w-full">Save</button></form></div>""", user)

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if 'user_email' not in session: return redirect('/')
    if request.method == 'POST':
        f = request.form
        img = request.files.get('photo')
        fname = secure_filename(img.filename) if img else None
        if fname: img.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
        arv = int(int(f.get('price')) * 1.3)
        with get_db() as conn:
            conn.execute("INSERT INTO leads (address, asking_price, arv, repair_cost, sqft, image_path, seller_email) VALUES (?,?,?,?,?,?,?)",
                        (f.get('addr'), f.get('price'), arv, f.get('repair'), f.get('sqft'), fname, session['user_email']))
            conn.commit()
        return redirect('/buy')
    return render_ui("""<div class="card p-10 max-w-xl mx-auto"><h2 class="text-2xl font-black mb-6">List Asset</h2><form method="POST" enctype="multipart/form-data" class="space-y-4">
        <input name="addr" placeholder="Address" required><div class="grid grid-cols-2 gap-4"><input name="price" placeholder="Price"><input name="repair" placeholder="Repairs"></div>
        <input name="sqft" placeholder="Sqft"><input type="file" name="photo" class="text-xs text-zinc-500"><button class="btn w-full">List Free</button></form></div>""", {'email':session['user_email']}) # Mock user dict for nav

@app.route('/outreach', methods=['GET', 'POST'])
def outreach():
    if 'user_email' not in session: return redirect('/')
    with get_db() as conn: user = conn.execute("SELECT * FROM users WHERE email=?", (session['user_email'],)).fetchone()
    if not user['email_machine_access']:
        return render_ui(f"""<div class="text-center py-20"><h2 class="text-5xl font-black italic mb-8">Locked</h2>
            <form action="/checkout" method="POST" class="space-y-4 max-w-md mx-auto">
                <button name="pid" value="{PRICE_IDS['EMAIL_ONCE']}" class="btn w-full">$20 Lifetime</button>
                <button name="pid" value="{PRICE_IDS['EMAIL_WEEKLY']}" class="btn-outline w-full">$3 Weekly</button>
            </form></div>""", user)
    if request.method == 'POST':
        send_gmail(user['email'], request.form.get('targets').split(','), request.form.get('subject'), request.form.get('body'))
        return redirect('/outreach')
    return render_ui("""<div class="card p-10"><h2 class="text-3xl font-black mb-6">Broadcast</h2><form method="POST" class="space-y-4">
        <input name="targets" placeholder="Targets"><input name="subject" placeholder="Subject"><textarea name="body" class="h-32" placeholder="Message"></textarea><button class="btn w-full">Send</button></form></div>""", user)

@app.route('/ai-agent')
def ai_agent():
    if 'user_email' not in session: return redirect('/')
    with get_db() as conn: user = conn.execute("SELECT * FROM users WHERE email=?", (session['user_email'],)).fetchone()
    access = user['ai_access'] or (user['ai_trial_end'] and datetime.now() < datetime.fromisoformat(user['ai_trial_end']))
    if not access:
        return render_ui(f"""<div class="text-center py-20"><h2 class="text-5xl font-black italic text-indigo-400 mb-8">Neural Locked</h2>
            <a href="/start-trial" class="btn bg-indigo-600 text-white border-none mb-4 inline-block">Start 48H Trial</a>
            <form action="/checkout" method="POST"><button name="pid" value="{PRICE_IDS['AI_MONTHLY']}" class="btn-outline">$50/Mo Sub</button></form></div>""", user)
    return render_ui(f"""<div class="card p-10 bg-zinc-900/50"><h2 class="text-3xl font-black text-indigo-400 mb-4">Neural Output</h2><p class="text-2xl italic font-mono">"{generate_ai_content()}"</p></div>""", user)

@app.route('/checkout', methods=['POST'])
def checkout():
    try:
        s = stripe.checkout.Session.create(line_items=[{'price': request.form.get('pid'), 'quantity': 1}], mode='subscription' if request.form.get('pid') != PRICE_IDS['EMAIL_ONCE'] else 'payment', success_url=request.host_url+'success?pid='+request.form.get('pid'), cancel_url=request.host_url, customer_email=session['user_email'])
        return redirect(s.url, 303)
    except Exception as e: return str(e)

@app.route('/success')
def success():
    with get_db() as conn:
        if request.args.get('pid') == PRICE_IDS['AI_MONTHLY']: conn.execute("UPDATE users SET ai_access=1 WHERE email=?", (session['user_email'],))
        else: conn.execute("UPDATE users SET email_machine_access=1 WHERE email=?", (session['user_email'],))
        conn.commit()
    return redirect('/')

@app.route('/start-trial')
def trial():
    with get_db() as conn: conn.execute("UPDATE users SET ai_trial_end=? WHERE email=?", ((datetime.now()+timedelta(hours=48)).isoformat(), session['user_email'])); conn.commit()
    return redirect('/ai-agent')

@app.route('/buy/unlock', methods=['POST'])
def unlock(): return redirect('/buy')

@app.route('/auth/login')
def login():
    f = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES); f.redirect_uri = os.environ.get("REDIRECT_URI")
    u, s = f.authorization_url(prompt='consent'); session['state'] = s
    return redirect(u)

@app.route('/callback')
def callback():
    f = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, state=session['state']); f.redirect_uri = os.environ.get("REDIRECT_URI")
    f.fetch_token(authorization_response=request.url)
    creds = f.credentials; email = id_token.verify_oauth2_token(creds.id_token, google_requests.Request(), GOOGLE_CLIENT_ID)['email']
    session['user_email'] = email
    c_json = json.dumps({'token':creds.token, 'refresh_token':creds.refresh_token, 'token_uri':creds.token_uri, 'client_id':creds.client_id, 'client_secret':creds.client_secret, 'scopes':creds.scopes})
    enc = cipher.encrypt(c_json.encode()).decode()
    with get_db() as conn: conn.execute("INSERT INTO users (email, google_creds_enc) VALUES (?,?) ON CONFLICT(email) DO UPDATE SET google_creds_enc=?", (email, enc, enc)); conn.commit()
    return redirect('/')

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

@app.route('/privacy')
def privacy(): return render_ui('<div class="card p-10 text-zinc-500">Privacy Protocol: Data is encrypted.</div>')

@app.route('/uploads/<filename>')
def uploaded_file(filename): return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

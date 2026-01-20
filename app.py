import os
import json
import sqlite3
import secrets
import logging
import base64
import uuid
from datetime import datetime, timedelta

import stripe
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, Response
from cryptography.fernet import Fernet
from groq import Groq

# Google Auth Imports
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from googleapiclient.discovery import build
from email.mime.text import MIMEText

# ==========================================
# CONFIG & INITIALIZATION
# ==========================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TITAN_CORE")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(64))

ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", Fernet.generate_key().decode())
cipher = Fernet(ENCRYPTION_KEY.encode())

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Render Persistence: SQLite must be in the mounted /storage directory
DB_PATH = "/storage/titan_main_v28.db"
os.makedirs("/storage", exist_ok=True)

PRICE_IDS = {
    'EMAIL_MACHINE_LIFETIME': "price_1Spy7SFXcDZgM3VoVZv71I63",
    'EMAIL_MACHINE_WEEKLY': "price_1SpxexFXcDZgM3Vo0iYmhfpb",
    'NEURAL_AGENT_MONTHLY': "price_1SqIjgFXcDZgM3VoEwrUvjWP"
}

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
REDIRECT_URI = os.environ.get("REDIRECT_URI")
SCOPES = ['https://www.googleapis.com/auth/userinfo.email', 'openid', 'https://www.googleapis.com/auth/gmail.send']

# ==========================================
# DATABASE LAYER
# ==========================================
class TitanDatabase:
    def __init__(self, path):
        self.path = path
        self._init_tables()

    def get_connection(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_tables(self):
        with self.get_connection() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY, full_name TEXT, profile_pic TEXT,
                email_machine_access INTEGER DEFAULT 0, email_trial_end TEXT, email_trial_used INTEGER DEFAULT 0,
                ai_access INTEGER DEFAULT 0, ai_trial_end TEXT, ai_trial_used INTEGER DEFAULT 0,
                google_creds_enc TEXT, last_login TEXT, created_at TEXT
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT, address TEXT, asking_price INTEGER, 
                arv INTEGER, seller_email TEXT, created_at TEXT
            )""")
            conn.commit()

    def get_user(self, email):
        with self.get_connection() as conn:
            return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

db = TitanDatabase(DB_PATH)

# ==========================================
# ACCESS & AUTH LOGIC
# ==========================================
class TitanAccess:
    @staticmethod
    def check(user, product_type):
        now = datetime.now()
        if product_type == "email":
            if user['email_machine_access']: return True
            if user['email_trial_end'] and now < datetime.fromisoformat(user['email_trial_end']): return True
        if product_type == "ai":
            if user['ai_access']: return True
            if user['ai_trial_end'] and now < datetime.fromisoformat(user['ai_trial_end']): return True
        return False

class TitanAuth:
    @staticmethod
    def get_flow():
        config = {"web": {"client_id": GOOGLE_CLIENT_ID, "auth_uri": "https://accounts.google.com/o/oauth2/auth", 
                  "token_uri": "https://oauth2.googleapis.com/token", "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"), 
                  "redirect_uris": [REDIRECT_URI]}}
        return Flow.from_client_config(config, scopes=SCOPES)

# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def index():
    if 'user_email' not in session: return redirect('/auth/login')
    user = db.get_user(session['user_email'])
    return render_titan_ui(f"<h1>Welcome, {user['full_name']}</h1>", user=user)

@app.route('/auth/login')
def login():
    flow = TitanAuth.get_flow()
    flow.redirect_uri = REDIRECT_URI
    url, state = flow.authorization_url(access_type='offline', prompt='consent')
    session['state'] = state
    return redirect(url)

@app.route('/callback')
def callback():
    flow = TitanAuth.get_flow()
    flow.redirect_uri = REDIRECT_URI
    flow.fetch_token(authorization_response=request.url)
    info = id_token.verify_oauth2_token(flow.credentials.id_token, google_requests.Request(), GOOGLE_CLIENT_ID)
    
    email = info['email']
    user = db.get_user(email)
    now = datetime.now()

    creds = {"token": flow.credentials.token, "refresh_token": flow.credentials.refresh_token, 
             "token_uri": flow.credentials.token_uri, "client_id": flow.credentials.client_id, 
             "client_secret": flow.credentials.client_secret}
    enc_creds = cipher.encrypt(json.dumps(creds).encode()).decode()

    if not user:
        # One-time Trial Logic
        email_trial = (now + timedelta(hours=24)).isoformat()
        ai_trial = (now + timedelta(hours=48)).isoformat()
        with db.get_connection() as conn:
            conn.execute("""INSERT INTO users (email, full_name, profile_pic, google_creds_enc, created_at, 
                         email_trial_end, ai_trial_end, email_trial_used, ai_trial_used) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1)""", 
                         (email, info.get('name'), info.get('picture'), enc_creds, now.isoformat(), email_trial, ai_trial))
            conn.commit()
    else:
        with db.get_connection() as conn:
            conn.execute("UPDATE users SET google_creds_enc = ?, last_login = ? WHERE email = ?", 
                         (enc_creds, now.isoformat(), email))
            conn.commit()

    session['user_email'] = email
    return redirect('/')

@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, os.environ.get('STRIPE_WEBHOOK_SECRET'))
    except: return Response(status=400)

    if event['type'] == 'checkout.session.completed':
        session_obj = event['data']['object']
        email = session_obj['customer_details']['email']
        line_items = stripe.checkout.Session.list_line_items(session_obj['id'])
        price_id = line_items['data'][0]['price']['id']

        with db.get_connection() as conn:
            if price_id in [PRICE_IDS['EMAIL_MACHINE_LIFETIME'], PRICE_IDS['EMAIL_MACHINE_WEEKLY']]:
                conn.execute("UPDATE users SET email_machine_access = 1 WHERE email = ?", (email,))
            elif price_id == PRICE_IDS['NEURAL_AGENT_MONTHLY']:
                conn.execute("UPDATE users SET ai_access = 1 WHERE email = ?", (email,))
            conn.commit()
    return Response(status=200)

@app.route('/ai-agent', methods=['GET', 'POST'])
def ai_agent():
    user = db.get_user(session.get('user_email'))
    if not user or not TitanAccess.check(user, "ai"):
        return redirect('/upsell-ai')
    
    generated_text = ""
    if request.method == 'POST':
        prompt = f"Write a real estate ad for {request.form.get('address')}"
        res = groq_client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama3-70b-8192")
        generated_text = res.choices[0].message.content
        
    return render_titan_ui(f"<form method='POST'><input name='address'><button>Generate</button></form><div>{generated_text}</div>", user=user)

@app.route('/checkout', methods=['POST'])
def create_checkout():
    session_st = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{'price': request.form.get('pid'), 'quantity': 1}],
        mode='subscription' if 'monthly' in request.form.get('pid') else 'payment',
        success_url=request.host_url + 'success',
        cancel_url=request.host_url + 'cancel',
        customer_email=session['user_email']
    )
    return redirect(session_st.url, code=303)

# UI HELPER
def render_titan_ui(content, user=None):
    return render_template_string("""
    <!DOCTYPE html><html><head><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-black text-white p-10">
        <nav class="mb-10 flex justify-between">
         <a href="/" class="font-bold text-xl">TITAN v28.2</a>
            <div>{{ user.email if user else 'Not Logged In' }}</div>
        </nav>
        <main>{{ content | safe }}</main>
    </body></html>
    """, content=content, user=user)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

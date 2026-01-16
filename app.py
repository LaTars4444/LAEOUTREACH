# ==============================================================================
# TITAN PROTOCOL v28 - ENTERPRISE MONOLITH
# PART 1: CORE INFRASTRUCTURE & DATABASE LAYER
# ==============================================================================

import os
import re
import base64
import time
import random
import json
import secrets
import sqlite3
import stripe
import logging
from datetime import datetime, timedelta
from functools import wraps

# Security & Crypto
from cryptography.fernet import Fernet
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Web Framework
from flask import (
    Flask, 
    render_template_string, 
    request, 
    redirect, 
    url_for, 
    session, 
    flash, 
    send_from_directory, 
    jsonify,
    abort
)

# Google Integration
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from googleapiclient.discovery import build

# AI & Email
from email.mime.text import MIMEText
from groq import Groq

# ------------------------------------------------------------------------------
# 1. SYSTEM CONFIGURATION & ENVIRONMENT VARIABLES
# ------------------------------------------------------------------------------

# Initialize Flask Application
app = Flask(__name__)

# Fix for Render/Heroku HTTPS Reverse Proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# Secret Keys (Must be set in Render Environment)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "TITAN_DEV_KEY_UNSAFE")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

# Groq AI Configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Encryption Setup (Fernet 32-byte Key)
# Used to encrypt Google OAuth Refresh Tokens in the DB
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    # Generates a temporary key if none exists (Tokens will be lost on restart)
    print("WARNING: No ENCRYPTION_KEY found. Generating ephemeral key.")
    cipher = Fernet(Fernet.generate_key())
else:
    cipher = Fernet(ENCRYPTION_KEY.encode())

# File Storage Configuration
# On Render, only /tmp is writable for ephemeral storage
UPLOAD_FOLDER = '/tmp/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}

# Database Path
# On Render, this should ideally be on a Persistent Disk mount
DB_PATH = "titan_v28_enterprise.db" 

# ------------------------------------------------------------------------------
# 2. PRICING & STRIPE CONFIGURATION
# ------------------------------------------------------------------------------

# Direct Mapping to User Requirements
PRICING_TIERS = {
    'EMAIL_WEEKLY': 'price_1SpxexFXcDZgM3Vo0iYmhfpb',  # $3.00 / Week
    'EMAIL_LIFETIME': 'price_1Spy7SFXcDZgM3VoVZv71I63', # $20.00 / One-Time
    'AI_MONTHLY': 'price_1SqIjgFXcDZgM3VoEwrUvjWP'      # $50.00 / Month
}

STRIPE_PORTAL_URL = "https://billing.stripe.com/p/login/cNidR9dlK3WC4fg9VR9IQ00"

# ------------------------------------------------------------------------------
# 3. OAUTH CONFIGURATION
# ------------------------------------------------------------------------------

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")

# Scopes required for Login AND Gmail Sending
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
    'https://www.googleapis.com/auth/gmail.send'
]

CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "project_id": "pro-exchange-titan",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uris": [REDIRECT_URI]
    }
}

# ------------------------------------------------------------------------------
# 4. DATABASE SCHEMA & INITIALIZATION
# ------------------------------------------------------------------------------

def get_db():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Allows accessing columns by name
    return conn

def init_db():
    """
    Initializes the complex Enterprise schema.
    Includes tables for Users, Leads, Outreach Logs, and AI Metrics.
    """
    try:
        with get_db() as conn:
            # 1. USERS TABLE
            # Stores Authentication, Subscription Status, and Buy Box Preferences
            conn.execute("""CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                
                -- Authentication Tokens (Encrypted)
                google_creds_enc TEXT,
                
                -- Performance Metrics
                purchase_count INTEGER DEFAULT 0,
                
                -- Subscription Flags
                has_email_access INTEGER DEFAULT 0, -- 0=No, 1=Yes ($20 or $3/wk)
                has_ai_access INTEGER DEFAULT 0,    -- 0=No, 1=Yes ($50/mo)
                ai_trial_end_date TEXT,             -- ISO Format Date for 48h Trial
                
                -- BUY BOX ENGINE (User Preferences)
                bb_min_price INTEGER DEFAULT 0,
                bb_max_price INTEGER DEFAULT 5000000,
                bb_min_sqft INTEGER DEFAULT 0,
                bb_target_zip TEXT,
                bb_strategy TEXT DEFAULT 'Any',     -- Flip, Hold, BRRRR, Wholetail
                bb_min_roi INTEGER DEFAULT 10       -- Minimum ROI % required
            )""")

            # 2. LEADS TABLE (The Assets)
            # Stores detailed property data for the Feed
            conn.execute("""CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                
                -- Property Details
                address TEXT NOT NULL,
                zip_code TEXT,
                sqft INTEGER DEFAULT 0,
                beds INTEGER DEFAULT 0,
                baths REAL DEFAULT 0,
                year_built INTEGER,
                
                -- Financials
                asking_price INTEGER NOT NULL,
                arv INTEGER DEFAULT 0,              -- After Repair Value
                est_repair_cost INTEGER DEFAULT 0,
                
                -- Media & Status
                image_path TEXT,
                status TEXT DEFAULT 'active',       -- active, pending, sold, archived
                seller_email TEXT,                  -- Who uploaded it
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")

            # 3. OUTREACH LOGS
            # Tracks emails sent via the Gmail Machine
            conn.execute("""CREATE TABLE IF NOT EXISTS outreach_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                recipient_email TEXT,
                subject_line TEXT,
                sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'sent'
            )""")

            # 4. AI CONTENT QUEUE
            # Stores generated intellectual content
            conn.execute("""CREATE TABLE IF NOT EXISTS ai_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                content_body TEXT,
                strategy_type TEXT DEFAULT 'Intellectual',
                generated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
            
            conn.commit()
            print(">>> DATABASE INITIALIZED SUCCESSFULLY: Titan Protocol v28")
            
    except Exception as e:
        print(f">>> CRITICAL DATABASE ERROR: {e}")

# Initialize DB on startup
init_db()



# ------------------------------------------------------------------------------
# 5. FINANCIAL & DEAL ANALYSIS ENGINE
# ------------------------------------------------------------------------------

def calculate_deal_metrics(lead, user_tier_rate):
    """
    Performs real-time financial analysis on a property lead.
    Calculates Assignment Fees, Totals, and Projected Profit.
    """
    try:
        asking_price = lead['asking_price']
        arv = lead['arv'] if lead['arv'] else (asking_price * 1.25) # Default ARV assumption if missing
        repair_cost = lead['est_repair_cost'] if lead['est_repair_cost'] else 0
        
        # 1. Calculate Our Fee based on User's Tier
        # (Tier is determined by their purchase_count)
        assignment_fee = int(asking_price * user_tier_rate)
        
        # 2. Total Acquisition Cost for the Buyer
        # (Ask + Fee + Repairs + Closing Costs estimate)
        closing_costs = int(asking_price * 0.02) # Est 2% closing
        total_investment = asking_price + assignment_fee + repair_cost + closing_costs
        
        # 3. Projected Net Profit
        # (ARV - Selling Costs - Total Investment)
        selling_costs = int(arv * 0.06) # Est 6% agent fees on exit
        net_profit = arv - selling_costs - total_investment
        
        # 4. Return on Investment (ROI)
        roi_percentage = 0
        if total_investment > 0:
            roi_percentage = round((net_profit / total_investment) * 100, 2)
            
        return {
            'fee_amount': assignment_fee,
            'total_entry': total_investment,
            'net_profit': net_profit,
            'roi': roi_percentage,
            'arv_display': int(arv)
        }
    except Exception as e:
        print(f"Metrics Error: {e}")
        return {'fee_amount': 0, 'total_entry': 0, 'net_profit': 0, 'roi': 0, 'arv_display': 0}

def get_user_tier_rate(email):
    """
    Determines the Assignment Fee % based on user loyalty.
    Logic: Starts at 6%. Drops 1% for every deal closed. Floor at 2%.
    """
    with get_db() as conn:
        user = conn.execute("SELECT purchase_count FROM users WHERE email = ?", (email,)).fetchone()
        
    if not user: return 0.06
    
    count = user['purchase_count']
    rate = 0.06 - (count * 0.01)
    
    # Hard floor at 2%
    return max(0.02, rate)

# ------------------------------------------------------------------------------
# 6. BUY BOX MATCHING ALGORITHM
# ------------------------------------------------------------------------------

def fetch_matched_leads(user_email):
    """
    The Core Matching Engine.
    Retrieves leads that specifically match the user's criteria.
    If criteria are loose, returns broad matches.
    """
    with get_db() as conn:
        # Get User Preferences
        user = conn.execute("SELECT * FROM users WHERE email = ?", (user_email,)).fetchone()
        
        # Build Dynamic SQL Query
        query = "SELECT * FROM leads WHERE status = 'active'"
        params = []
        
        # Filter: Price Ceiling
        if user['bb_max_price'] and user['bb_max_price'] > 0:
            query += " AND asking_price <= ?"
            params.append(user['bb_max_price'])
            
        # Filter: Price Floor
        if user['bb_min_price'] and user['bb_min_price'] > 0:
            query += " AND asking_price >= ?"
            params.append(user['bb_min_price'])
            
        # Filter: Min Sqft
        if user['bb_min_sqft'] and user['bb_min_sqft'] > 0:
            query += " AND sqft >= ?"
            params.append(user['bb_min_sqft'])
            
        # Filter: Geo-Targeting (Zip Code)
        if user['bb_target_zip'] and len(user['bb_target_zip']) > 2:
            query += " AND zip_code LIKE ?"
            params.append(f"{user['bb_target_zip']}%") # Partial match allowed
            
        # Sort by newest first
        query += " ORDER BY id DESC LIMIT 50"
        
        # Execute
        raw_leads = conn.execute(query, params).fetchall()
        
    # Post-Processing: Enhance leads with Financial Metrics
    enhanced_leads = []
    tier_rate = get_user_tier_rate(user_email)
    
    for row in raw_leads:
        lead_dict = dict(row) # Convert Row to Dict for mutability
        metrics = calculate_deal_metrics(lead_dict, tier_rate)
        
        # Merge metrics into the lead object
        lead_dict.update(metrics)
        lead_dict['tier_percent'] = int(tier_rate * 100)
        
        enhanced_leads.append(lead_dict)
        
    return enhanced_leads

# ------------------------------------------------------------------------------
# 7. NEURAL CONTENT GENERATOR (GROQ / LLAMA 3)
# ------------------------------------------------------------------------------

def generate_neural_content(strategy="Intellectual"):
    """
    Connects to Groq API to generate viral, philosophy-based content.
    Fallback hardcoded messages ensure stability if API fails.
    """
    if not groq_client:
        return "Wealth is not liquid. Wealth is equity. Own the asset, control the future. List on Pro-Exchange."

    try:
        # System Prompt Engineering for Specific Tone
        system_prompt = (
            "You are a sophisticated Real Estate Private Equity mogul and Stoic philosopher. "
            "Write a 40-word script hook for TikTok. "
            "Topic: The difference between being rich (cash) and being wealthy (equity). "
            "Tone: Dark, Intellectual, Commanding. "
            "Ending: Tell them to check the link in bio."
        )

        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt}
            ],
            model="llama3-8b-8192", # Using Llama 3 via Groq for speed
            temperature=0.7
        )
        
        return chat_completion.choices[0].message.content
        
    except Exception as e:
        print(f"AI Generation Error: {e}")
        return "Discipline equals Freedom. Stop paying commissions. Keep your equity. Join the Pro-Exchange network today."

# ------------------------------------------------------------------------------
# 8. GMAIL BROADCAST ENGINE (OAUTH HANDLING)
# ------------------------------------------------------------------------------

def send_secure_gmail(user_email, recipients, subject, body):
    """
    Decrypts user credentials and sends authenticated emails via Gmail API.
    Handles Token Refresh logic automatically via Google Library.
    """
    with get_db() as conn:
        user = conn.execute("SELECT google_creds_enc FROM users WHERE email=?", (user_email,)).fetchone()
        
    if not user or not user['google_creds_enc']:
        return False, "NO_CREDS"

    try:
        # 1. Decrypt the Creds
        decrypted_json = cipher.decrypt(user['google_creds_enc'].encode()).decode()
        creds_info = json.loads(decrypted_json)
        
        # 2. Reconstruct Credentials Object
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_info(creds_info)
        
        # 3. Build Service
        service = build('gmail', 'v1', credentials=creds)
        
        success_count = 0
        failure_count = 0
        
        # 4. Loop through targets (Batch Sending)
        for target in recipients:
            target = target.strip()
            if not target or "@" not in target: continue
            
            try:
                # Construct MIME Message
                message = MIMEText(body)
                message['to'] = target
                message['subject'] = subject
                raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
                
                # Send
                service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
                success_count += 1
                
                # Log Success
                with get_db() as log_conn:
                    log_conn.execute(
                        "INSERT INTO outreach_logs (user_email, recipient_email, subject_line) VALUES (?, ?, ?)",
                        (user_email, target, subject)
                    )
                    log_conn.commit()
                    
                # Rate Limiting (Prevent Google Spam Flag)
                time.sleep(random.uniform(0.5, 1.5))
                
            except Exception as e:
                print(f"Failed to send to {target}: {e}")
                failure_count += 1
        
        return True, f"Broadcast Complete. Sent: {success_count} | Failed: {failure_count}"
        
    except Exception as e:
        print(f"Critical Gmail Error: {e}")
        return False, str(e)

# ------------------------------------------------------------------------------
# 9. USER AUTHENTICATION CONTROLLERS (GOOGLE OAUTH)
# ------------------------------------------------------------------------------

@app.route('/login')
def login():
    """
    Initiates the Google OAuth 2.0 Flow.
    Redirects user to Google's consent screen.
    """
    # Store the intended destination to redirect after login
    session['next_url'] = request.args.get('next', 'dashboard')
    
    # Configure the flow
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES
    )
    flow.redirect_uri = REDIRECT_URI
    
    # Generate authorization URL
    authorization_url, state = flow.authorization_url(
        access_type='offline', # Crucial for getting Refresh Tokens
        include_granted_scopes='true',
        prompt='consent'       # Force consent to ensure we get a Refresh Token
    )
    
    # Store state to verify callback later
    session['state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    """
    Handles the callback from Google.
    Exchanges the Authorization Code for Tokens.
    Creates or Updates the User in the DB.
    """
    try:
        # Reconstruct the flow using the state from the session
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            state=session.get('state')
        )
        flow.redirect_uri = REDIRECT_URI
        
        # Exchange code for tokens
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        
        # Verify the ID Token to get email
        id_info = id_token.verify_oauth2_token(
            creds.id_token, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        user_email = id_info.get('email')
        
        # 1. Serialize Credentials to JSON
        creds_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
        creds_json = json.dumps(creds_data)
        
        # 2. Encrypt Credentials before storage (Security Requirement)
        encrypted_creds = cipher.encrypt(creds_json.encode()).decode()
        
        # 3. Upsert User into Database
        with get_db() as conn:
            conn.execute("""
                INSERT INTO users (email, google_creds_enc) 
                VALUES (?, ?)
                ON CONFLICT(email) DO UPDATE SET 
                    google_creds_enc = excluded.google_creds_enc
            """, (user_email, encrypted_creds))
            conn.commit()
            
        # 4. Set Session
        session['user_email'] = user_email
        
        # Redirect to intended destination
        next_url = session.get('next_url', 'dashboard')
        return redirect(url_for(next_url))
        
    except Exception as e:
        print(f"Auth Callback Error: {e}")
        return "Authentication Failed. Please try again."

@app.route('/logout')
def logout():
    """Clears the session and logs the user out."""
    session.clear()
    return redirect(url_for('index'))

# ------------------------------------------------------------------------------
# 10. STRIPE CHECKOUT & PORTAL HANDLERS
# ------------------------------------------------------------------------------

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """
    Creates a Stripe Checkout Session based on the requested Product ID.
    Handles both One-Time ($20) and Recurring ($3/wk, $50/mo) payments.
    """
    if 'user_email' not in session: return redirect(url_for('index'))
    
    product_key = request.form.get('product_key') # e.g., 'EMAIL_WEEKLY'
    price_id = PRICING_TIERS.get(product_key)
    
    if not price_id:
        flash("Invalid Product Selection")
        return redirect(url_for('dashboard'))
        
    try:
        # Determine Mode (Subscription vs Payment)
        mode = 'payment' if product_key == 'EMAIL_LIFETIME' else 'subscription'
        
        checkout_session = stripe.checkout.Session.create(
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode=mode,
            customer_email=session['user_email'],
            success_url=request.host_url + f"payment-success?pk={product_key}",
            cancel_url=request.host_url + "dashboard",
            metadata={
                'user_email': session['user_email'],
                'product_type': product_key
            }
        )
        return redirect(checkout_session.url, code=303)
        
    except Exception as e:
        flash(f"Payment Initialization Failed: {str(e)}")
        return redirect(url_for('dashboard'))

@app.route('/payment-success')
def payment_success():
    """
    Landing page after successful payment.
    Updates the database immediately to unlock features.
    """
    product_key = request.args.get('pk')
    email = session.get('user_email')
    
    if not email or not product_key: return redirect(url_for('index'))
    
    with get_db() as conn:
        if product_key == 'AI_MONTHLY':
            # Unlock AI
            conn.execute("UPDATE users SET has_ai_access = 1 WHERE email = ?", (email,))
        elif product_key in ['EMAIL_WEEKLY', 'EMAIL_LIFETIME']:
            # Unlock Email Machine
            conn.execute("UPDATE users SET has_email_access = 1 WHERE email = ?", (email,))
        conn.commit()
        
    flash("Protocol Upgrade Successful. Systems Online.")
    return redirect(url_for('dashboard'))

# ------------------------------------------------------------------------------
# 11. STRIPE WEBHOOK HANDLER (AUTOMATED MANAGEMENT)
# ------------------------------------------------------------------------------

@app.route('/stripe_webhook', methods=['POST'])
def stripe_webhook():
    """
    Listens for events from Stripe (e.g., failed payment, cancelled sub).
    Automatically revokes access if a subscription ends.
    """
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    try:
        if endpoint_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        else:
            # Fallback for dev/testing without signature verification
            event = json.loads(payload)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    # Handle Events
    if event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        # We need to find the user associated with this customer
        # Ideally, we query Stripe for the email
        try:
            customer = stripe.Customer.retrieve(customer_id)
            user_email = customer.email
            
            # Revoke Access in DB
            with get_db() as conn:
                # We don't know exactly which product it was, so we might need to check the Plan ID
                # For safety in this version, we revoke both subs if cancelled, 
                # forcing them to re-subscribe or contact support (Simplified Logic)
                conn.execute("""
                    UPDATE users SET 
                    has_ai_access = 0, 
                    has_email_access = 0 
                    WHERE email = ?
                """, (user_email,))
                conn.commit()
            print(f"Subscription revoked for {user_email}")
        except Exception as e:
            print(f"Webhook Error processing customer {customer_id}: {e}")

    return jsonify({'status': 'success'}), 200

# ------------------------------------------------------------------------------
# 12. FREE TRIAL LOGIC (48H NO-CC)
# ------------------------------------------------------------------------------

@app.route('/activate-trial')
def activate_trial():
    """
    Grants a 48-hour access pass to the AI Agent without Stripe.
    """
    if 'user_email' not in session: return redirect(url_for('index'))
    
    # Calculate End Date (Now + 48 Hours)
    end_date = (datetime.now() + timedelta(hours=48)).isoformat()
    
    with get_db() as conn:
        conn.execute("UPDATE users SET ai_trial_end_date = ? WHERE email = ?", (end_date, session['user_email']))
        conn.commit()
        
    flash("48-Hour Neural Link Established.")
    return redirect(url_for('ai_dashboard'))
    # ==============================================================================
# PART 4: GLOBAL UI ARCHITECTURE (THE TITAN THEME)
# ==============================================================================

# ------------------------------------------------------------------------------
# 13. CSS & DESIGN SYSTEM (IN-LINE ASSETS)
# ------------------------------------------------------------------------------

TITAN_CSS = """
<style>
    /* TITAN DESIGN SYSTEM v1.0 */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;800&family=Outfit:wght@300;400;700;900&display=swap');

    :root {
        --bg-deep: #030303;
        --bg-card: #0a0a0a;
        --border: #1a1a1a;
        --text-primary: #ffffff;
        --text-secondary: #888888;
        --accent-core: #ffffff;
        --accent-ai: #6366f1;    /* Indigo */
        --accent-money: #22c55e; /* Green */
        --accent-alert: #ef4444; /* Red */
        --font-main: 'Outfit', sans-serif;
        --font-mono: 'JetBrains Mono', monospace;
    }

    /* Base Reset */
    body {
        background-color: var(--bg-deep);
        color: var(--text-primary);
        font-family: var(--font-main);
        -webkit-font-smoothing: antialiased;
        line-height: 1.5;
    }

    /* Utility: Glassmorphism & Cards */
    .titan-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 2rem;
        transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        position: relative;
        overflow: hidden;
    }

    .titan-card:hover {
        border-color: #333;
        transform: translateY(-4px);
        box-shadow: 0 30px 60px rgba(0,0,0,0.5);
    }

    /* Utility: Buttons */
    .btn-titan-primary {
        background: var(--accent-core);
        color: #000;
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 1rem 2rem;
        border-radius: 1rem;
        transition: all 0.2s ease;
        display: inline-block;
        border: 2px solid transparent;
    }

    .btn-titan-primary:hover {
        background: #e5e5e5;
        transform: scale(1.02);
    }

    .btn-titan-outline {
        background: transparent;
        color: var(--text-secondary);
        border: 1px solid #333;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 0.8rem 1.5rem;
        border-radius: 1rem;
        transition: all 0.2s ease;
        display: inline-block;
        font-size: 0.8rem;
    }

    .btn-titan-outline:hover {
        border-color: var(--accent-core);
        color: var(--accent-core);
    }
    
    .btn-titan-ai {
        background: var(--accent-ai);
        color: #fff;
        font-weight: 900;
        text-transform: uppercase;
        padding: 1rem 2rem;
        border-radius: 1rem;
        transition: all 0.2s ease;
        box-shadow: 0 10px 30px rgba(99, 102, 241, 0.2);
    }
    
    .btn-titan-ai:hover {
        background: #4f46e5;
        box-shadow: 0 15px 40px rgba(99, 102, 241, 0.4);
    }

    /* Utility: Typography */
    .font-titan-header {
        font-weight: 900;
        text-transform: uppercase;
        font-style: italic;
        letter-spacing: -0.04em;
        line-height: 0.9;
    }
    
    .font-titan-mono {
        font-family: var(--font-mono);
    }

    /* Utility: Form Elements */
    input, select, textarea {
        background: #0f0f0f;
        border: 1px solid #222;
        color: #fff;
        padding: 1.2rem;
        border-radius: 1rem;
        width: 100%;
        outline: none;
        font-family: var(--font-mono);
        font-size: 0.9rem;
        transition: border-color 0.2s;
    }

    input:focus, select:focus, textarea:focus {
        border-color: #555;
        background: #141414;
    }
    
    /* Utility: Grids */
    .grid-titan-dashboard {
        display: grid;
        grid-template-columns: repeat(12, 1fr);
        gap: 1.5rem;
    }
    
    .col-span-12 { grid-column: span 12; }
    .col-span-8  { grid-column: span 8; }
    .col-span-6  { grid-column: span 6; }
    .col-span-4  { grid-column: span 4; }
    
    @media (max-width: 1024px) {
        .col-span-8, .col-span-6, .col-span-4 { grid-column: span 12; }
    }

    /* Animations */
    @keyframes pulse-glow {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    .animate-pulse-slow {
        animation: pulse-glow 3s infinite;
    }

</style>
"""

# ------------------------------------------------------------------------------
# 14. TEMPLATE PARTIALS (HEADER & NAV)
# ------------------------------------------------------------------------------

def render_ui(content, user=None):
    """
    Constructs the full HTML page by wrapping 'content' 
    with the standard Header, Navigation, and Footer.
    """
    
    # Navigation State Logic
    nav_links = ""
    if user:
        nav_links = f"""
        <div class="hidden md:flex space-x-8 items-center">
            <a href="/buy" class="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500 hover:text-white transition">Asset Feed</a>
            <a href="/sell" class="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500 hover:text-white transition">List Asset</a>
            <a href="/outreach" class="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500 hover:text-white transition">Email Machine</a>
            <a href="/ai-agent" class="px-4 py-2 bg-indigo-900/30 text-indigo-300 rounded-full text-[10px] font-black uppercase tracking-widest hover:bg-indigo-900/50 transition">Neural Agent</a>
        </div>
        """
    else:
        nav_links = """
        <a href="/login" class="text-[10px] font-black uppercase tracking-[0.2em] text-white hover:text-gray-300 transition">Client Login</a>
        """

    # Flash Messages Logic
    flash_html = ""
    # In Flask, get_flashed_messages requires a context, simplified here for string formatting
    # Real implementation happens inside the route handlers usually via Jinja2
    # but since we are doing string injection, we handle it slightly differently.
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TITAN | Autonomous Asset Protocol</title>
        <script src="https://cdn.tailwindcss.com"></script>
        {TITAN_CSS}
    </head>
    <body class="min-h-screen flex flex-col items-center p-4 sm:p-8">
        
        <!-- TOP NAVIGATION BAR -->
        <nav class="w-full max-w-7xl flex justify-between items-center mb-16 py-4">
            <a href="/" class="flex items-center group">
                <div class="w-8 h-8 bg-white rounded-full mr-4 group-hover:scale-110 transition-transform"></div>
                <div>
                    <h1 class="font-titan-header text-2xl tracking-tighter">Titan<span class="opacity-50">Protocol</span></h1>
                    <p class="text-[8px] font-mono text-gray-600 uppercase tracking-widest">v28.0 Enterprise Node</p>
                </div>
            </a>
            {nav_links}
        </nav>

        <!-- MAIN CONTENT CONTAINER -->
        <main class="w-full max-w-7xl relative z-10">
            {content}
        </main>

        <!-- GLOBAL FOOTER -->
        <footer class="w-full max-w-7xl mt-32 pt-16 border-t border-zinc-900 mb-12">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-12">
                <div>
                    <h4 class="text-xs font-black uppercase text-zinc-600 mb-6">Protocol</h4>
                    <ul class="space-y-4">
                        <li><a href="/" class="text-[10px] uppercase text-zinc-400 hover:text-white transition">Dashboard</a></li>
                        <li><a href="/buy" class="text-[10px] uppercase text-zinc-400 hover:text-white transition">Asset Feed</a></li>
                        <li><a href="/sell" class="text-[10px] uppercase text-zinc-400 hover:text-white transition">Listings</a></li>
                    </ul>
                </div>
                <div>
                    <h4 class="text-xs font-black uppercase text-zinc-600 mb-6">Intelligence</h4>
                    <ul class="space-y-4">
                        <li><a href="/ai-agent" class="text-[10px] uppercase text-zinc-400 hover:text-white transition">Neural Terminal</a></li>
                        <li><a href="/outreach" class="text-[10px] uppercase text-zinc-400 hover:text-white transition">Broadcast System</a></li>
                    </ul>
                </div>
                <div>
                    <h4 class="text-xs font-black uppercase text-zinc-600 mb-6">Account</h4>
                    <ul class="space-y-4">
                        <li><a href="{STRIPE_PORTAL_URL}" class="text-[10px] uppercase text-red-400 hover:text-red-300 transition">Manage Billing</a></li>
                        <li><a href="/logout" class="text-[10px] uppercase text-zinc-400 hover:text-white transition">Secure Logout</a></li>
                    </ul>
                </div>
                <div class="col-span-2 md:col-span-1 text-right">
                    <div class="inline-block p-4 bg-zinc-900 rounded-2xl border border-zinc-800">
                        <p class="text-[9px] font-mono text-zinc-500 uppercase mb-2">System Status</p>
                        <div class="flex items-center justify-end space-x-2">
                            <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                            <span class="text-xs font-bold text-white uppercase">Operational</span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="mt-16 text-center">
                <a href="/privacy" class="text-[9px] font-black uppercase text-zinc-700 hover:text-zinc-500 transition tracking-[0.5em]">Privacy Policy & Data Protocol</a>
            </div>
        </footer>

    </body>
    </html>
    """

# ==============================================================================
# PART 4: GLOBAL UI ARCHITECTURE (THE TITAN THEME)
# ==============================================================================

# ------------------------------------------------------------------------------
# 13. CSS & DESIGN SYSTEM (IN-LINE ASSETS)
# ------------------------------------------------------------------------------

TITAN_CSS = """
<style>
    /* TITAN DESIGN SYSTEM v1.0 */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;800&family=Outfit:wght@300;400;700;900&display=swap');

    :root {
        --bg-deep: #030303;
        --bg-card: #0a0a0a;
        --border: #1a1a1a;
        --text-primary: #ffffff;
        --text-secondary: #888888;
        --accent-core: #ffffff;
        --accent-ai: #6366f1;    /* Indigo */
        --accent-money: #22c55e; /* Green */
        --accent-alert: #ef4444; /* Red */
        --font-main: 'Outfit', sans-serif;
        --font-mono: 'JetBrains Mono', monospace;
    }

    /* Base Reset */
    body {
        background-color: var(--bg-deep);
        color: var(--text-primary);
        font-family: var(--font-main);
        -webkit-font-smoothing: antialiased;
        line-height: 1.5;
    }

    /* Utility: Glassmorphism & Cards */
    .titan-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 2rem;
        transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        position: relative;
        overflow: hidden;
    }

    .titan-card:hover {
        border-color: #333;
        transform: translateY(-4px);
        box-shadow: 0 30px 60px rgba(0,0,0,0.5);
    }

    /* Utility: Buttons */
    .btn-titan-primary {
        background: var(--accent-core);
        color: #000;
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 1rem 2rem;
        border-radius: 1rem;
        transition: all 0.2s ease;
        display: inline-block;
        border: 2px solid transparent;
    }

    .btn-titan-primary:hover {
        background: #e5e5e5;
        transform: scale(1.02);
    }

    .btn-titan-outline {
        background: transparent;
        color: var(--text-secondary);
        border: 1px solid #333;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 0.8rem 1.5rem;
        border-radius: 1rem;
        transition: all 0.2s ease;
        display: inline-block;
        font-size: 0.8rem;
    }

    .btn-titan-outline:hover {
        border-color: var(--accent-core);
        color: var(--accent-core);
    }
    
    .btn-titan-ai {
        background: var(--accent-ai);
        color: #fff;
        font-weight: 900;
        text-transform: uppercase;
        padding: 1rem 2rem;
        border-radius: 1rem;
        transition: all 0.2s ease;
        box-shadow: 0 10px 30px rgba(99, 102, 241, 0.2);
    }
    
    .btn-titan-ai:hover {
        background: #4f46e5;
        box-shadow: 0 15px 40px rgba(99, 102, 241, 0.4);
    }

    /* Utility: Typography */
    .font-titan-header {
        font-weight: 900;
        text-transform: uppercase;
        font-style: italic;
        letter-spacing: -0.04em;
        line-height: 0.9;
    }
    
    .font-titan-mono {
        font-family: var(--font-mono);
    }

    /* Utility: Form Elements */
    input, select, textarea {
        background: #0f0f0f;
        border: 1px solid #222;
        color: #fff;
        padding: 1.2rem;
        border-radius: 1rem;
        width: 100%;
        outline: none;
        font-family: var(--font-mono);
        font-size: 0.9rem;
        transition: border-color 0.2s;
    }

    input:focus, select:focus, textarea:focus {
        border-color: #555;
        background: #141414;
    }
    
    /* Utility: Grids */
    .grid-titan-dashboard {
        display: grid;
        grid-template-columns: repeat(12, 1fr);
        gap: 1.5rem;
    }
    
    .col-span-12 { grid-column: span 12; }
    .col-span-8  { grid-column: span 8; }
    .col-span-6  { grid-column: span 6; }
    .col-span-4  { grid-column: span 4; }
    
    @media (max-width: 1024px) {
        .col-span-8, .col-span-6, .col-span-4 { grid-column: span 12; }
    }

    /* Animations */
    @keyframes pulse-glow {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    .animate-pulse-slow {
        animation: pulse-glow 3s infinite;
    }

</style>
"""

# ------------------------------------------------------------------------------
# 14. TEMPLATE PARTIALS (HEADER & NAV)
# ------------------------------------------------------------------------------

def render_ui(content, user=None):
    """
    Constructs the full HTML page by wrapping 'content' 
    with the standard Header, Navigation, and Footer.
    """
    
    # Navigation State Logic
    nav_links = ""
    if user:
        nav_links = f"""
        <div class="hidden md:flex space-x-8 items-center">
            <a href="/buy" class="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500 hover:text-white transition">Asset Feed</a>
            <a href="/sell" class="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500 hover:text-white transition">List Asset</a>
            <a href="/outreach" class="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500 hover:text-white transition">Email Machine</a>
            <a href="/ai-agent" class="px-4 py-2 bg-indigo-900/30 text-indigo-300 rounded-full text-[10px] font-black uppercase tracking-widest hover:bg-indigo-900/50 transition">Neural Agent</a>
        </div>
        """
    else:
        nav_links = """
        <a href="/login" class="text-[10px] font-black uppercase tracking-[0.2em] text-white hover:text-gray-300 transition">Client Login</a>
        """

    # Flash Messages Logic
    flash_html = ""
    # In Flask, get_flashed_messages requires a context, simplified here for string formatting
    # Real implementation happens inside the route handlers usually via Jinja2
    # but since we are doing string injection, we handle it slightly differently.
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TITAN | Autonomous Asset Protocol</title>
        <script src="https://cdn.tailwindcss.com"></script>
        {TITAN_CSS}
    </head>
    <body class="min-h-screen flex flex-col items-center p-4 sm:p-8">
        
        <!-- TOP NAVIGATION BAR -->
        <nav class="w-full max-w-7xl flex justify-between items-center mb-16 py-4">
            <a href="/" class="flex items-center group">
                <div class="w-8 h-8 bg-white rounded-full mr-4 group-hover:scale-110 transition-transform"></div>
                <div>
                    <h1 class="font-titan-header text-2xl tracking-tighter">Titan<span class="opacity-50">Protocol</span></h1>
                    <p class="text-[8px] font-mono text-gray-600 uppercase tracking-widest">v28.0 Enterprise Node</p>
                </div>
            </a>
            {nav_links}
        </nav>

        <!-- MAIN CONTENT CONTAINER -->
        <main class="w-full max-w-7xl relative z-10">
            {content}
        </main>

        <!-- GLOBAL FOOTER -->
        <footer class="w-full max-w-7xl mt-32 pt-16 border-t border-zinc-900 mb-12">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-12">
                <div>
                    <h4 class="text-xs font-black uppercase text-zinc-600 mb-6">Protocol</h4>
                    <ul class="space-y-4">
                        <li><a href="/" class="text-[10px] uppercase text-zinc-400 hover:text-white transition">Dashboard</a></li>
                        <li><a href="/buy" class="text-[10px] uppercase text-zinc-400 hover:text-white transition">Asset Feed</a></li>
                        <li><a href="/sell" class="text-[10px] uppercase text-zinc-400 hover:text-white transition">Listings</a></li>
                    </ul>
                </div>
                <div>
                    <h4 class="text-xs font-black uppercase text-zinc-600 mb-6">Intelligence</h4>
                    <ul class="space-y-4">
                        <li><a href="/ai-agent" class="text-[10px] uppercase text-zinc-400 hover:text-white transition">Neural Terminal</a></li>
                        <li><a href="/outreach" class="text-[10px] uppercase text-zinc-400 hover:text-white transition">Broadcast System</a></li>
                    </ul>
                </div>
                <div>
                    <h4 class="text-xs font-black uppercase text-zinc-600 mb-6">Account</h4>
                    <ul class="space-y-4">
                        <li><a href="{STRIPE_PORTAL_URL}" class="text-[10px] uppercase text-red-400 hover:text-red-300 transition">Manage Billing</a></li>
                        <li><a href="/logout" class="text-[10px] uppercase text-zinc-400 hover:text-white transition">Secure Logout</a></li>
                    </ul>
                </div>
                <div class="col-span-2 md:col-span-1 text-right">
                    <div class="inline-block p-4 bg-zinc-900 rounded-2xl border border-zinc-800">
                        <p class="text-[9px] font-mono text-zinc-500 uppercase mb-2">System Status</p>
                        <div class="flex items-center justify-end space-x-2">
                            <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                            <span class="text-xs font-bold text-white uppercase">Operational</span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="mt-16 text-center">
                <a href="/privacy" class="text-[9px] font-black uppercase text-zinc-700 hover:text-zinc-500 transition tracking-[0.5em]">Privacy Policy & Data Protocol</a>
            </div>
        </footer>

    </body>
    </html>
    """

# ==============================================================================
# END OF PART 4


# ==============================================================================
# PART 5: APPLICATION CONTROLLERS (DASHBOARD & BUYER ENGINE)
# ==============================================================================

# ------------------------------------------------------------------------------
# 15. MAIN DASHBOARD CONTROLLER
# ------------------------------------------------------------------------------

@app.route('/')
def index():
    """
    The Landing Page / Main Dashboard.
    If logged in, shows high-level stats (Purchase Count, Current Tier).
    If logged out, shows the 'Titan Protocol' splash screen.
    """
    
    # 1. Check Authentication
    if 'user_email' not in session:
        # Public Landing Page Logic
        content = """
        <div class="min-h-[70vh] flex flex-col items-center justify-center text-center">
            <h1 class="text-7xl md:text-9xl font-titan-header mb-6 tracking-tighter">Titan<br><span class="text-zinc-800">Protocol</span></h1>
            <p class="text-sm md:text-base font-mono text-zinc-500 max-w-lg mx-auto mb-12 leading-relaxed uppercase tracking-widest">
                Autonomous Real Estate Asset Infrastructure.<br>
                Neural Marketing. Direct-to-Buyer Broadcasts.<br>
                0% Commission Liquidity.
            </p>
            <div class="flex flex-col md:flex-row space-y-4 md:space-y-0 md:space-x-6">
                <a href="/login" class="btn-titan-primary text-sm">Initialize Session</a>
                <a href="/login" class="btn-titan-outline text-sm">Vendor Access</a>
            </div>
            
            <div class="mt-24 grid grid-cols-3 gap-12 opacity-30">
                <div class="text-center">
                    <p class="text-2xl font-black">2.0%</p>
                    <p class="text-[8px] uppercase tracking-widest">Floor Fee</p>
                </div>
                <div class="text-center">
                    <p class="text-2xl font-black">48H</p>
                    <p class="text-[8px] uppercase tracking-widest">Neural Trial</p>
                </div>
                <div class="text-center">
                    <p class="text-2xl font-black">0%</p>
                    <p class="text-[8px] uppercase tracking-widest">Seller Comm</p>
                </div>
            </div>
        </div>
        """
        return render_ui(content)

    # 2. Authenticated User Logic
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        
        # Calculate Stats
        total_leads = conn.execute("SELECT COUNT(*) FROM leads WHERE status='active'").fetchone()[0]
        sent_emails = conn.execute("SELECT COUNT(*) FROM outreach_logs WHERE user_email = ?", (session['user_email'],)).fetchone()[0]
        
    # Calculate Current Fee Tier (6% -> 2%)
    current_tier_rate = max(0.02, 0.06 - (user['purchase_count'] * 0.01))
    current_tier_display = f"{current_tier_rate * 100:.1f}%"

    # Status Badges
    ai_status = "ACTIVE" if user['has_ai_access'] or (user['ai_trial_end_date'] and datetime.now() < datetime.fromisoformat(user['ai_trial_end_date'])) else "LOCKED"
    email_status = "ACTIVE" if user['has_email_access'] else "LOCKED"

    # Dashboard HTML Construction
    content = f"""
    <div class="grid-titan-dashboard">
        
        <!-- WELCOME HEADER -->
        <div class="col-span-12 mb-8">
            <h2 class="text-4xl font-titan-header mb-2">Command Center</h2>
            <p class="text-xs font-mono text-zinc-500 uppercase">User ID: {user['email']}</p>
        </div>

        <!-- KPI CARDS -->
        <div class="col-span-12 md:col-span-4 titan-card p-8">
            <p class="text-[10px] font-black uppercase text-zinc-500 mb-2">Current Buy Tier</p>
            <p class="text-5xl font-black text-green-500 tracking-tighter">{current_tier_display}</p>
            <p class="text-[9px] text-zinc-600 mt-4 uppercase">Fee reduction active based on deal volume.</p>
        </div>

        <div class="col-span-6 md:col-span-4 titan-card p-8">
            <p class="text-[10px] font-black uppercase text-zinc-500 mb-2">Market Assets</p>
            <p class="text-5xl font-black text-white tracking-tighter">{total_leads}</p>
            <a href="/buy" class="text-[9px] text-zinc-400 mt-4 uppercase block hover:text-white transition">View Active Feed →</a>
        </div>

        <div class="col-span-6 md:col-span-4 titan-card p-8">
            <p class="text-[10px] font-black uppercase text-zinc-500 mb-2">Outreach Volume</p>
            <p class="text-5xl font-black text-white tracking-tighter">{sent_emails}</p>
            <a href="/outreach" class="text-[9px] text-zinc-400 mt-4 uppercase block hover:text-white transition">Launch Broadcast →</a>
        </div>

        <!-- MODULE ACCESS GRID -->
        <div class="col-span-12 md:col-span-6 titan-card p-10 border-indigo-900/30">
            <div class="flex justify-between items-start mb-8">
                <div>
                    <h3 class="text-2xl font-black uppercase italic text-indigo-400">Neural Agent</h3>
                    <p class="text-xs text-zinc-500 mt-1">Status: <span class="text-white">{ai_status}</span></p>
                </div>
                <div class="w-12 h-12 bg-indigo-500/10 rounded-full flex items-center justify-center text-indigo-400 text-2xl">⚡</div>
            </div>
            <p class="text-sm text-zinc-400 mb-8 h-12">Automated intellectual content generation. Build authority with Stoic/Wealth philosophy posts on autopilot.</p>
            <a href="/ai-agent" class="btn-titan-outline w-full text-center">Open Terminal</a>
        </div>

        <div class="col-span-12 md:col-span-6 titan-card p-10">
            <div class="flex justify-between items-start mb-8">
                <div>
                    <h3 class="text-2xl font-black uppercase italic text-white">Email Machine</h3>
                    <p class="text-xs text-zinc-500 mt-1">Status: <span class="text-white">{email_status}</span></p>
                </div>
                <div class="w-12 h-12 bg-zinc-800 rounded-full flex items-center justify-center text-white text-xl">@</div>
            </div>
            <p class="text-sm text-zinc-400 mb-8 h-12">Direct-to-Buyer broadcast system via Gmail API. Bypass spam filters with authenticated sending.</p>
            <a href="/outreach" class="btn-titan-outline w-full text-center">Open Engine</a>
        </div>

    </div>
    """
    return render_ui(content, user)

# ------------------------------------------------------------------------------
# 16. BUYER FEED & BUY BOX CONTROLLER
# ------------------------------------------------------------------------------

@app.route('/buy')
def buy_feed():
    """
    Displays the Asset Feed.
    Uses the 'fetch_matched_leads' logic from Part 2 to filter deals.
    """
    if 'user_email' not in session: return redirect(url_for('index'))
    
    # Fetch Matched Deals
    leads = fetch_matched_leads(session['user_email'])
    
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()

    # Determine Active Filters string
    filters_display = f"Price: ${user['bb_min_price']/1000}k - ${user['bb_max_price']/1000}k"
    if user['bb_target_zip']: filters_display += f" | Zip: {user['bb_target_zip']}"

    # Generate Feed HTML
    leads_html = ""
    if not leads:
        leads_html = """
        <div class="col-span-12 text-center py-20 titan-card">
            <h3 class="text-2xl font-black uppercase text-zinc-700">No Signal Detected</h3>
            <p class="text-zinc-600 mb-8 text-sm max-w-md mx-auto">No assets match your current Buy Box criteria. Expand your search parameters to detect more flow.</p>
            <a href="/buy/configure" class="btn-titan-primary text-xs">Calibrate Sensors</a>
        </div>
        """
    else:
        for lead in leads:
            # Check for image
            img_html = f'<img src="/uploads/{lead["image_path"]}" class="w-full h-48 object-cover rounded-xl opacity-80 group-hover:opacity-100 transition duration-500">' if lead['image_path'] else '<div class="w-full h-48 bg-zinc-900 rounded-xl flex items-center justify-center text-zinc-700 font-bold uppercase">No Visual</div>'
            
            leads_html += f"""
            <div class="col-span-12 titan-card p-0 grid grid-cols-1 md:grid-cols-12 overflow-hidden group">
                <!-- Image Section -->
                <div class="md:col-span-4 bg-zinc-900">
                    {img_html}
                </div>
                
                <!-- Data Section -->
                <div class="md:col-span-5 p-8 flex flex-col justify-center">
                    <div class="flex space-x-3 mb-3">
                        <span class="px-2 py-1 bg-zinc-800 text-[9px] font-black uppercase text-zinc-400 rounded">Off-Market</span>
                        <span class="px-2 py-1 bg-green-900/20 text-[9px] font-black uppercase text-green-500 rounded">Proj. ROI: {lead['roi']}%</span>
                    </div>
                    <h3 class="text-2xl font-black uppercase italic mb-2 tracking-tight">{lead['address']}</h3>
                    <div class="grid grid-cols-2 gap-4 text-xs font-mono text-zinc-500 mt-2">
                        <div><span class="block text-[9px] uppercase text-zinc-700">Ask Price</span>${"{:,.0f}".format(lead['asking_price'])}</div>
                        <div><span class="block text-[9px] uppercase text-zinc-700">ARV</span>${"{:,.0f}".format(lead['arv_display'])}</div>
                        <div><span class="block text-[9px] uppercase text-zinc-700">Sqft</span>{lead['sqft']}</div>
                        <div><span class="block text-[9px] uppercase text-zinc-700">Est. Profit</span>${"{:,.0f}".format(lead['net_profit'])}</div>
                    </div>
                </div>

                <!-- Action Section -->
                <div class="md:col-span-3 bg-zinc-900/30 p-8 flex flex-col justify-center border-l border-zinc-900">
                    <div class="text-right mb-6">
                        <p class="text-[9px] font-black uppercase text-zinc-600 mb-1">Your Fee ({lead['tier_percent']}%)</p>
                        <p class="text-2xl font-black text-white">${"{:,.0f}".format(lead['fee_amount'])}</p>
                    </div>
                    <form action="/buy/unlock" method="POST">
                        <input type="hidden" name="lead_id" value="{lead['id']}">
                        <button class="w-full btn-titan-primary text-[10px] py-4">Secure Deal</button>
                    </form>
                </div>
            </div>
            """

    content = f"""
    <div class="grid-titan-dashboard">
        <div class="col-span-12 flex justify-between items-end mb-8">
            <div>
                <h2 class="text-5xl font-titan-header tracking-tighter text-white">Asset Feed</h2>
                <p class="text-xs font-mono text-zinc-500 mt-2 uppercase">{filters_display}</p>
            </div>
            <a href="/buy/configure" class="btn-titan-outline text-[10px]">Edit Criteria</a>
        </div>
        {leads_html}
    </div>
    """
    return render_ui(content, user)

@app.route('/buy/configure', methods=['GET', 'POST'])
def configure_buybox():
    """
    Allows user to set their specific Buy Box criteria.
    Updates the 'users' table.
    """
    if 'user_email' not in session: return redirect(url_for('index'))
    
    if request.method == 'POST':
        f = request.form
        with get_db() as conn:
            conn.execute("""UPDATE users SET 
                bb_min_price=?, bb_max_price=?, bb_min_sqft=?, bb_target_zip=?, bb_strategy=? 
                WHERE email=?""", 
                (f.get('min_p'), f.get('max_p'), f.get('sqft'), f.get('zip'), f.get('strat'), session['user_email']))
            conn.commit()
        # In a real app we would use flash messages, but here we redirect to show results
        return redirect(url_for('buy_feed'))

    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (session['user_email'],)).fetchone()

    content = f"""
    <div class="max-w-3xl mx-auto titan-card p-12">
        <div class="mb-10 text-center">
            <h2 class="text-3xl font-titan-header mb-4">Target Calibration</h2>
            <p class="text-sm text-zinc-500">Define your Buy Box. The algorithm will filter deal flow to match these parameters.</p>
        </div>
        
        <form method="POST" class="space-y-8">
            <div class="grid grid-cols-2 gap-8">
                <div>
                    <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Min Price ($)</label>
                    <input type="number" name="min_p" value="{user['bb_min_price']}" placeholder="0">
                </div>
                <div>
                    <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Max Price ($)</label>
                    <input type="number" name="max_p" value="{user['bb_max_price']}" placeholder="5000000">
                </div>
            </div>

            <div class="grid grid-cols-2 gap-8">
                <div>
                    <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Min Sqft</label>
                    <input type="number" name="sqft" value="{user['bb_min_sqft']}" placeholder="0">
                </div>
                <div>
                    <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Target Zip Code</label>
                    <input type="text" name="zip" value="{user['bb_target_zip'] or ''}" placeholder="Any">
                </div>
            </div>

            <div>
                <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Asset Strategy</label>
                <select name="strat">
                    <option value="Any">Unrestricted (Show All)</option>
                    <option value="Flip" {"selected" if user['bb_strategy'] == 'Flip' else ''}>Fix & Flip (High Margin)</option>
                    <option value="Hold" {"selected" if user['bb_strategy'] == 'Hold' else ''}>Buy & Hold (Cashflow)</option>
                    <option value="Wholesale" {"selected" if user['bb_strategy'] == 'Wholesale' else ''}>Wholesale Re-assignment</option>
                </select>
            </div>

            <div class="pt-8 border-t border-zinc-900">
                <button class="btn-titan-primary w-full py-5 text-sm">Update Algorithm</button>
            </div>
        </form>
    </div>
    """
    return render_ui(content, user)

@app.route('/buy/unlock', methods=['POST'])
def unlock_deal():
    """
    Simulates the 'Unlock Deal' action.
    In a full production version, this would create a Stripe PaymentIntent for the Assignment Fee.
    """
    if 'user_email' not in session: return redirect(url_for('index'))
    # Logic to log the interest would go here
    return redirect(url_for('buy_feed'))

# ==============================================================================
# PART 6: APPLICATION CONTROLLERS (NEURAL & OUTREACH ENGINES)
# ==============================================================================

# ------------------------------------------------------------------------------
# 17. NEURAL AGENT CONTROLLER (AI)
# ------------------------------------------------------------------------------

@app.route('/ai-agent')
def ai_agent():
    """
    The AI Dashboard.
    Enforces the $50/mo subscription or 48H Trial.
    If unlocked, calls the Groq API to generate content.
    """
    if 'user_email' not in session: return redirect(url_for('index'))
    
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()

    # 1. ACCESS CHECK LOGIC
    has_access = False
    is_trial = False
    
    # Check Paid Status
    if user['has_ai_access'] == 1:
        has_access = True
        
    # Check Trial Status
    if user['ai_trial_end_date']:
        trial_end = datetime.fromisoformat(user['ai_trial_end_date'])
        if datetime.now() < trial_end:
            has_access = True
            is_trial = True

    # 2. LOCKED STATE UI
    if not has_access:
        content = f"""
        <div class="max-w-4xl mx-auto text-center py-20">
            <h2 class="text-6xl font-titan-header text-indigo-400 mb-8">Neural Agent Locked</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                <!-- Value Prop -->
                <div class="titan-card p-10 text-left border-indigo-900/40">
                    <h3 class="text-2xl font-black uppercase text-white mb-4">Why Activate?</h3>
                    <ul class="space-y-4 text-sm text-zinc-400">
                        <li class="flex items-center"><span class="mr-2 text-indigo-500">●</span> Automated Intellectual Content Generation</li>
                        <li class="flex items-center"><span class="mr-2 text-indigo-500">●</span> Stoic & Wealth Philosophy Framework</li>
                        <li class="flex items-center"><span class="mr-2 text-indigo-500">●</span> Viral TikTok/Reels Scripting</li>
                        <li class="flex items-center"><span class="mr-2 text-indigo-500">●</span> Build Authority While You Sleep</li>
                    </ul>
                </div>
                
                <!-- Pricing Options -->
                <div class="titan-card p-10 flex flex-col justify-center bg-zinc-900/50">
                    <a href="/activate-trial" class="btn-titan-ai w-full mb-6">Start 48H No-CC Trial</a>
                    
                    <div class="relative flex py-5 items-center">
                        <div class="flex-grow border-t border-zinc-800"></div>
                        <span class="flex-shrink-0 mx-4 text-[10px] uppercase text-zinc-600 font-bold">Or Full Access</span>
                        <div class="flex-grow border-t border-zinc-800"></div>
                    </div>

                    <form action="/create-checkout-session" method="POST">
                        <input type="hidden" name="product_key" value="AI_MONTHLY">
                        <button class="btn-titan-outline w-full hover:bg-white hover:text-black hover:border-white">
                            $50 / Month Subscription
                        </button>
                    </form>
                </div>
            </div>
        </div>
        """
        return render_ui(content, user)

    # 3. ACTIVE STATE UI (Content Generation)
    # Generate content using the Neural Engine logic from Part 2
    ai_output = generate_neural_content(strategy="Intellectual")
    
    # Check if this content needs to be logged
    with get_db() as conn:
        conn.execute("INSERT INTO ai_content (user_email, content_body) VALUES (?, ?)", (user['email'], ai_output))
        conn.commit()

    trial_banner = ""
    if is_trial:
        time_left = datetime.fromisoformat(user['ai_trial_end_date']) - datetime.now()
        hours_left = int(time_left.total_seconds() / 3600)
        trial_banner = f"""
        <div class="col-span-12 mb-8 p-4 bg-indigo-900/20 border border-indigo-500/30 rounded-xl flex justify-between items-center">
            <span class="text-xs font-bold text-indigo-300 uppercase">⚠️ Trial Active: {hours_left} Hours Remaining</span>
            <form action="/create-checkout-session" method="POST">
                <input type="hidden" name="product_key" value="AI_MONTHLY">
                <button class="text-[10px] font-black uppercase bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-500 transition">Upgrade Now</button>
            </form>
        </div>
        """

    content = f"""
    <div class="grid-titan-dashboard">
        {trial_banner}
        
        <div class="col-span-12 flex justify-between items-center mb-12">
            <div>
                <h2 class="text-4xl font-titan-header text-indigo-400">Neural Terminal</h2>
                <p class="text-xs font-mono text-zinc-500 mt-2 uppercase tracking-widest">Model: Llama-3-8b-Groq // Strategy: Stoic Wealth</p>
            </div>
            <div class="flex items-center space-x-3">
                <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span class="text-[10px] font-black uppercase text-zinc-400">System Online</span>
            </div>
        </div>

        <!-- GENERATED OUTPUT CARD -->
        <div class="col-span-12 md:col-span-8 titan-card p-12 bg-zinc-900/30 border-indigo-900/30">
            <h3 class="text-[10px] font-black uppercase text-indigo-500 mb-8 tracking-[0.3em]">Current Output Stream</h3>
            
            <div class="font-mono text-xl md:text-2xl text-zinc-100 leading-relaxed mb-12 relative z-10">
                "{ai_output}"
            </div>
            
            <!-- Decorative Background Element -->
            <div class="absolute top-0 right-0 p-8 text-9xl opacity-5 pointer-events-none select-none">🤖</div>

            <div class="flex space-x-4 border-t border-zinc-800 pt-8">
                <button onclick="window.location.reload()" class="btn-titan-primary text-xs">Regenerate Signal</button>
                <button class="btn-titan-outline text-xs">Copy to Clipboard</button>
            </div>
        </div>

        <!-- SIDEBAR STATS -->
        <div class="col-span-12 md:col-span-4 space-y-6">
            <div class="titan-card p-8">
                <p class="text-[9px] font-black uppercase text-zinc-500 mb-2">Automation Status</p>
                <p class="text-xl font-black text-white uppercase">Manual Override</p>
                <p class="text-[9px] text-zinc-600 mt-2">Auto-posting disabled in safe mode.</p>
            </div>
            <div class="titan-card p-8">
                <p class="text-[9px] font-black uppercase text-zinc-500 mb-2">Content Strategy</p>
                <p class="text-xl font-black text-indigo-400 uppercase">Intellectual</p>
                <p class="text-[9px] text-zinc-600 mt-2">Targeting high-net-worth psychology.</p>
            </div>
        </div>
    </div>
    """
    return render_ui(content, user)

# ------------------------------------------------------------------------------
# 18. OUTREACH CONTROLLER (EMAIL MACHINE)
# ------------------------------------------------------------------------------

@app.route('/outreach', methods=['GET', 'POST'])
def outreach():
    """
    The Email Broadcast Dashboard.
    Enforces the $20 or $3/wk Paywall.
    Handles form submission to trigger the Gmail API.
    """
    if 'user_email' not in session: return redirect(url_for('index'))
    
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        
    # 1. ACCESS CHECK
    if not user['has_email_access']:
        content = f"""
        <div class="max-w-4xl mx-auto text-center py-20">
            <h2 class="text-6xl font-titan-header mb-8 text-white">Broadcast Engine Locked</h2>
            
            <div class="titan-card p-12 bg-zinc-900/80">
                <p class="text-lg text-zinc-400 mb-12 max-w-2xl mx-auto">
                    Unlock the capability to broadcast deals directly to investor inboxes using your own Gmail credentials.
                    <span class="text-white font-bold">Zero spam flags. 100% deliverability.</span>
                </p>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-2xl mx-auto">
                    <!-- Option A: Subscription -->
                    <div class="p-6 border border-zinc-800 rounded-2xl hover:border-white transition cursor-pointer group">
                        <p class="text-xs font-black uppercase text-zinc-500 mb-2">Weekly Access</p>
                        <p class="text-3xl font-black text-white mb-6">$3.00 <span class="text-sm font-normal text-zinc-600">/ week</span></p>
                        <form action="/create-checkout-session" method="POST">
                            <input type="hidden" name="product_key" value="EMAIL_WEEKLY">
                            <button class="btn-titan-outline w-full group-hover:bg-white group-hover:text-black">Subscribe</button>
                        </form>
                    </div>

                    <!-- Option B: Lifetime -->
                    <div class="p-6 border-2 border-white rounded-2xl bg-white text-black relative overflow-hidden">
                        <div class="absolute top-0 right-0 bg-black text-white text-[8px] font-bold px-2 py-1 uppercase">Best Value</div>
                        <p class="text-xs font-black uppercase text-zinc-600 mb-2">Lifetime Access</p>
                        <p class="text-3xl font-black mb-6">$20.00 <span class="text-sm font-normal text-zinc-600">/ once</span></p>
                        <form action="/create-checkout-session" method="POST">
                            <input type="hidden" name="product_key" value="EMAIL_LIFETIME">
                            <button class="btn-titan-primary w-full bg-black text-white hover:bg-zinc-800 border-none">Buy Forever</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
        """
        return render_ui(content, user)

    # 2. LOGIC: HANDLE BROADCAST
    if request.method == 'POST':
        # Parse Form Data
        raw_targets = request.form.get('targets', '')
        subject = request.form.get('subject', '')
        body = request.form.get('body', '')
        
        target_list = [t.strip() for t in raw_targets.split(',') if t.strip()]
        
        # Execute Sending Logic (from Part 2)
        success, message = send_secure_gmail(user['email'], target_list, subject, body)
        
        # Show Result
        status_color = "text-green-500" if success else "text-red-500"
        flash_msg = f'<span class="{status_color}">{message}</span>'
        
        # Return to page (flash message handled by UI renderer is complex in string mode, 
        # so we inject a simple result page or redirect)
        # For this architecture, we will re-render with a success flag
        # (Simplified for the sake of the script length constraints)
        
    # 3. ACTIVE UI
    content = f"""
    <div class="grid-titan-dashboard">
        <div class="col-span-12 mb-8">
            <h2 class="text-4xl font-titan-header text-white">Broadcast Center</h2>
            <p class="text-xs font-mono text-zinc-500 mt-2 uppercase tracking-widest">Routing via Gmail API OAuth 2.0</p>
        </div>

        <!-- COMPOSER -->
        <div class="col-span-12 md:col-span-8 titan-card p-10">
            <form method="POST" class="space-y-6">
                <div>
                    <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Target Frequencies (Emails)</label>
                    <input type="text" name="targets" placeholder="investor1@example.com, investor2@example.com" required>
                    <p class="text-[9px] text-zinc-600 mt-2">Separate multiple targets with commas.</p>
                </div>
                
                <div>
                    <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Signal Header (Subject)</label>
                    <input type="text" name="subject" placeholder="OFF-MARKET: 40% Under ARV - [Address]" required>
                </div>

                <div>
                    <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Payload (Body)</label>
                    <textarea name="body" class="h-64 font-mono text-sm leading-relaxed" placeholder="Deal Details..." required></textarea>
                </div>

                <div class="pt-6 border-t border-zinc-900 flex justify-end">
                    <button class="btn-titan-primary px-8 py-4">Transmit Signal</button>
                </div>
            </form>
        </div>

        <!-- SIDEBAR GUIDANCE -->
        <div class="col-span-12 md:col-span-4 space-y-6">
            <div class="titan-card p-8 bg-zinc-900/50">
                <h4 class="text-xs font-black uppercase text-white mb-4">Protocol Guidelines</h4>
                <ul class="space-y-3 text-[10px] text-zinc-400 uppercase tracking-wide">
                    <li>• Keep subjects under 60 chars</li>
                    <li>• Include ROI in the first line</li>
                    <li>• Do not use spam triggers ($$$, FREE)</li>
                    <li>• Rate Limit: 500 / Day</li>
                </ul>
            </div>
            
            <div class="titan-card p-8">
                <h4 class="text-xs font-black uppercase text-zinc-500 mb-4">Connection Status</h4>
                <div class="flex items-center space-x-3 mb-2">
                    <div class="w-2 h-2 bg-green-500 rounded-full"></div>
                    <span class="text-xs font-bold text-white">Gmail API Linked</span>
                </div>
                <p class="text-[9px] text-zinc-600">Token Refresh: Auto</p>
            </div>
        </div>
    </div>
    """
    return render_ui(content, user)
# ==============================================================================
# PART 7: APPLICATION CONTROLLERS (SELLER ENGINE)
# ==============================================================================

# ------------------------------------------------------------------------------
# 19. SELLER LISTING CONTROLLER
# ------------------------------------------------------------------------------

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    """
    The Seller Dashboard.
    Allows users to upload assets to the Global Feed.
    Calculates estimated metrics (ARV, Profit) automatically.
    """
    if 'user_email' not in session: return redirect(url_for('index'))
    
    # 1. HANDLE FORM SUBMISSION
    if request.method == 'POST':
        try:
            # Extract Form Data
            f = request.form
            address = f.get('address')
            price = int(f.get('price'))
            sqft = int(f.get('sqft')) if f.get('sqft') else 0
            repair = int(f.get('repair')) if f.get('repair') else 0
            zip_code = f.get('zip')
            
            # Auto-Calculate ARV (Mock Algorithm for Demo)
            # In production, this would hit Zillow/Redfin API
            # Rule: ARV is typically listing price + repairs + 20% margin
            estimated_arv = int((price + repair) * 1.35)
            
            # Handle Image Upload
            file = request.files.get('photo')
            filename = None
            if file and file.filename != '':
                # Secure the filename to prevent path traversal attacks
                original_name = secure_filename(file.filename)
                # Add timestamp to make unique
                timestamp = int(time.time())
                filename = f"{timestamp}_{original_name}"
                
                # Save to Upload Folder (Ephemeral on Render)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # Insert into Database
            with get_db() as conn:
                conn.execute("""
                    INSERT INTO leads (
                        address, 
                        asking_price, 
                        arv, 
                        est_repair_cost, 
                        sqft, 
                        zip_code, 
                        image_path, 
                        seller_email, 
                        status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """, (address, price, estimated_arv, repair, sqft, zip_code, filename, session['user_email']))
                conn.commit()
                
            # Redirect to Feed to see the new item
            # (In a real app, use flash("Asset Listed Successfully"))
            return redirect(url_for('buy_feed'))
            
        except Exception as e:
            print(f"Listing Error: {e}")
            # Fallback re-render on error would go here

    # 2. RENDER SELLER UI
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        # Get history of user's uploads
        my_listings = conn.execute("SELECT * FROM leads WHERE seller_email = ?", (session['user_email'],)).fetchall()

    # Generate History HTML
    history_html = ""
    if my_listings:
        rows = ""
        for item in my_listings:
            rows += f"""
            <div class="flex justify-between items-center p-4 bg-zinc-900 rounded-xl mb-2">
                <div>
                    <p class="text-[10px] font-bold uppercase text-white">{item['address']}</p>
                    <p class="text-[9px] text-zinc-500">${"{:,.0f}".format(item['asking_price'])}</p>
                </div>
                <span class="text-[9px] uppercase px-2 py-1 bg-green-900/20 text-green-500 rounded">Active</span>
            </div>
            """
        history_html = f"""
        <div class="titan-card p-8 mt-8">
            <h3 class="text-xs font-black uppercase text-zinc-500 mb-6">Your Asset Portfolio</h3>
            {rows}
        </div>
        """

    content = f"""
    <div class="grid-titan-dashboard">
        
        <div class="col-span-12 mb-8 text-center">
            <h2 class="text-4xl font-titan-header text-white">List New Asset</h2>
            <p class="text-xs font-mono text-zinc-500 mt-2 uppercase tracking-widest">0% Commission Protocol Active</p>
        </div>

        <!-- LISTING FORM -->
        <div class="col-span-12 md:col-span-8 md:col-start-3 titan-card p-12">
            <form method="POST" enctype="multipart/form-data" class="space-y-8">
                
                <!-- Section 1: Core Data -->
                <div>
                    <h4 class="text-xs font-black uppercase text-white mb-6 border-b border-zinc-800 pb-2">Asset Identifiers</h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div class="md:col-span-2">
                            <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Property Address</label>
                            <input type="text" name="address" placeholder="1234 Main St, City, State" required>
                        </div>
                        <div>
                            <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Zip Code</label>
                            <input type="text" name="zip" placeholder="90210" required>
                        </div>
                        <div>
                            <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Square Footage</label>
                            <input type="number" name="sqft" placeholder="2500">
                        </div>
                    </div>
                </div>

                <!-- Section 2: Financials -->
                <div>
                    <h4 class="text-xs font-black uppercase text-white mb-6 border-b border-zinc-800 pb-2">Financial Data</h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Asking Price ($)</label>
                            <input type="number" name="price" placeholder="500000" required>
                        </div>
                        <div>
                            <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Est. Repair Cost ($)</label>
                            <input type="number" name="repair" placeholder="50000">
                        </div>
                    </div>
                </div>

                <!-- Section 3: Visuals -->
                <div>
                    <h4 class="text-xs font-black uppercase text-white mb-6 border-b border-zinc-800 pb-2">Visual Evidence</h4>
                    <div class="p-8 border-2 border-dashed border-zinc-800 rounded-2xl bg-zinc-900/50 text-center hover:border-zinc-600 transition">
                        <input type="file" name="photo" class="hidden" id="file-upload">
                        <label for="file-upload" class="cursor-pointer">
                            <div class="text-2xl mb-2">📸</div>
                            <span class="text-[10px] font-bold uppercase text-zinc-400">Click to Upload Primary Photo</span>
                        </label>
                    </div>
                </div>

                <!-- Submit -->
                <div class="pt-6">
                    <button class="btn-titan-primary w-full py-5 text-sm">Broadcast to Global Feed</button>
                    <p class="text-[9px] text-zinc-600 text-center mt-4 uppercase">
                        By listing, you agree to the Titan Protocol Seller Terms.
                    </p>
                </div>

            </form>
        </div>
        
        <!-- HISTORY SIDEBAR (Only if history exists) -->
        <div class="col-span-12 md:col-span-8 md:col-start-3">
            {history_html}
        </div>

    </div>
    """
    return render_ui(content, user)

# ------------------------------------------------------------------------------
# 20. FILE SERVING UTILITY
# ------------------------------------------------------------------------------

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """
    Serves images from the upload folder.
    Necessary because files aren't in the static folder on Render.
    """
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ==============================================================================
# PART 7: APPLICATION CONTROLLERS (SELLER ENGINE)
# ==============================================================================

# ------------------------------------------------------------------------------
# 19. SELLER LISTING CONTROLLER
# ------------------------------------------------------------------------------

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    """
    The Seller Dashboard.
    Allows users to upload assets to the Global Feed.
    Calculates estimated metrics (ARV, Profit) automatically.
    """
    if 'user_email' not in session: return redirect(url_for('index'))
    
    # 1. HANDLE FORM SUBMISSION
    if request.method == 'POST':
        try:
            # Extract Form Data
            f = request.form
            address = f.get('address')
            price = int(f.get('price'))
            sqft = int(f.get('sqft')) if f.get('sqft') else 0
            repair = int(f.get('repair')) if f.get('repair') else 0
            zip_code = f.get('zip')
            
            # Auto-Calculate ARV (Mock Algorithm for Demo)
            # In production, this would hit Zillow/Redfin API
            # Rule: ARV is typically listing price + repairs + 20% margin
            estimated_arv = int((price + repair) * 1.35)
            
            # Handle Image Upload
            file = request.files.get('photo')
            filename = None
            if file and file.filename != '':
                # Secure the filename to prevent path traversal attacks
                original_name = secure_filename(file.filename)
                # Add timestamp to make unique
                timestamp = int(time.time())
                filename = f"{timestamp}_{original_name}"
                
                # Save to Upload Folder (Ephemeral on Render)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # Insert into Database
            with get_db() as conn:
                conn.execute("""
                    INSERT INTO leads (
                        address, 
                        asking_price, 
                        arv, 
                        est_repair_cost, 
                        sqft, 
                        zip_code, 
                        image_path, 
                        seller_email, 
                        status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """, (address, price, estimated_arv, repair, sqft, zip_code, filename, session['user_email']))
                conn.commit()
                
            # Redirect to Feed to see the new item
            # (In a real app, use flash("Asset Listed Successfully"))
            return redirect(url_for('buy_feed'))
            
        except Exception as e:
            print(f"Listing Error: {e}")
            # Fallback re-render on error would go here

    # 2. RENDER SELLER UI
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        # Get history of user's uploads
        my_listings = conn.execute("SELECT * FROM leads WHERE seller_email = ?", (session['user_email'],)).fetchall()

    # Generate History HTML
    history_html = ""
    if my_listings:
        rows = ""
        for item in my_listings:
            rows += f"""
            <div class="flex justify-between items-center p-4 bg-zinc-900 rounded-xl mb-2">
                <div>
                    <p class="text-[10px] font-bold uppercase text-white">{item['address']}</p>
                    <p class="text-[9px] text-zinc-500">${"{:,.0f}".format(item['asking_price'])}</p>
                </div>
                <span class="text-[9px] uppercase px-2 py-1 bg-green-900/20 text-green-500 rounded">Active</span>
            </div>
            """
        history_html = f"""
        <div class="titan-card p-8 mt-8">
            <h3 class="text-xs font-black uppercase text-zinc-500 mb-6">Your Asset Portfolio</h3>
            {rows}
        </div>
        """

    content = f"""
    <div class="grid-titan-dashboard">
        
        <div class="col-span-12 mb-8 text-center">
            <h2 class="text-4xl font-titan-header text-white">List New Asset</h2>
            <p class="text-xs font-mono text-zinc-500 mt-2 uppercase tracking-widest">0% Commission Protocol Active</p>
        </div>

        <!-- LISTING FORM -->
        <div class="col-span-12 md:col-span-8 md:col-start-3 titan-card p-12">
            <form method="POST" enctype="multipart/form-data" class="space-y-8">
                
                <!-- Section 1: Core Data -->
                <div>
                    <h4 class="text-xs font-black uppercase text-white mb-6 border-b border-zinc-800 pb-2">Asset Identifiers</h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div class="md:col-span-2">
                            <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Property Address</label>
                            <input type="text" name="address" placeholder="1234 Main St, City, State" required>
                        </div>
                        <div>
                            <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Zip Code</label>
                            <input type="text" name="zip" placeholder="90210" required>
                        </div>
                        <div>
                            <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Square Footage</label>
                            <input type="number" name="sqft" placeholder="2500">
                        </div>
                    </div>
                </div>

                <!-- Section 2: Financials -->
                <div>
                    <h4 class="text-xs font-black uppercase text-white mb-6 border-b border-zinc-800 pb-2">Financial Data</h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Asking Price ($)</label>
                            <input type="number" name="price" placeholder="500000" required>
                        </div>
                        <div>
                            <label class="block text-[10px] font-black uppercase text-zinc-500 mb-2">Est. Repair Cost ($)</label>
                            <input type="number" name="repair" placeholder="50000">
                        </div>
                    </div>
                </div>

                <!-- Section 3: Visuals -->
                <div>
                    <h4 class="text-xs font-black uppercase text-white mb-6 border-b border-zinc-800 pb-2">Visual Evidence</h4>
                    <div class="p-8 border-2 border-dashed border-zinc-800 rounded-2xl bg-zinc-900/50 text-center hover:border-zinc-600 transition">
                        <input type="file" name="photo" class="hidden" id="file-upload">
                        <label for="file-upload" class="cursor-pointer">
                            <div class="text-2xl mb-2">📸</div>
                            <span class="text-[10px] font-bold uppercase text-zinc-400">Click to Upload Primary Photo</span>
                        </label>
                    </div>
                </div>

                <!-- Submit -->
                <div class="pt-6">
                    <button class="btn-titan-primary w-full py-5 text-sm">Broadcast to Global Feed</button>
                    <p class="text-[9px] text-zinc-600 text-center mt-4 uppercase">
                        By listing, you agree to the Titan Protocol Seller Terms.
                    </p>
                </div>

            </form>
        </div>
        
        <!-- HISTORY SIDEBAR (Only if history exists) -->
        <div class="col-span-12 md:col-span-8 md:col-start-3">
            {history_html}
        </div>

    </div>
    """
    return render_ui(content, user)

# ------------------------------------------------------------------------------
# 20. FILE SERVING UTILITY
# ------------------------------------------------------------------------------

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """
    Serves images from the upload folder.
    Necessary because files aren't in the static folder on Render.
    """
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ==============================================================================
# END OF PART 7
# PASTE PART 8 BELOW THIS LINE
# ==============================================================================
# ==============================================================================
# PART 8: SYSTEM INITIALIZATION & ENTRY POINT
# ==============================================================================

# ------------------------------------------------------------------------------
# 21. LEGAL & SYSTEM PAGES
# ------------------------------------------------------------------------------

@app.route('/privacy')
def privacy():
    """
    The Privacy Policy Page.
    Required for Google OAuth verification and legal compliance.
    """
    content = """
    <div class="max-w-3xl mx-auto titan-card p-12 text-zinc-400 text-sm leading-relaxed">
        <h2 class="text-4xl font-titan-header text-white mb-12">Privacy Protocol</h2>
        
        <div class="space-y-8">
            <section>
                <h3 class="text-xs font-black uppercase text-white mb-2">1. Data Sovereignty</h3>
                <p>Pro-Exchange acknowledges that your data belongs to you. We do not sell, trade, or rent user data to third-party brokers. All data persistence is localized to your specific account context.</p>
            </section>
            
            <section>
                <h3 class="text-xs font-black uppercase text-white mb-2">2. Google API Scope Usage</h3>
                <p>The application utilizes the <span class="font-mono text-xs bg-zinc-800 px-1">https://www.googleapis.com/auth/gmail.send</span> scope strictly for the purpose of executing user-initiated email broadcasts via the 'Email Machine' module. The system does not read, index, or store your incoming emails. Tokens are encrypted at rest using AES-256 standards via the Fernet implementation.</p>
            </section>
            
            <section>
                <h3 class="text-xs font-black uppercase text-white mb-2">3. AI & Neural Data</h3>
                <p>Content generation is processed via the Groq API using Llama-3 models. No personal user data is trained upon. Prompts are ephemeral and strictly used to generate the requested marketing copy.</p>
            </section>
            
            <section>
                <h3 class="text-xs font-black uppercase text-white mb-2">4. Financial Security</h3>
                <p>All payment processing is offloaded to Stripe, Inc. Pro-Exchange does not touch, store, or transmit raw credit card data. Subscription management is handled via the Stripe Customer Portal.</p>
            </section>
        </div>

        <div class="mt-12 pt-12 border-t border-zinc-900">
            <a href="/" class="btn-titan-outline text-[10px]">Return to Dashboard</a>
        </div>
    </div>
    """
    # If user is logged in, wrap in logged-in UI, else public UI
    user = None
    if 'user_email' in session:
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (session['user_email'],)).fetchone()
            
    return render_ui(content, user)

# ------------------------------------------------------------------------------
# 22. HEALTH CHECK & MONITORING
# ------------------------------------------------------------------------------

@app.route('/health')
def health_check():
    """
    Simple endpoint for uptime monitoring services.
    """
    return jsonify({
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "version": "v28.0.4"
    }), 200

# ------------------------------------------------------------------------------
# 23. SERVER ENTRY POINT
# ------------------------------------------------------------------------------

if __name__ == '__main__':
    # 1. Environment Verification
    print(">>> TITAN PROTOCOL v28 INITIATING...")
    
    # Check Critical Keys
    if not os.environ.get("STRIPE_SECRET_KEY"):
        print("!!! WARNING: STRIPE_SECRET_KEY IS MISSING")
    if not os.environ.get("GROQ_API_KEY"):
        print("!!! WARNING: GROQ_API_KEY IS MISSING (AI will be disabled)")
    if not os.environ.get("GOOGLE_CLIENT_ID"):
        print("!!! WARNING: GOOGLE_CLIENT_ID IS MISSING (Auth will fail)")

    # 2. Storage Initialization
    # Ensure upload directory exists before starting
    if not os.path.exists(UPLOAD_FOLDER):
        try:
            os.makedirs(UPLOAD_FOLDER)
            print(f">>> STORAGE MOUNTED AT: {UPLOAD_FOLDER}")
        except Exception as e:
            print(f"!!! CRITICAL STORAGE ERROR: {e}")

    # 3. Port Configuration
    # Render assigns a dynamic port via the 'PORT' environment variable.
    # Default to 5000 for local development.
    port = int(os.environ.get("PORT", 5000))
    
    # 4. Launch Server
    # 'host=0.0.0.0' makes the server accessible externally (required for Render)
    app.run(host='0.0.0.0', port=port, debug=False)

# ==============================================================================
# END OF APPLICATION CODE
# ==============================================================================

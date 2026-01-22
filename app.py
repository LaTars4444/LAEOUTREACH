import os
import random
import time
import base64
import json
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText

# Third-party imports
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_required, current_user, login_user, logout_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import stripe
from groq import Groq

# ---------------------------------------------------------
# 1. CONFIGURATION & SETUP
# ---------------------------------------------------------
app = Flask(__name__)

# Security & Config
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_dev_key')

# Database: Try Persistent Disk, Fallback to Local
if os.path.exists('/var/data'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/data/titan.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///titan.db'
    
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Init Database
db = SQLAlchemy(app)

# Init Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Init APIs
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
UPLOAD_FOLDER = 'static/uploads'

# ---------------------------------------------------------
# 2. AUTO-GENERATE HTML TEMPLATES (With Deal Hunter)
# ---------------------------------------------------------
html_templates = {
    'base.html': """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TITAN | Real Estate AI</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }</style>
</head>
<body class="bg-light">
<nav class="navbar navbar-expand-lg navbar-dark bg-dark">
    <div class="container">
        <a class="navbar-brand" href="/">TITAN ⚡</a>
        <div class="collapse navbar-collapse">
            <ul class="navbar-nav ms-auto">
                {% if current_user.is_authenticated %}
                    <li class="nav-item"><a class="nav-link" href="/dashboard">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/buy_box">Buy Box</a></li>
                    <li class="nav-item"><a class="nav-link" href="/sell">Sell Property</a></li>
                    <li class="nav-item"><a class="nav-link text-danger" href="/logout">Logout</a></li>
                {% else %}
                    <li class="nav-item"><a class="nav-link" href="/login">Login</a></li>
                    <li class="nav-item"><a class="nav-link" href="/register">Register</a></li>
                {% endif %}
            </ul>
        </div>
    </div>
</nav>
<div class="container mt-4">
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    {% block content %}{% endblock %}
</div>
</body>
</html>
""",
    'login.html': """
{% extends "base.html" %}
{% block content %}
<div class="card mx-auto mt-5 shadow" style="max-width: 400px;">
    <div class="card-body p-4">
        <h3 class="card-title text-center mb-4">Login to Titan</h3>
        <form method="POST">
            <div class="mb-3"><label>Email</label><input type="email" name="email" class="form-control" required></div>
            <div class="mb-3"><label>Password</label><input type="password" name="password" class="form-control" required></div>
            <button type="submit" class="btn btn-primary w-100">Login</button>
        </form>
        <p class="mt-3 text-center">No account? <a href="/register">Register here</a></p>
    </div>
</div>
{% endblock %}
""",
    'register.html': """
{% extends "base.html" %}
{% block content %}
<div class="card mx-auto mt-5 shadow" style="max-width: 400px;">
    <div class="card-body p-4">
        <h3 class="card-title text-center mb-4">Create Account</h3>
        <form method="POST">
            <div class="mb-3"><label>Email</label><input type="email" name="email" class="form-control" required></div>
            <div class="mb-3"><label>Password</label><input type="password" name="password" class="form-control" required></div>
            <button type="submit" class="btn btn-success w-100">Start Free Trial</button>
        </form>
        <p class="mt-3 text-center">Already have an account? <a href="/login">Login here</a></p>
    </div>
</div>
{% endblock %}
""",
    'dashboard.html': """
{% extends "base.html" %}
{% block content %}
<div class="p-4 mb-4 bg-white rounded-3 shadow-sm border">
    <h1>🚀 Welcome, {{ user.email }}</h1>
    <p>Status: <span class="badge bg-info text-dark">{{ user.subscription_status|upper }}</span></p>
    {% if user.subscription_end %}
        <p class="small text-muted">Access valid until: {{ user.subscription_end }}</p>
    {% endif %}
</div>

<div class="row">
    <!-- DEAL HUNTER (NEW) -->
    <div class="col-12 mb-4">
        <div class="card shadow-sm border-warning">
            <div class="card-header bg-warning text-dark d-flex justify-content-between">
                <strong>🕵️ Deep Search Deal Hunter</strong>
                <span class="badge bg-dark">Free Foreclosure Data</span>
            </div>
            <div class="card-body">
                <div class="row g-2">
                    <div class="col-md-3">
                        <input type="text" id="targetCity" class="form-control" placeholder="City (e.g. Austin)">
                    </div>
                    <div class="col-md-3">
                        <input type="text" id="targetState" class="form-control" placeholder="State (e.g. TX)">
                    </div>
                    <div class="col-md-3">
                        <input type="text" id="targetZip" class="form-control" placeholder="Zip (e.g. 78701)">
                    </div>
                </div>
                <div class="mt-3 d-flex gap-2 flex-wrap">
                    <button onclick="huntDeals('hud')" class="btn btn-outline-dark">🏛️ HUD Foreclosures</button>
                    <button onclick="huntDeals('tax')" class="btn btn-outline-danger">⚖️ Tax Asset Sales</button>
                    <button onclick="huntDeals('fsbo')" class="btn btn-outline-success">🏡 Hidden FSBOs</button>
                    <button onclick="huntDeals('pre')" class="btn btn-outline-primary">📉 Pre-Foreclosures</button>
                </div>
                <small class="text-muted mt-2 d-block">*Opens official gov/listing sites with advanced search filters applied.</small>
            </div>
        </div>
    </div>

    <!-- AI CONTENT GENERATOR -->
    <div class="col-lg-7 mb-4">
        <div class="card h-100 shadow-sm">
            <div class="card-header bg-dark text-white d-flex justify-content-between align-items-center">
                <span>🤖 Titan AI Marketing</span>
                <span class="badge bg-secondary">Llama 3.3 (High-Perf)</span>
            </div>
            <div class="card-body">
                <label class="form-label">What are you marketing?</label>
                <textarea id="aiInput" class="form-control mb-3" rows="3" placeholder="E.g. 3-bed fixer upper in Austin, TX with huge backyard..."></textarea>
                
                <p class="mb-2 fw-bold">Generate Content:</p>
                <div class="d-flex gap-2 flex-wrap">
                    <button onclick="runAI('email')" class="btn btn-outline-primary btn-sm">📧 Cold Email</button>
                    <button onclick="runAI('listing')" class="btn btn-outline-success btn-sm">🏡 Zillow Listing</button>
                    <button onclick="runAI('tiktok')" class="btn btn-outline-dark btn-sm">🎵 TikTok Script</button>
                    <button onclick="runAI('facebook')" class="btn btn-outline-primary btn-sm">📘 FB Ad</button>
                    <button onclick="runAI('instagram')" class="btn btn-outline-danger btn-sm">📸 Insta Caption</button>
                    <button onclick="runAI('youtube')" class="btn btn-outline-danger btn-sm">▶️ YT Shorts</button>
                </div>

                <div id="aiResult" class="mt-3 p-3 bg-light border rounded d-none" style="white-space: pre-wrap;"></div>
            </div>
        </div>
    </div>

    <!-- EMAIL MACHINE -->
    <div class="col-lg-5 mb-4">
        <div class="card h-100 shadow-sm">
            <div class="card-header bg-danger text-white">📧 Email Machine</div>
            <div class="card-body">
                <p><strong>Connection Status:</strong> 
                {% if user.google_token %} 
                    <span class="badge bg-success">Connected</span> 
                {% else %} 
                    <span class="badge bg-secondary">Disconnected</span> 
                {% endif %}
                </p>
                
                <hr>
                <label>Recipients (Comma separated)</label>
                <textarea id="recipients" class="form-control mb-2" placeholder="lead1@gmail.com, lead2@yahoo.com"></textarea>
                
                <label>Subject</label>
                <input id="subject" type="text" class="form-control mb-2" placeholder="Cash offer for your property">
                
                <label>Body (HTML allowed)</label>
                <textarea id="body" class="form-control mb-3" rows="3" placeholder="Hi there, I saw your property..."></textarea>
                
                <button onclick="sendEmails()" class="btn btn-danger w-100">🚀 Launch Campaign</button>
                <div id="emailStatus" class="mt-2 small text-muted"></div>
            </div>
        </div>
    </div>
</div>

<script>
async function runAI(type) {
    const input = document.getElementById('aiInput').value;
    const resultBox = document.getElementById('aiResult');
    
    if(!input) { alert("Please enter property details first!"); return; }

    resultBox.classList.remove('d-none');
    resultBox.innerText = "Titan AI is writing your " + type + "...";
    
    const res = await fetch('/ai/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({type: type, input: input})
    });
    
    const data = await res.json();
    resultBox.innerText = data.result || data.error;
}

async function sendEmails() {
    const statusBox = document.getElementById('emailStatus');
    statusBox.innerText = "Initializing campaign...";
    
    const recipients = document.getElementById('recipients').value.split(',').map(e => e.trim());
    const subject = document.getElementById('subject').value;
    const body = document.getElementById('body').value;

    const response = await fetch('/email_machine/send', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({recipients: recipients, subject: subject, body: body})
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const {value, done} = await reader.read();
        if (done) break;
        const text = decoder.decode(value);
        statusBox.innerText += text;
    }
}

function huntDeals(type) {
    const city = document.getElementById('targetCity').value;
    const state = document.getElementById('targetState').value;
    const zip = document.getElementById('targetZip').value;

    if(!city && !zip) { alert("Please enter at least a City or Zip Code"); return; }

    let url = "";
    if(type === 'hud') {
        // Direct link to HUD Homestore for State
        url = "https://www.hudhomestore.gov/Home/Index.aspx"; 
        alert("Redirecting to HUD. Select " + state + " in the map.");
    } else if(type === 'tax') {
        // Google Dork for County Tax Sales
        const query = (city + " " + state + " county tax sale list filetype:pdf").trim();
        url = "https://www.google.com/search?q=" + encodeURIComponent(query);
    } else if(type === 'fsbo') {
        // Craigslist/FSBO deep search
        const query = ("site:craigslist.org " + city + " real estate -broker -agent").trim();
        url = "https://www.google.com/search?q=" + encodeURIComponent(query);
    } else if(type === 'pre') {
        // Zillow Pre-foreclosure filter
        url = "https://www.zillow.com/homes/for_sale/" + city + "-" + state + "_rb/?searchQueryState=%7B%22isPreMarketForeclosure%22%3Atrue%7D";
    }

    window.open(url, '_blank');
}
</script>
{% endblock %}
""",
    'buy_box.html': """
{% extends "base.html" %}
{% block content %}
<div class="container mt-5">
    <h2>Adjust Your Buy Box</h2>
    <form method="POST">
        <div class="mb-3"><label>Locations</label><input type="text" name="locations" class="form-control" value="{{ user.bb_locations or '' }}"></div>
        <div class="row">
            <div class="col-6 mb-3"><label>Min Price</label><input type="number" name="min_price" class="form-control" value="{{ user.bb_min_price }}"></div>
            <div class="col-6 mb-3"><label>Max Price</label><input type="number" name="max_price" class="form-control" value="{{ user.bb_max_price }}"></div>
        </div>
        <button type="submit" class="btn btn-primary">Save Preferences</button>
    </form>
</div>
{% endblock %}
""",
    'sell.html': """
{% extends "base.html" %}
{% block content %}
<div class="container mt-5">
    <h2>Sell Property</h2>
    <form method="POST" enctype="multipart/form-data">
        <div class="mb-3"><label>Address</label><input type="text" name="address" class="form-control" required></div>
        <div class="mb-3"><label>Price</label><input type="number" name="desired_price" class="form-control" required></div>
        <div class="mb-3"><label>Phone</label><input type="text" name="phone" class="form-control" required></div>
        <button type="submit" class="btn btn-success">Submit for Offer</button>
    </form>
</div>
{% endblock %}
"""
}

# Ensure templates exist (Self-Repairing)
if not os.path.exists('templates'):
    os.makedirs('templates')

for filename, content in html_templates.items():
    filepath = os.path.join('templates', filename)
    with open(filepath, 'w') as f:
        f.write(content.strip())

# ---------------------------------------------------------
# 3. MODELS
# ---------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    google_token = db.Column(db.Text, nullable=True)
    subscription_status = db.Column(db.String(50), default='free') 
    subscription_end = db.Column(db.DateTime, nullable=True)
    # Buy Box
    bb_locations = db.Column(db.String(255))
    bb_min_price = db.Column(db.Integer)
    bb_max_price = db.Column(db.Integer)

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    address = db.Column(db.String(255), nullable=False)
    desired_price = db.Column(db.Integer)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OutreachLog(db.Model):
    __tablename__ = 'outreach_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_email = db.Column(db.String(150), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50)) 
    error_msg = db.Column(db.Text)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# ---------------------------------------------------------
# 4. LOGIC
# ---------------------------------------------------------
def check_access(user, feature):
    if not user: return False
    if user.subscription_status == 'lifetime': return True
    if user.subscription_status in ['weekly', 'monthly']:
        if user.subscription_end and user.subscription_end > datetime.utcnow(): return True
    now = datetime.utcnow()
    # 24h Email Trial, 48h AI Trial
    if feature == 'email' and now < user.created_at + timedelta(hours=24): return True
    if feature == 'ai' and now < user.created_at + timedelta(hours=48): return True
    return False

# ---------------------------------------------------------
# 5. ROUTES
# ---------------------------------------------------------

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user:
            # Fallback for simple/hashed passwords
            try:
                if check_password_hash(user.password, password) or user.password == password:
                    login_user(user)
                    return redirect(url_for('dashboard'))
            except:
                if user.password == password:
                    login_user(user)
                    return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'error')
        else:
            hashed_pw = generate_password_hash(password, method='scrypt')
            new_user = User(email=email, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

# ---------------------------------------------------------
# 6. FEATURE: AI (Social Media + Listings)
# ---------------------------------------------------------
@app.route('/ai/generate', methods=['POST'])
@login_required
def ai_generate():
    if not check_access(current_user, 'ai'):
        return jsonify({'error': 'AI Trial expired. Upgrade for lifetime access.'}), 403
    
    data = request.json
    task = data.get('type', 'email')
    user_input = data.get('input')
    
    if not groq_client: return jsonify({'result': 'System Error: Groq API Key Missing'}), 500

    # SOCIAL MEDIA PERSONAS
    prompts = {
        'email': "You are an elite real estate wholesaler. Write a short, urgent, cold email to a homeowner to buy their house for cash.",
        'listing': "You are a luxury real estate copywriter. Write a Zillow description highlighting features, using sensory words and a call to action.",
        'tiktok': "You are a viral TikTok marketer. Write a 15-second high-energy video script for this property. Include visual cues in [brackets]. Use trending hooks.",
        'facebook': "You are a direct-response ad copywriter. Write a Facebook Ad for this property. Use the AIDA framework (Attention, Interest, Desire, Action).",
        'instagram': "Write an aesthetic Instagram caption for this property. Include 30 relevant real estate hashtags.",
        'youtube': "Write a script for a YouTube Short. Fast-paced, engaging, highlighting the investment potential."
    }
    
    system_msg = prompts.get(task, prompts['email'])

    try:
        chat = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_input}
            ],
            model="llama-3.3-70b-versatile"
        )
        return jsonify({'result': chat.choices[0].message.content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------------------------------------------------
# 7. FEATURE: EMAIL AUTOMATION (Full Logic)
# ---------------------------------------------------------
@app.route('/email_machine/send', methods=['POST'])
@login_required
def send_email_campaign():
    if not check_access(current_user, 'email'):
        return jsonify({'error': 'Trial expired.'}), 403
    
    data = request.json
    recipients = data.get('recipients', [])
    subject = data.get('subject')
    body_template = data.get('body')

    if not current_user.google_token:
        return jsonify({'error': 'Google Account not connected.'}), 400

    creds_data = json.loads(current_user.google_token)
    creds = Credentials.from_authorized_user_info(creds_data)

    if creds.expired and creds.refresh_token:
        try:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            current_user.google_token = creds.to_json()
            db.session.commit()
        except:
            return jsonify({'error': 'Google Token Expired. Re-login.'}), 401

    service = build('gmail', 'v1', credentials=creds)

    def generate_sending_stream():
        yield "Starting campaign...\n"
        for email in recipients:
            try:
                # 5-15 Second Delay
                delay = random.randint(5, 15)
                time.sleep(delay)

                message = MIMEText(body_template, 'html')
                message['to'] = email
                message['subject'] = subject
                raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

                service.users().messages().send(userId='me', body={'raw': raw}).execute()
                
                log = OutreachLog(user_id=current_user.id, recipient_email=email, status='success')
                db.session.add(log)
                db.session.commit()
                yield f"Sent to {email} (Delayed {delay}s)\n"
            except Exception as e:
                log = OutreachLog(user_id=current_user.id, recipient_email=email, status='failed', error_msg=str(e))
                db.session.add(log)
                db.session.commit()
                yield f"Failed to send to {email}: {str(e)}\n"
        yield "Campaign Complete."

    return Response(generate_sending_stream(), mimetype='text/plain')

# ---------------------------------------------------------
# 8. OTHER ROUTES
# ---------------------------------------------------------
@app.route('/buy_box', methods=['GET', 'POST'])
@login_required
def buy_box():
    if request.method == 'POST':
        current_user.bb_locations = request.form.get('locations')
        current_user.bb_min_price = request.form.get('min_price')
        current_user.bb_max_price = request.form.get('max_price')
        db.session.commit()
        flash('Saved', 'success')
    return render_template('buy_box.html', user=current_user)

@app.route('/sell', methods=['GET', 'POST'])
def sell_property():
    if request.method == 'POST':
        flash('Submitted!', 'success')
    return render_template('sell.html')

@app.route('/stripe_webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            client_ref = session.get('client_reference_id')
            user = User.query.get(client_ref)
            if user:
                # Update these IDs
                PRICE_WEEKLY = "price_1SpxexFXcDZgM3Vo0iYmhfpb"
                PRICE_MONTHLY = "price_1SqIjgFXcDZgM3VoEwrUvjWP"
                PRICE_LIFETIME = "price_1Spy7SFXcDZgM3VoVZv71I63"
                
                line_items = stripe.checkout.Session.list_line_items(session['id'], limit=1)
                pid = line_items['data'][0]['price']['id']
                
                if pid == PRICE_LIFETIME: user.subscription_status = 'lifetime'
                elif pid == PRICE_MONTHLY: 
                    user.subscription_status = 'monthly'
                    user.subscription_end = datetime.utcnow() + timedelta(days=30)
                elif pid == PRICE_WEEKLY:
                    user.subscription_status = 'weekly'
                    user.subscription_end = datetime.utcnow() + timedelta(days=7)
                db.session.commit()
    except:
        return 'Error', 400
    return jsonify(success=True)

if __name__ == "__main__":
    app.run(debug=True)

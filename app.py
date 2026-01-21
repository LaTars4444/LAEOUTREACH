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
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from werkzeug.utils import secure_filename
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import stripe
from groq import Groq

# LOCAL IMPORTS (Must match your file structure)
from extensions import db 
from models import User, Lead, OutreachLog 
from access_control import check_access

# ---------------------------------------------------------
# CONFIGURATION & SETUP
# ---------------------------------------------------------
app = Flask(__name__)

# Security & Config
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_dev_key')
# Use persistent disk on Render
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/data/titan.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Assumes you have a login route (not shown here, but required)

# Initialize APIs
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
UPLOAD_FOLDER = 'static/uploads'

# Load User Logic for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create DB Tables on startup
with app.app_context():
    db.create_all()

# ---------------------------------------------------------
# ROUTE: EMAIL AUTOMATION MACHINE
# ---------------------------------------------------------
@app.route('/email_machine/send', methods=['POST'])
@login_required
def send_email_campaign():
    # Strict Access Check
    if not check_access(current_user, 'email'):
        return jsonify({'error': 'Trial expired. Please upgrade.'}), 403

    data = request.json
    recipients = data.get('recipients', [])
    subject = data.get('subject')
    body_template = data.get('body')

    if not current_user.google_token:
        return jsonify({'error': 'Google Account not connected.'}), 400

    creds_data = json.loads(current_user.google_token)
    creds = Credentials.from_authorized_user_info(creds_data)

    # Refresh Token Logic
    if creds.expired and creds.refresh_token:
        try:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            current_user.google_token = creds.to_json()
            db.session.commit()
        except Exception:
            return jsonify({'error': 'Google Token Expired. Re-login.'}), 401

    service = build('gmail', 'v1', credentials=creds)

    def generate_sending_stream():
        yield "Starting campaign...\n"
        
        for email in recipients:
            try:
                # Random Delay 5-15s
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
# ROUTE: TITAN AI (GROQ)
# ---------------------------------------------------------
@app.route('/ai/generate', methods=['POST'])
@login_required
def ai_generate():
    # Strict Access Check
    if not check_access(current_user, 'ai'):
        return jsonify({'error': 'AI Trial expired. Upgrade for lifetime access.'}), 403

    data = request.json
    task_type = data.get('type')
    user_input = data.get('input')

    if not user_input:
        return jsonify({'error': 'Input data required'}), 400

    prompts = {
        'email': "You are an elite real estate wholesaler. Write a short, urgent, cold email to a homeowner.",
        'listing': "You are a luxury real estate copywriter. Write a Zillow description highlighting features.",
        'negotiation': "You are a master negotiator. Provide 3 psychological responses to handle this objection."
    }
    
    system_msg = prompts.get(task_type, prompts['email'])

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_input}
            ],
            model="llama3-8b-8192",
            temperature=0.7,
            max_tokens=500,
        )
        result = chat_completion.choices[0].message.content
        return jsonify({'result': result, 'status': 'success'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------------------------------------------------
# ROUTE: BUY BOX
# ---------------------------------------------------------
@app.route('/buy_box', methods=['GET', 'POST'])
@login_required
def buy_box():
    if request.method == 'POST':
        current_user.bb_property_type = request.form.get('property_type')
        current_user.bb_locations = request.form.get('locations')
        current_user.bb_min_price = request.form.get('min_price')
        current_user.bb_max_price = request.form.get('max_price')
        current_user.bb_condition = request.form.get('condition')
        current_user.bb_strategy = request.form.get('strategy')
        current_user.bb_funding = request.form.get('funding')
        current_user.bb_timeline = request.form.get('timeline')
        
        db.session.commit()
        flash('Buy Box saved.', 'success')
        return redirect(url_for('buy_box'))

    return render_template('buy_box.html', user=current_user)

# ---------------------------------------------------------
# ROUTE: SELLER INTAKE
# ---------------------------------------------------------
@app.route('/sell', methods=['GET', 'POST'])
def sell_property():
    if request.method == 'POST':
        required = ['address', 'property_type', 'desired_price', 'phone']
        for field in required:
            if not request.form.get(field):
                flash(f"Missing {field}", "error")
                return redirect(url_for('sell_property'))

        desired_price = float(request.form.get('desired_price'))
        year_built = int(request.form.get('year_built', 1990))
        age = 2025 - year_built
        repair_est = 5000 + (age * 500)
        arv = desired_price * 1.3
        mao = (arv * 0.7) - repair_est

        photo_url = None
        if 'photos' in request.files:
            file = request.files['photos']
            if file.filename != '':
                filename = secure_filename(file.filename)
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                photo_url = f"/{UPLOAD_FOLDER}/{filename}"

        new_lead = Lead(
            submitter_id=current_user.id if current_user.is_authenticated else None,
            address=request.form.get('address'),
            property_type=request.form.get('property_type'),
            year_built=year_built,
            roof_age=request.form.get('roof_age'),
            hvac_age=request.form.get('hvac_age'),
            condition_plumbing=request.form.get('condition_plumbing'),
            condition_electrical=request.form.get('condition_electrical'),
            condition_overall=request.form.get('condition_overall'),
            occupancy_status=request.form.get('occupancy_status'),
            desired_price=desired_price,
            timeline=request.form.get('timeline'),
            phone=request.form.get('phone'),
            photos_url=photo_url,
            arv_estimate=int(arv),
            repair_estimate=int(repair_est),
            max_allowable_offer=int(mao)
        )
        db.session.add(new_lead)
        db.session.commit()
        
        flash("Property analyzed. Check your email for our offer!", "success")
        return redirect(url_for('sell_property'))

    return render_template('sell.html')

# ---------------------------------------------------------
# ROUTE: STRIPE WEBHOOK
# ---------------------------------------------------------
@app.route('/stripe_webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception:
        return 'Invalid payload', 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        client_reference_id = session.get('client_reference_id')
        
        user = User.query.get(client_reference_id)
        if user:
            line_items = stripe.checkout.Session.list_line_items(session['id'], limit=1)
            price_id = line_items['data'][0]['price']['id']

            # IDs PROVIDED
            PRICE_WEEKLY = "price_1SpxexFXcDZgM3Vo0iYmhfpb"
            PRICE_LIFETIME = "price_1Spy7SFXcDZgM3VoVZv71I63"
            PRICE_MONTHLY = "price_1SqIjgFXcDZgM3VoEwrUvjWP"

            if price_id == PRICE_LIFETIME:
                user.subscription_status = 'lifetime'
                user.subscription_end = None
                
            elif price_id == PRICE_MONTHLY:
                user.subscription_status = 'monthly'
                user.subscription_end = datetime.utcnow() + timedelta(days=30)

            elif price_id == PRICE_WEEKLY:
                user.subscription_status = 'weekly'
                user.subscription_end = datetime.utcnow() + timedelta(days=7)
            
            db.session.commit()

    return jsonify(success=True)

if __name__ == "__main__":
    app.run(debug=True)

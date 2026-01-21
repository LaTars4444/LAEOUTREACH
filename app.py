import os
import random
import time
import base64
import json
import requests
from email.mime.text import MIMEText
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import stripe

# Custom imports
from models import db, User, Lead, OutreachLog
from access_control import check_access

# Configuration
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
UPLOAD_FOLDER = 'static/uploads'

# ---------------------------------------------------------
# 1) EMAIL AUTOMATION MACHINE (Server-Side Delay)
# ---------------------------------------------------------

@app.route('/email_machine/send', methods=['POST'])
@login_required
def send_email_campaign():
    # 1. Strict Access Check
    if not check_access(current_user, 'email'):
        return jsonify({'error': 'Trial expired. Please upgrade.'}), 403

    data = request.json
    recipients = data.get('recipients', []) # List of emails
    subject = data.get('subject')
    body_template = data.get('body') # HTML content

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
        except Exception:
            return jsonify({'error': 'Google Token Expired. Re-login.'}), 401

    service = build('gmail', 'v1', credentials=creds)

    def generate_sending_stream():
        yield "Starting campaign...\n"
        
        for email in recipients:
            try:
                # Server-Side Random Delay (5-15 seconds)
                delay = random.randint(5, 15)
                time.sleep(delay)

                # Construct Message
                message = MIMEText(body_template, 'html')
                message['to'] = email
                message['subject'] = subject
                raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

                # Send
                service.users().messages().send(userId='me', body={'raw': raw}).execute()
                
                # Log Success
                log = OutreachLog(user_id=current_user.id, recipient_email=email, status='success')
                db.session.add(log)
                db.session.commit()
                
                yield f"Sent to {email} (Delayed {delay}s)\n"

            except Exception as e:
                # Log Failure
                log = OutreachLog(user_id=current_user.id, recipient_email=email, status='failed', error_msg=str(e))
                db.session.add(log)
                db.session.commit()
                yield f"Failed to send to {email}: {str(e)}\n"

        yield "Campaign Complete."

    # Use Stream Response to prevent timeout on long lists
    return Response(generate_sending_stream(), mimetype='text/plain')

# ---------------------------------------------------------
# 2) BUYER BUY BOX
# ---------------------------------------------------------

@app.route('/buy_box', methods=['GET', 'POST'])
@login_required
def buy_box():
    if request.method == 'POST':
        # Persist fields
        current_user.bb_property_type = request.form.get('property_type')
        current_user.bb_locations = request.form.get('locations')
        current_user.bb_min_price = request.form.get('min_price')
        current_user.bb_max_price = request.form.get('max_price')
        current_user.bb_condition = request.form.get('condition')
        current_user.bb_strategy = request.form.get('strategy')
        current_user.bb_funding = request.form.get('funding')
        current_user.bb_timeline = request.form.get('timeline')
        
        db.session.commit()
        flash('Buy Box criteria updated successfully!', 'success')
        return redirect(url_for('buy_box'))

    return render_template('buy_box.html', user=current_user)

def filter_inventory_by_buybox(inventory_list, user):
    """Helper to filter generic inventory based on user Buy Box"""
    if not user.bb_max_price: return inventory_list # No filter if empty
    
    filtered = []
    for item in inventory_list:
        # Logic: Check Price
        if item.price > user.bb_max_price: continue
        if user.bb_min_price and item.price < user.bb_min_price: continue
        
        # Logic: Check Location (Simple string match)
        if user.bb_locations and user.bb_locations.lower() not in item.address.lower(): continue
        
        filtered.append(item)
    return filtered

# ---------------------------------------------------------
# 3) SELLER PROPERTY INTAKE (Zillow-Style)
# ---------------------------------------------------------

@app.route('/sell', methods=['GET', 'POST'])
def sell_property():
    if request.method == 'POST':
        # 1. Validation
        required = ['address', 'property_type', 'desired_price', 'phone']
        for field in required:
            if not request.form.get(field):
                flash(f"Missing required field: {field}", "error")
                return redirect(url_for('sell_property'))

        # 2. TitanFinance Calculation (Simple Logic)
        desired_price = float(request.form.get('desired_price'))
        # Heuristic: Repairs = $25/sqft (estimated) or Base 10k + Age factor
        year_built = int(request.form.get('year_built', 1990))
        age = 2025 - year_built
        repair_est = 5000 + (age * 500) # Simple algorithm
        
        arv = desired_price * 1.3 # Optimistic ARV assumption
        mao = (arv * 0.7) - repair_est # 70% Rule

        # 3. Handle Image
        photo_url = None
        if 'photos' in request.files:
            file = request.files['photos']
            if file.filename != '':
                filename = secure_filename(file.filename)
                # Ensure folder exists
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                photo_url = f"/{UPLOAD_FOLDER}/{filename}"

        # 4. Save to DB
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
        
        flash("Property details submitted. We are analyzing your deal!", "success")
        return redirect(url_for('sell_property'))

    return render_template('sell.html')

# ---------------------------------------------------------
# 5) STRIPE WEBHOOK (STRICT)
# ---------------------------------------------------------

@app.route('/stripe_webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError as e:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        return 'Invalid signature', 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        client_reference_id = session.get('client_reference_id') # User ID passed during checkout
        
        user = User.query.get(client_reference_id)
        if user:
            # Check which product was bought
            line_items = stripe.checkout.Session.list_line_items(session['id'], limit=1)
            price_id = line_items['data'][0]['price']['id']

            # REPLACE WITH YOUR ACTUAL PRICE IDs
            PRICE_WEEKLY = "price_1Q..." 
            PRICE_LIFETIME = "price_1Q..."

            if price_id == PRICE_LIFETIME:
                user.subscription_status = 'lifetime'
                user.subscription_end = None # Forever
            elif price_id == PRICE_WEEKLY:
                user.subscription_status = 'weekly'
                # Add 7 days from now
                user.subscription_end = datetime.utcnow() + timedelta(days=7)
            
            db.session.commit()

    return jsonify(success=True)

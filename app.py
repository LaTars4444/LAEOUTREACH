import os
import json
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, login_manager
from models import User, Lead, OutreachLog
from utils import USA_STATES, check_access
from tasks import vicious_hunter, outreach_machine, log_activity, SYSTEM_LOGS
from sqlalchemy import inspect, text
from groq import Groq

def create_app():
    """ PRODUCTION APPLICATION FACTORY """
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'industrial_standard_v11')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/data/titan.db' if os.path.exists('/var/data') else 'sqlite:///titan.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- INDUSTRIAL SELF-HEALING MIGRATION ENGINE ---
    # Fixes the 500 error: no such column outreach_logs.address
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        
        # Repair Outreach Logs Table
        log_cols = [c['name'] for c in inspector.get_columns('outreach_logs')]
        if 'address' not in log_cols:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE outreach_logs ADD COLUMN address TEXT'))
                conn.commit()
                
        # Repair User Table
        user_cols = [c['name'] for c in inspector.get_columns('users')]
        if 'email_template' not in user_cols:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE users ADD COLUMN email_template TEXT'))
                conn.commit()
        
    return app

app = create_app()

# GLOBAL PRODUCTION API HANDLERS
SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")
try:
    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except:
    groq_client = None

@app.route('/logs')
@login_required
def get_logs(): return jsonify(SYSTEM_LOGS)

@app.route('/dashboard')
@login_required
def dashboard():
    leads = Lead.query.filter_by(submitter_id=current_user.id).order_by(Lead.created_at.desc()).all()
    history = OutreachLog.query.filter_by(user_id=current_user.id).order_by(OutreachLog.sent_at.desc()).limit(20).all()
    stats = {'total': len(leads), 'hot': len([l for l in leads if l.status == 'Hot']), 'emails': sum([l.emailed_count or 0 for l in leads])}
    return render_template('dashboard.html', user=current_user, leads=leads, stats=stats, history=history, gmail_connected=bool(current_user.smtp_email))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(email=request.form['email']).first()
        if u and check_password_hash(u.password, request.form['password']):
            login_user(u); return redirect(url_for('dashboard'))
        flash('Invalid Credentials.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not User.query.filter_by(email=request.form['email']).first():
            hashed = generate_password_hash(request.form['password'], method='scrypt')
            u = User(email=request.form['email'], password=hashed); db.session.add(u); db.session.commit(); login_user(u); return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/leads/hunt', methods=['POST'])
@login_required
def hunt_leads():
    threading.Thread(target=vicious_hunter, args=(app, current_user.id, request.form.get('city'), request.form.get('state'), SEARCH_API_KEY, SEARCH_CX)).start()
    return jsonify({'message': "🚀 Industrial scan mission launched."})

@app.route('/email/campaign', methods=['POST'])
@login_required
def email_campaign():
    threading.Thread(target=outreach_machine, args=(app, current_user.id, request.form.get('subject'), request.form.get('body'), groq_client)).start()
    return jsonify({'message': "🚀 Mass outreach launched."})

@app.route('/email/template/save', methods=['POST'])
@login_required
def save_template():
    current_user.email_template = request.form.get('template'); db.session.commit()
    flash('Universal Script Updated!', 'success'); return redirect(url_for('dashboard'))

@app.route('/settings/save', methods=['POST'])
@login_required
def save_settings():
    current_user.smtp_email = request.form.get('smtp_email'); current_user.smtp_password = request.form.get('smtp_password')
    db.session.commit(); return redirect(url_for('dashboard'))

@app.route('/leads/add', methods=['POST'])
@login_required
def add_manual_lead():
    new_lead = Lead(submitter_id=current_user.id, address=request.form.get('address'), name=request.form.get('name'), phone=request.form.get('phone'), email=request.form.get('email'), source="Manual", status="New", link="#")
    db.session.add(new_lead); db.session.commit(); return redirect(url_for('dashboard'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/sell', methods=['GET', 'POST'])
def sell_property():
    if request.method == 'POST': flash('Evaluation Initiated.', 'success'); return redirect(url_for('sell_property'))
    return render_template('sell.html')

@app.route('/')
def index(): return redirect(url_for('login'))

# --- BOOTSTRAPPER ---
# Ensures templates are written to the Render disk before serving requests.
@app.context_processor
def inject_us_data(): return dict(us_data_json=json.dumps(USA_STATES))

if __name__ == "__main__":
    app.run(debug=True, port=5000)

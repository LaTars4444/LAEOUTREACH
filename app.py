import os
import json
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, login_manager
from models import User, Lead, OutreachLog, Video
from utils import USA_STATES, check_access
from tasks import vicious_hunter, outreach_machine, log_activity, SYSTEM_LOGS
from sqlalchemy import inspect, text
from groq import Groq

def create_app():
    """ PRODUCTION INDUSTRIAL FACTORY """
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'industrial_standard_auth_protocol_v13')
    
    # Render Persistent Disk Support
    if os.path.exists('/var/data'):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/data/titan.db'
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///titan.db'
        
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- PRODUCTION SELF-HEALING SCHEMA ENGINE ---
    # Fixes the 500 OperationalErrors by surgically injecting columns.
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        
        # Repair Outreach Logs Table (Sent History Visibility)
        h_cols = [c['name'] for c in inspector.get_columns('outreach_logs')]
        if 'address' not in h_cols:
            with db.engine.connect() as cn:
                cn.execute(text('ALTER TABLE outreach_logs ADD COLUMN address TEXT'))
                cn.commit()
        if 'message' not in h_cols:
            with db.engine.connect() as cn:
                cn.execute(text('ALTER TABLE outreach_logs ADD COLUMN message TEXT'))
                cn.commit()
                
        # Repair User Table (Universal Script Templates)
        u_cols = [c['name'] for c in inspector.get_columns('users')]
        if 'email_template' not in u_cols:
            with db.engine.connect() as cn:
                cn.execute(text('ALTER TABLE users ADD COLUMN email_template TEXT'))
                cn.commit()
        
    return app

app = create_app()

# GLOBAL PRODUCTION API HANDLERS
SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")
try:
    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except:
    groq_client = None

# --- INDUSTRIAL ROUTES ---

@app.route('/logs')
@login_required
def get_logs(): return jsonify(SYSTEM_LOGS)

@app.route('/dashboard')
@login_required
def dashboard():
    my_leads = Lead.query.filter_by(submitter_id=current_user.id).order_by(Lead.created_at.desc()).all()
    history = OutreachLog.query.filter_by(user_id=current_user.id).order_by(OutreachLog.sent_at.desc()).limit(30).all()
    stats = {'total': len(my_leads), 'hot': len([l for l in my_leads if l.status == 'Hot']), 'emails': sum([l.emailed_count or 0 for l in my_leads])}
    return render_template('dashboard.html', user=current_user, leads=my_leads, stats=stats, history=history, gmail_connected=bool(current_user.smtp_email))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = User.query.filter_by(email=request.form['email']).first()
        if identifier and check_password_hash(identifier.password, request.form['password']):
            login_user(identifier); return redirect(url_for('dashboard'))
        flash('Industrial access keys rejected.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not User.query.filter_by(email=request.form['email']).first():
            hashed_key = generate_password_hash(request.form['password'], method='scrypt')
            u = User(email=request.form['email'], password=hashed_key); db.session.add(u); db.session.commit(); login_user(u)
            return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/leads/hunt', methods=['POST'])
@login_required
def hunt_leads():
    threading.Thread(target=vicious_hunter, args=(app, current_user.id, request.form.get('city'), request.form.get('state'), SEARCH_API_KEY, SEARCH_CX)).start()
    return jsonify({'message': "🚀 Industrial scan mission started."})

@app.route('/email/campaign', methods=['POST'])
@login_required
def email_campaign():
    if not check_access(current_user, 'email'): return jsonify({'error': 'Subscription Required.'}), 403
    threading.Thread(target=outreach_machine, args=(app, current_user.id, request.form.get('subject'), request.form.get('body'), groq_client)).start()
    return jsonify({'message': "🚀 Bulk outreach launched."})

@app.route('/email/template/save', methods=['POST'])
@login_required
def save_template():
    current_user.email_template = request.form.get('template'); db.session.commit()
    flash('Industrial Script Template Saved!', 'success'); return redirect(url_for('dashboard'))

@app.route('/settings/save', methods=['POST'])
@login_required
def save_settings():
    current_user.smtp_email = request.form.get('smtp_email'); current_user.smtp_password = request.form.get('smtp_password')
    db.session.commit(); return redirect(url_for('dashboard'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/sell', methods=['GET', 'POST'])
def sell_property():
    if request.method == 'POST': flash('Evaluation sequence started.', 'success'); return redirect(url_for('sell_property'))
    return render_template('sell.html')

@app.route('/')
def index(): return redirect(url_for('login'))

# --- INDUSTRIAL BOOTSTRAPPER ---
template_path_industrial = os.path.join(os.getcwd(), 'templates')
if not os.path.exists(template_path_industrial): os.makedirs(template_path_industrial)

@app.context_processor
def industrial_context_processor():
    return dict(us_data_json=json.dumps(USA_STATES))

if __name__ == "__main__":
    app.run(debug=True, port=5000)

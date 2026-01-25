import os
import json
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, login_manager
from models import User, Lead, OutreachLog, Video
from utils import USA_STATES, check_access, industrial_encrypt
from tasks import task_vicious_hunter, task_outreach_machine, log_activity, SYSTEM_LOGS
from bootstrapper import run_production_repair, generate_production_ui
from config import EnterpriseConfig
from groq import Groq

def create_app():
    """ ENTERPRISE APPLICATION FACTORY """
    app = Flask(__name__)
    app.config.from_object(EnterpriseConfig)
    
    # Initialize Core Industrial Extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # ------------------------------------------------------------------------------------------------------------------
    # ! CRITICAL FIX: USER LOADER REGISTRATION (FIXES 500 ERROR)                                                       !
    # ------------------------------------------------------------------------------------------------------------------
    @login_manager.user_loader
    def load_user(user_id):
        """ Production-grade user retrieval logic. """
        return User.query.get(int(user_id))
    # ------------------------------------------------------------------------------------------------------------------

    # FORCED GLOBAL SELF-HEALING REPAIR Sequence
    # This audits the database schema and injects missing columns automatically.
    run_production_repair(app)
        
    return app

# Initialize Global App Object
app = create_app()

# GLOBAL PRODUCTION API HANDLERS (Provisioned from Config)
SEARCH_API_KEY = EnterpriseConfig.GOOGLE_SEARCH_API_KEY
SEARCH_CX = EnterpriseConfig.GOOGLE_SEARCH_CX
MASTER_KEY = EnterpriseConfig.MASTER_ENCRYPTION_KEY

# GROQ AI Client Initialization
try:
    if EnterpriseConfig.GROQ_API_KEY:
        groq_client = Groq(api_key=EnterpriseConfig.GROQ_API_KEY)
    else:
        groq_client = None
except:
    groq_client = None

# ----------------------------------------------------------------------------------------------------------------------
# 5. INDUSTRIAL PRODUCTION ROUTES
# ----------------------------------------------------------------------------------------------------------------------

@app.route('/logs')
@login_required
def get_logs():
    """ Industrial stream for real-time terminal logging. """
    return jsonify(SYSTEM_LOGS)

@app.route('/dashboard')
@login_required
def dashboard():
    """ Enterprise Dashboard Gateway. """
    leads = Lead.query.filter_by(submitter_id=current_user.id).order_by(Lead.created_at.desc()).all()
    # history visibility logic for history pane
    history = OutreachLog.query.filter_by(user_id=current_user.id).order_by(OutreachLog.sent_at.desc()).limit(30).all()
    
    stats = {
        'total': len(leads), 
        'hot': len([l for l in leads if l.status == 'Hot']), 
        'emails': sum([l.emailed_count or 0 for l in leads])
    }
    return render_template('dashboard.html', 
        user=current_user, leads=leads, stats=stats, 
        history=history, gmail_connected=bool(current_user.smtp_email)
    )

@app.route('/ai/chat', methods=['POST'])
@login_required
def ai_chat():
    """ Enterprise AI Intelligence Hub Gateway. """
    if not groq_client:
        return jsonify({'response': 'AI Engine offline.'})
    
    user_prompt = request.json.get('message')
    try:
        completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": user_prompt}], 
            model="llama-3.3-70b-versatile"
        )
        return jsonify({'response': completion.choices[0].message.content})
    except Exception as e:
        return jsonify({'response': "AI Fault: {0}".format(str(e))})

@app.route('/login', methods=['GET', 'POST'])
def login():
    """ Industrial Authentication gateway. """
    if request.method == 'POST':
        identifier = User.query.filter_by(email=request.form['email']).first()
        if identifier and check_password_hash(identifier.password, request.form['password']):
            login_user(identifier)
            return redirect(url_for('dashboard'))
        flash('Industrial access keys rejected.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """ Industrial Registration Gateway with industrial encryption standard. """
    if request.method == 'POST':
        if not User.query.filter_by(email=request.form['email']).first():
            hashed_key = generate_password_hash(request.form['password'], method='scrypt')
            provision_user = User(email=request.form['email'], password=hashed_key)
            db.session.add(provision_user); db.session.commit()
            login_user(provision_user)
            return redirect(url_for('dashboard'))
        flash('Email identifier already provisioned.', 'error')
    return render_template('register.html')

@app.route('/leads/hunt', methods=['POST'])
@login_required
def hunt_leads():
    """ Mission: Lead extraction background sequence. """
    threading.Thread(target=task_vicious_hunter, args=(app, current_user.id, request.form.get('city'), request.form.get('state'), SEARCH_API_KEY, SEARCH_CX)).start()
    return jsonify({'message': "🚀 Industrial scan mission started. Monitor terminal."})

@app.route('/email/campaign', methods=['POST'])
@login_required
def email_campaign():
    """ Mission: Mass AI outreach background sequence. """
    if not check_access(current_user, 'email'):
        return jsonify({'error': 'Subscription Authorization Required.'}), 403
    threading.Thread(target=task_outreach_machine, args=(app, current_user.id, request.form.get('subject'), request.form.get('body'), groq_client, MASTER_KEY)).start()
    return jsonify({'message': "🚀 Bulk outreach machine launched with human delays."})

@app.route('/email/template/save', methods=['POST'])
@login_required
def save_template():
    """ Saves the Universal Script Template to persistent storage. """
    current_user.email_template = request.form.get('template')
    db.session.commit()
    flash('Universal Script Template Updated!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/settings/save', methods=['POST'])
@login_required
def save_settings():
    """ Production credentials gate with industrial encryption logic. """
    current_user.smtp_email = request.form.get('smtp_email')
    raw_pass = request.form.get('smtp_password')
    # ENCRYPT APP PASSWORD BEFORE DB COMMIT
    current_user.smtp_password_encrypted = industrial_encrypt(raw_pass, MASTER_KEY)
    db.session.commit()
    log_activity("⚙️ SETTINGS: Production keys encrypted and saved.")
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    """ Industrial session termination sequence. """
    logout_user()
    return redirect(url_for('login'))

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    """ High-visibility Seller Portal handler. """
    if request.method == 'POST': 
        flash('Lead Assessment Synchronized.', 'success')
        return redirect(url_for('sell'))
    return render_template('sell.html')

@app.route('/')
def index(): 
    return redirect(url_for('login'))

# ----------------------------------------------------------------------------------------------------------------------
# 6. GLOBAL PRODUCTION BOOTSTRAPPER
# ----------------------------------------------------------------------------------------------------------------------

# Forced Writing of Templates to Disk for Render Compatibility
UI_REPOSITORY = {
    'dashboard.html': """ (INSERT FULL DASHBOARD CODE FROM BELOW) """,
    'login.html': """ (INSERT FULL LOGIN CODE FROM BELOW) """
}
generate_production_ui(UI_REPOSITORY)

@app.context_processor
def industrial_context_processor():
    """ Shares industrial state data with all frontend templates. """
    return dict(us_data_json=json.dumps(USA_STATES))

if __name__ == "__main__":
    # Standard industrial port 5000 utilized for high-volume synchronization.
    app.run(debug=True, port=5000)


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
    """ INDUSTRIAL PRODUCTION APPLICATION FACTORY """
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'titan_enterprise_standard_auth_protocol')
    
    # Render Persistent Disk support
    if os.path.exists('/var/data'):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/data/titan.db'
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///titan.db'
        
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize Core Industrial Extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # REGISTER USER LOADER (FIXES 500 EXCEPTION)
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- PRODUCTION SELF-HEALING MIGRATION ENGINE ---
    # Fixes the 500 error: no such column outreach_logs.address
    # Injects missing columns into existing Render DB files automatically.
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        
        # 1. Repair Outreach Logs (Visibility Pane Support)
        log_cols = [c['name'] for c in inspector.get_columns('outreach_logs')]
        if 'address' not in log_cols:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE outreach_logs ADD COLUMN address TEXT'))
                conn.commit()
                
        # 2. Repair User Table (Universal Template Support)
        user_cols = [c['name'] for c in inspector.get_columns('users')]
        if 'email_template' not in user_cols:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE users ADD COLUMN email_template TEXT'))
                conn.commit()
        
    return app

# Initialize Global App Object
app = create_app()

# GLOBAL PRODUCTION API HANDLERS
SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")
try:
    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except:
    groq_client = None

# ---------------------------------------------------------
# INDUSTRIAL GATEWAY ROUTES
# ---------------------------------------------------------

@app.route('/logs')
@login_required
def get_logs(): return jsonify(SYSTEM_LOGS)

@app.route('/dashboard')
@login_required
def dashboard():
    """ Industrial Dashboard Gateway. """
    active_leads = Lead.query.filter_by(submitter_id=current_user.id).order_by(Lead.created_at.desc()).all()
    # Visibility Pane History Data
    outreach_history = OutreachLog.query.filter_by(user_id=current_user.id).order_by(OutreachLog.sent_at.desc()).limit(30).all()
    stats = {
        'total': len(active_leads), 
        'hot': len([l for l in active_leads if l.status == 'Hot']), 
        'emails': sum([l.emailed_count or 0 for l in active_leads])
    }
    return render_template('dashboard.html', 
        user=current_user, 
        leads=active_leads, 
        stats=stats, 
        history=outreach_history, 
        gmail_connected=bool(current_user.smtp_email)
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    """ Authentication Gateway with Industrial Security Checks. """
    if request.method == 'POST':
        identifier = User.query.filter_by(email=request.form['email']).first()
        if identifier and check_password_hash(identifier.password, request.form['password']):
            login_user(identifier)
            return redirect(url_for('dashboard'))
        flash('Industrial access keys rejected.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """ Industrial Registration Gateway with Scrypt Hashing. """
    if request.method == 'POST':
        if not User.query.filter_by(email=request.form['email']).first():
            hashed_key = generate_password_hash(request.form['password'], method='scrypt')
            provision_user = User(email=request.form['email'], password=hashed_key)
            db.session.add(provision_user); db.session.commit()
            login_user(provision_user)
            return redirect(url_for('dashboard'))
        flash('Identifier already exists in production database.', 'error')
    return render_template('register.html')

@app.route('/leads/hunt', methods=['POST'])
@login_required
def hunt_leads():
    """ Mission: Lead extraction launch sequence. """
    threading.Thread(target=vicious_hunter, args=(app, current_user.id, request.form.get('city'), request.form.get('state'), SEARCH_API_KEY, SEARCH_CX)).start()
    return jsonify({'message': "🚀 Industrial scan mission launched. Check Terminal."})

@app.route('/email/campaign', methods=['POST'])
@login_required
def email_campaign():
    """ Mission: Mass AI outreach launch sequence. """
    if not check_access(current_user, 'email'):
        return jsonify({'error': 'Subscription Authorization Required.'}), 403
    threading.Thread(target=outreach_machine, args=(app, current_user.id, request.form.get('subject'), request.form.get('body'), groq_client)).start()
    return jsonify({'message': "🚀 Bulk outreach machine launched with stealth protocol."})

@app.route('/email/template/save', methods=['POST'])
@login_required
def save_template():
    """ Saves the Universal Script Template to persistent storage. """
    current_user.email_template = request.form.get('template')
    db.session.commit()
    flash('Universal Script Template Updated Successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/settings/save', methods=['POST'])
@login_required
def save_settings():
    """ Persistent configuration update gate. """
    current_user.smtp_email = request.form.get('smtp_email')
    current_user.smtp_password = request.form.get('smtp_password')
    db.session.commit()
    log_activity("⚙️ SETTINGS: Production credentials updated.")
    return redirect(url_for('dashboard'))

@app.route('/leads/add', methods=['POST'])
@login_required
def add_manual_lead():
    """ Manual lead injection gateway. """
    injection = Lead(
        submitter_id=current_user.id, 
        address=request.form.get('address'), 
        name=request.form.get('name'), 
        phone=request.form.get('phone'), 
        email=request.form.get('email'), 
        source="Manual Injection", 
        status="New", 
        link="#"
    )
    db.session.add(injection); db.session.commit()
    log_activity("➕ LEAD: Manual entry added for {0}.".format(injection.address))
    return redirect(url_for('dashboard'))

@app.route('/leads/update/<int:id>', methods=['POST'])
@login_required
def update_lead_status(id):
    """ Leads lifecycle state manager. """
    active_target = Lead.query.get_or_404(id)
    active_target.status = request.json.get('status')
    db.session.commit()
    return jsonify({'message': 'Lifecycle State Synchronized.'})

@app.route('/logout')
def logout():
    """ Industrial session termination sequence. """
    logout_user()
    return redirect(url_for('login'))

@app.route('/sell', methods=['GET', 'POST'])
def sell_property():
    """ High-visibility Seller Lead Generation Gate. """
    if request.method == 'POST': 
        flash('Evaluation Sequence Initiated. AI Valuations in progress.', 'success')
        return redirect(url_for('sell_property'))
    return render_template('sell.html')

@app.route('/')
def index(): return redirect(url_for('login'))

# --- GLOBAL INDUSTRIAL BOOTSTRAPPER ---
# Logic placed at global scope to force Disk Write during Gunicorn import.
# Prevents TemplateNotFound errors on Render.
# ---------------------------------------------------------
template_disk_path = os.path.join(os.getcwd(), 'templates')
if not os.path.exists(template_disk_path): os.makedirs(template_disk_path)

# HTML TEMPLATE REPOSITORY
# Preserves all industrial CSS and UI components.
INDUSTRIAL_UI = {
 'login.html': """{% extends "base.html" %} {% block content %} <div class="row justify-content-center pt-5"><div class="col-md-10"><div class="card shadow-lg border-0 mb-5 bg-warning text-dark text-center p-5"><h1 class="fw-bold display-3">🏠 SELL YOUR PROPERTY NOW</h1><p class="lead fw-bold fs-4 mb-4 text-uppercase">Professional cash investors are waiting for your address. Skip the agents and get paid today.</p><a href="/sell" class="btn btn-dark btn-xl fw-bold px-5 py-4 shadow-lg border-0 rounded-pill"><i class="fas fa-money-bill-wave me-2"></i> GET AN INSTANT CASH OFFER</a></div></div><div class="col-md-5"><div class="card p-5 shadow-lg border-0"><h3 class="text-center fw-bold mb-4 text-primary">Industrial Gateway</h3><form method="POST"><div class="mb-3"><label class="form-label fw-bold">Identifier (Email)</label><input name="email" class="form-control form-control-lg" placeholder="admin@titanintel.ai" required></div><div class="mb-4"><label class="form-label fw-bold">Access Key (Password)</label><input type="password" name="password" class="form-control form-control-lg" placeholder="Enter Access Code" required></div><button class="btn btn-primary w-100 fw-bold py-3 shadow">AUTHORIZE ACCESS</button></form><div class="text-center mt-4"><a href="/register" class="small text-muted">Provision New Account</a></div></div></div></div>{% endblock %}""",
 'dashboard.html': """{% extends "base.html" %} {% block content %} <div class="row g-4"><div class="col-12"><div class="card shadow-lg bg-dark text-white"><div class="card-header border-secondary d-flex justify-content-between"><span><i class="fas fa-terminal me-2"></i> SYSTEM LOG ENGINE</span><span class="badge bg-success">STREAMS ACTIVE</span></div><div class="card-body p-0"><div id="system-terminal" class="terminal">Initializing connection...</div></div></div></div><div class="col-12"><div class="card shadow-sm"><div class="card-body d-flex justify-content-around text-center py-4"><div><h3>{{ stats.total }}</h3><small class="text-muted fw-bold">TOTAL LEADS</small></div><div class="text-success"><h3>{{ stats.hot }}</h3><small class="text-muted fw-bold">HOT LEADS</small></div><div class="text-primary"><h3>{{ stats.emails }}</h3><small class="text-muted fw-bold">EMAILS SENT</small></div><div class="align-self-center d-flex gap-2"><button class="btn btn-sm btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#settingsModal">Settings</button><button class="btn btn-sm btn-success" data-bs-toggle="modal" data-bs-target="#addLeadModal">Manual Add</button></div></div></div></div><div class="col-12"><ul class="nav nav-tabs mb-4" id="titanTab" role="tablist"><li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#leads">🏠 My Leads</button></li><li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#hunter">🕵️ Lead Hunter</button></li><li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#email">📧 Outreach Machine</button></li><li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#history">📜 Sent History</button></li></ul><div class="tab-content"><div class="tab-pane fade show active" id="leads"><div class="card shadow-sm"><div class="card-body p-0"><div class="table-responsive"><table class="table table-hover align-middle mb-0"><thead><tr><th>Status</th><th>Address</th><th>Owner</th><th>Link</th></tr></thead><tbody>{% for lead in leads %}<tr><td><select class="form-select form-select-sm" onchange="updateStatus({{ lead.id }}, this.value)"><option {% if lead.status == 'New' %}selected{% endif %}>New</option><option {% if lead.status == 'Hot' %}selected{% endif %}>Hot</option></select></td><td class="fw-bold">{{ lead.address }}</td><td>{{ lead.name }}</td><td><a href="{{ lead.link }}" target="_blank" class="btn btn-sm btn-outline-primary">Link</a></td></tr>{% endfor %}</tbody></table></div></div></div></div><div class="tab-pane fade" id="hunter"><div class="card bg-dark text-white p-5 text-center shadow-lg"><h2 class="fw-bold mb-3">🕵️ Scraper Mission Engine</h2><p>High-volume extraction across your 1,000+ Site cluster.</p><div class="row justify-content-center mt-4 g-3"><div class="col-md-3"><select id="huntState" class="form-select" onchange="loadCities()"><option value="">State</option></select></div><div class="col-md-3"><select id="huntCity" class="form-select"><option value="">City</option></select></div><div class="col-md-3"><button onclick="runHunt()" class="btn btn-warning w-100 fw-bold">LAUNCH SCAN</button></div></div></div></div><div class="tab-pane fade" id="email"><div class="card shadow-sm border-primary"><div class="card-header bg-primary text-white fw-bold d-flex justify-content-between"><span>📧 Universal Outreach Config</span><small>Use [[ADDRESS]] and [[NAME]]</small></div><div class="card-body p-4"><form action="/email/template/save" method="POST" class="mb-4"><textarea name="template" class="form-control mb-2" rows="4">{{ user.email_template }}</textarea><button class="btn btn-sm btn-primary">Save Global Template</button></form><hr>{% if not gmail_connected %}<div class="alert alert-danger">Connect Gmail App Password in Settings!</div>{% endif %}<div class="mb-3"><label class="form-label">Subject Line</label><input id="emailSubject" class="form-control" value="Regarding your property at [[ADDRESS]]"></div><button onclick="sendBlast()" class="btn btn-dark w-100 fw-bold shadow" {% if not gmail_connected %}disabled{% endif %}>🚀 Launch Mission</button></div></div></div><div class="tab-pane fade" id="history"><div class="card shadow-sm border-0"><div class="card-body"><h5 class="fw-bold mb-3">Outreach Message History</h5><div class="list-group">{% for item in history %}<div class="list-group-item"><h6 class="mb-1 fw-bold">{{ item.address }}</h6><p class="mb-1 small">{{ item.message }}...</p><small class="text-primary">Sent to: {{ item.recipient_email }}</small></div>{% endfor %}</div></div></div></div></div></div></div><div class="modal fade" id="settingsModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><form action="/settings/save" method="POST"><div class="modal-body"><h6>Outreach Config</h6><input name="smtp_email" class="form-control mb-2" value="{{ user.smtp_email or '' }}" placeholder="Gmail Address"><input type="password" name="smtp_password" class="form-control mb-2" value="{{ user.smtp_password or '' }}" placeholder="16-Character Key"></div><div class="modal-footer"><button class="btn btn-primary">Save</button></div></form></div></div></div><div class="modal fade" id="addLeadModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><form action="/leads/add" method="POST"><div class="modal-body"><h6>Manual Entry</h6><input name="address" class="form-control mb-2" placeholder="Address" required><input name="name" class="form-control mb-2" placeholder="Owner Name"><input name="phone" class="form-control mb-2" placeholder="Phone"><input name="email" class="form-control mb-2" placeholder="Email"></div><div class="modal-footer"><button type="submit" class="btn btn-success">Save</button></div></form></div></div></div><script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script><script>const usData = {{ us_data_json|safe }}; window.onload = function() { const s = document.getElementById("huntState"); for (let st in usData) { let o = document.createElement("option"); o.value = st; o.innerText = st; s.appendChild(o); } setInterval(updateTerminal, 2000); }; function loadCities() { const st = document.getElementById("huntState").value; const c = document.getElementById("huntCity"); c.innerHTML = '<option value="">Select City</option>'; if(st) usData[st].forEach(ct => { let o = document.createElement("option"); o.value = ct; o.innerText = ct; c.appendChild(o); }); } async function updateTerminal() { const t = document.getElementById('system-terminal'); try { const r = await fetch('/logs'); const l = await r.json(); t.innerHTML = l.join('<br>'); t.scrollTop = t.scrollHeight; } catch(e) {} } async function runHunt() { const city = document.getElementById('huntCity').value; const state = document.getElementById('huntState').value; if(!city || !state) return alert("Select location."); const r = await fetch('/leads/hunt', {method:'POST', body:new URLSearchParams({city, state})}); const d = await r.json(); alert(d.message); } async function sendBlast() { const f = new FormData(); f.append('subject', document.getElementById('emailSubject').value); f.append('body', ''); const r = await fetch('/email/campaign', {method:'POST', body:f}); const d = await r.json(); alert(d.message); } async function updateStatus(id, s) { await fetch('/leads/update/'+id, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status:s})}); }</script>{% endblock %}"""
}

# FORCED DISK BOOTSTRAPPER
for name, content in INDUSTRIAL_UI.items():
    with open(os.path.join(template_disk_path, name), 'w') as f: f.write(content.strip())

@app.context_processor
def industrial_context_processor():
    return dict(us_data_json=json.dumps(USA_STATES))

if __name__ == "__main__":
    # Standard industrial port 5000 synchronization.
    app.run(debug=True, port=5000)

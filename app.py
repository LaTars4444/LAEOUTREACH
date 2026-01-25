import os
import json
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, login_manager
from models import User, Lead, OutreachLog, Video
from utils import USA_STATES, check_access
from tasks import industrial_hunter, industrial_outreach, log_activity, SYSTEM_LOGS
from groq import Groq
from bootstrapper import run_industrial_bootstrapper, write_industrial_templates
from config import EnterpriseConfig

def create_app():
    """ ENTERPRISE APPLICATION FACTORY """
    app = Flask(__name__)
    app.config.from_object(EnterpriseConfig)
    
    db.init_app(app)
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Forced Global Repair Sequence
    run_industrial_bootstrapper(app)
        
    return app

app = create_app()

@app.route('/logs')
@login_required
def get_logs(): return jsonify(SYSTEM_LOGS)

@app.route('/dashboard')
@login_required
def dashboard():
    leads = Lead.query.filter_by(submitter_id=current_user.id).order_by(Lead.created_at.desc()).all()
    history = OutreachLog.query.filter_by(user_id=current_user.id).order_by(OutreachLog.sent_at.desc()).limit(30).all()
    stats = {'total': len(leads), 'hot': len([l for l in leads if l.status == 'Hot']), 'emails': sum([l.emailed_count or 0 for l in leads])}
    return render_template('dashboard.html', user=current_user, leads=leads, stats=stats, history=history, gmail_connected=bool(current_user.smtp_email))

@app.route('/ai/chat', methods=['POST'])
@login_required
def ai_chat():
    p = request.json.get('message')
    if EnterpriseConfig.GROQ_API_KEY:
        groq = Groq(api_key=EnterpriseConfig.GROQ_API_KEY)
        c = groq.chat.completions.create(messages=[{"role": "user", "content": p}], model="llama-3.3-70b-versatile")
        return jsonify({'response': c.choices[0].message.content})
    return jsonify({'response': 'Engine Offline.'})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(email=request.form['email']).first()
        if u and check_password_hash(u.password, request.form['password']):
            login_user(u); return redirect(url_for('dashboard'))
        flash('Industrial security check failed.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not User.query.filter_by(email=request.form['email']).first():
            h = generate_password_hash(request.form['password'], method='scrypt')
            u = User(email=request.form['email'], password=h); db.session.add(u); db.session.commit(); login_user(u)
            return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/leads/hunt', methods=['POST'])
@login_required
def hunt_leads():
    threading.Thread(target=industrial_hunter, args=(app, current_user.id, request.form.get('city'), request.form.get('state'), EnterpriseConfig.GOOGLE_SEARCH_API_KEY, EnterpriseConfig.GOOGLE_SEARCH_CX)).start()
    return jsonify({'message': "🚀 industrial Mission started."})

@app.route('/email/campaign', methods=['POST'])
@login_required
def email_campaign():
    if not check_access(current_user, 'email'): return jsonify({'error': 'Upgrade Required.'}), 403
    groq = Groq(api_key=EnterpriseConfig.GROQ_API_KEY) if EnterpriseConfig.GROQ_API_KEY else None
    threading.Thread(target=industrial_outreach, args=(app, current_user.id, request.form.get('subject'), request.form.get('body'), groq)).start()
    return jsonify({'message': "🚀 Bulk outreach machine launched."})

@app.route('/')
def index(): return redirect(url_for('login'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if request.method == 'POST': flash('Submission Received.', 'success'); return redirect(url_for('sell'))
    return render_template('sell.html')

@app.route('/buy_box', methods=['GET', 'POST'])
@login_required
def buy_box():
    if request.method == 'POST':
        current_user.bb_property_type = request.form.get('property_type'); db.session.commit(); flash('Buy Box Saved!', 'success')
    return render_template('buybox.html', user=current_user)

# ---------------------------------------------------------
# INDUSTRIAL UI REPOSITORY
# ---------------------------------------------------------
INDUSTRIAL_UI = {
 'login.html': """{% extends "base.html" %} {% block content %} <div class="row justify-content-center pt-5"><div class="col-md-10"><div class="card shadow-lg border-0 mb-5 bg-warning text-dark text-center p-5"><h1 class="fw-bold display-3">🏠 SELL YOUR PROPERTY NOW</h1><p class="lead fw-bold fs-4 mb-4 text-uppercase">Professional cash investors are waiting for your address. Skip the agents and get paid cash today.</p><a href="/sell" class="btn btn-dark btn-xl fw-bold px-5 py-4 shadow-lg border-0 rounded-pill"><i class="fas fa-money-bill-wave me-2"></i> GET AN INSTANT CASH OFFER</a></div></div><div class="col-md-10 mb-5"><div class="card shadow-lg border-0 bg-primary text-white text-center p-4"><h2 class="fw-bold text-uppercase">Industrial Buy Box Portal</h2><p>Configure your investment architectural preferences before lead access.</p><a href="/buy_box" class="btn btn-light fw-bold px-4 py-2 mt-2 shadow">CONFIGURE PARAMETERS</a></div></div><div class="col-md-5"><div class="card p-5 shadow-lg border-0"><h3 class="text-center fw-bold mb-4 text-primary"><i class="fas fa-lock me-2"></i> Industrial Gateway</h3><form method="POST"><div class="mb-3"><label class="form-label fw-bold">Identifier (Email)</label><input name="email" class="form-control form-control-lg bg-light" placeholder="admin@titanintel.ai" required></div><div class="mb-4"><label class="form-label fw-bold">Production Access Key</label><input type="password" name="password" class="form-control form-control-lg bg-light" placeholder="Enter Code" required></div><button class="btn btn-primary w-100 fw-bold py-3 shadow border-0">AUTHORIZE ACCESS</button></form><div class="text-center mt-4"><a href="/register" class="small fw-bold text-muted">Provision New Account</a></div></div></div></div>{% endblock %}""",
 'dashboard.html': """{% extends "base.html" %} {% block content %} <div class="row g-4"><div class="col-12"><div class="card shadow-lg bg-dark text-white"><div class="card-header border-secondary d-flex justify-content-between align-items-center"><span><i class="fas fa-terminal me-2 text-warning"></i> SYSTEM LOG ENGINE</span><span class="badge bg-success">STREAMS ACTIVE</span></div><div class="card-body p-0"><div id="system-terminal" class="terminal">Initializing extraction synchronization...</div></div></div></div><div class="col-12"><div class="card shadow-sm"><div class="card-body d-flex justify-content-around text-center py-4"><div><h3>{{ stats.total }}</h3><small class="text-muted fw-bold text-uppercase">Leads indexed</small></div><div class="text-success"><h3>{{ stats.hot }}</h3><small class="text-muted fw-bold text-uppercase">Hot Deals</small></div><div class="text-primary"><h3>{{ stats.emails }}</h3><small class="text-muted fw-bold text-uppercase">Outreach mission</small></div><div class="align-self-center d-flex gap-2"><button class="btn btn-sm btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#settingsModal">Settings & App Password</button><button class="btn btn-sm btn-success" data-bs-toggle="modal" data-bs-target="#addLeadModal">Manual Add</button></div></div></div></div><div class="col-12"><ul class="nav nav-tabs mb-4 border-0" id="titanTab" role="tablist"><li class="nav-item"><button class="nav-link active text-uppercase" data-bs-toggle="tab" data-bs-target="#leads">🏠 My Leads</button></li><li class="nav-item"><button class="nav-link text-uppercase" data-bs-toggle="tab" data-bs-target="#hunter">🕵️ Scraper Engine</button></li><li class="nav-item"><button class="nav-link text-uppercase" data-bs-toggle="tab" data-bs-target="#email">📧 Universal Outreach</button></li><li class="nav-item"><button class="nav-link text-uppercase" data-bs-toggle="tab" data-bs-target="#history">📜 Sent History</button></li><li class="nav-item"><button class="nav-link text-uppercase" data-bs-toggle="tab" data-bs-target="#chat">💬 Titan AI Hub</button></li></ul><div class="tab-content"><div class="tab-pane fade show active" id="leads"><div class="card shadow-sm"><div class="card-body p-0"><div class="table-responsive"><table class="table table-hover align-middle mb-0"><thead><tr><th>Status</th><th>Address</th><th>Owner</th><th>Link</th></tr></thead><tbody>{% for lead in leads %}<tr><td><select class="form-select form-select-sm" onchange="updateStatus({{ lead.id }}, this.value)"><option {% if lead.status == 'New' %}selected{% endif %}>New</option><option {% if lead.status == 'Hot' %}selected{% endif %}>Hot</option></select></td><td class="fw-bold">{{ lead.address }}</td><td>{{ lead.name }}</td><td><a href="{{ lead.link }}" target="_blank" class="btn btn-sm btn-outline-primary"><i class="fas fa-external-link-alt"></i></a></td></tr>{% endfor %}</tbody></table></div></div></div></div><div class="tab-pane fade" id="hunter"><div class="card bg-dark text-white p-5 text-center shadow-lg"><h2>🕵️ Industrial Lead Scraper Engine</h2><p class="text-muted">High-volume combinatorial extraction across your cluster.</p><div class="row justify-content-center mt-4 g-3"><div class="col-md-3"><select id="huntState" class="form-select" onchange="loadCities()"><option value="">State</option></select></div><div class="col-md-3"><select id="huntCity" class="form-select"><option value="">City</option></select></div><div class="col-md-3"><button onclick="runHunt()" class="btn btn-warning w-100 fw-bold shadow">START SCAN</button></div></div></div></div><div class="tab-pane fade" id="email"><div class="card shadow-sm border-primary"><div class="card-header bg-primary text-white fw-bold d-flex justify-content-between"><span>📧 Global Outreach Config</span><small>Use tags: [[ADDRESS]], [[NAME]]</small></div><div class="card-body p-4"><form action="/email/template/save" method="POST" class="mb-4"><textarea name="template" class="form-control mb-2" rows="4">{{ user.email_template }}</textarea><button class="btn btn-sm btn-primary">Save Template</button></form><hr>{% if not gmail_connected %}<div class="alert alert-danger">Connect App Password in Settings!</div>{% endif %}<div class="mb-3"><label class="form-label fw-bold">Outreach Subject</label><input id="emailSubject" class="form-control" value="Regarding property at [[ADDRESS]]"></div><button onclick="sendBlast()" class="btn btn-dark w-100 fw-bold shadow" {% if not gmail_connected %}disabled{% endif %}>🚀 Launch Mission</button></div></div></div><div class="tab-pane fade" id="history"><div class="card shadow-sm border-0"><div class="card-body p-4"><h5 class="fw-bold mb-3">Previous Sent History</h5><div class="list-group">{% for item in history %}<div class="list-group-item"><h6 class="mb-1 fw-bold">{{ item.address }}</h6><p class="mb-1 small">{{ item.message }}...</p><small class="text-primary">To: {{ item.recipient_email }} | {{ item.sent_at.strftime('%m-%d %H:%M') }}</small></div>{% else %}<p>No outreach history found.</p>{% endfor %}</div></div></div></div><div class="tab-pane fade" id="chat"><div class="card shadow-sm"><div class="card-header bg-info text-white fw-bold">💬 TITAN AI INTELLIGENCE</div><div class="card-body overflow-auto" id="ai-log" style="height:350px;"><div class="alert alert-secondary small shadow-sm"><b>Titan AI:</b> Welcome to the Production Intelligence Hub. I am synchronized with your industrial leads. I can analyze properties, draft cash-offer contracts, or plan marketing strategies. How can I assist you today?</div></div><div class="card-footer"><div class="input-group shadow-sm"><input id="ai-prompt" class="form-control" placeholder="Ask Engine anything..."><button onclick="askAI()" class="btn btn-info text-white fw-bold">Execute Prompt</button></div></div></div></div></div></div></div><div class="modal fade" id="settingsModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><form action="/settings/save" method="POST"><div class="modal-body"><h6>Gmail Industrial Config</h6><input name="smtp_email" class="form-control mb-2" value="{{ user.smtp_email or '' }}" placeholder="Gmail Address"><input type="password" name="smtp_password" class="form-control mb-2" value="{{ user.smtp_password or '' }}" placeholder="16-Character App Password"></div><div class="modal-footer"><button class="btn btn-primary">Save Settings</button></div></form></div></div></div><div class="modal fade" id="addLeadModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><form action="/leads/add" method="POST"><div class="modal-body"><h6>Manual Entry</h6><input name="address" class="form-control mb-2" placeholder="Address" required><input name="name" class="form-control mb-2" placeholder="Owner Name"><input name="phone" class="form-control mb-2" placeholder="Phone"><input name="email" class="form-control mb-2" placeholder="Email"></div><div class="modal-footer"><button type="submit" class="btn btn-success">Save</button></div></form></div></div></div><script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script><script>const usData = {{ us_data_json|safe }}; window.onload = function() { const s = document.getElementById("huntState"); for (let st in usData) { let o = document.createElement("option"); o.value = st; o.innerText = st; s.appendChild(o); } setInterval(updateTerminal, 2000); }; function loadCities() { const st = document.getElementById("huntState").value; const c = document.getElementById("huntCity"); c.innerHTML = '<option value="">Select City</option>'; if(st) usData[st].forEach(ct => { let o = document.createElement("option"); o.value = ct; o.innerText = ct; c.appendChild(o); }); } async function updateTerminal() { const t = document.getElementById('system-terminal'); try { const r = await fetch('/logs'); const l = await r.json(); t.innerHTML = l.join('<br>'); t.scrollTop = t.scrollHeight; } catch(e) {} } async function runHunt() { const city = document.getElementById('huntCity').value; const state = document.getElementById('huntState').value; if(!city || !state) return alert("Select location."); const r = await fetch('/leads/hunt', {method:'POST', body:new URLSearchParams({city, state})}); const d = await r.json(); alert(d.message); } async function sendBlast() { const f = new FormData(); f.append('subject', document.getElementById('emailSubject').value); f.append('body', ''); const r = await fetch('/email/campaign', {method:'POST', body:f}); const d = await r.json(); alert(d.message); } async function askAI() { const p = document.getElementById('ai-prompt').value; const log = document.getElementById('ai-log'); log.innerHTML += `<div class='text-end small mb-2 text-primary'><b>Investor:</b> ${p}</div>`; const r = await fetch('/ai/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message: p})}); const d = await r.json(); log.innerHTML += `<div class='alert alert-secondary small shadow-sm'><b>Titan AI:</b> ${d.response}</div>`; log.scrollTop = log.scrollHeight; document.getElementById('ai-prompt').value = ''; } async function updateStatus(id, s) { await fetch('/leads/update/'+id, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status:s})}); }</script>{% endblock %}"""
}

# --- GLOBAL BOOTSTRAPPER INVOCATION ---
write_industrial_templates(INDUSTRIAL_UI)

@app.context_processor
def industrial_processor(): return dict(us_data_json=json.dumps(USA_STATES))

if __name__ == "__main__":
    app.run(debug=True, port=5000)

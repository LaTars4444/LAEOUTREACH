import os
import random
import time
import base64
import json
# Allow HTTP for OAuth on Render (Required for internal callback handling)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText

# Third-party imports
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_required, current_user, login_user, logout_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# GOOGLE / YOUTUBE IMPORTS
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# AI & VIDEO IMPORTS
import stripe
from groq import Groq
from gtts import gTTS
from moviepy.editor import ImageClip, AudioFileClip

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super_secret_key')

# Persistent Database Config
if os.path.exists('/var/data'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/data/titan.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///titan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# API Clients
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# OAUTH CREDENTIALS (LOADED FROM ENV)
CREDS = {
    'google': {
        'id': os.environ.get("GOOGLE_CLIENT_ID"),
        'secret': os.environ.get("GOOGLE_CLIENT_SECRET")
    },
    'tiktok': {
        'key': os.environ.get("TIKTOK_CLIENT_KEY"),
        'secret': os.environ.get("TIKTOK_CLIENT_SECRET")
    },
    'meta': {
        'id': os.environ.get("META_CLIENT_ID"),
        'secret': os.environ.get("META_CLIENT_SECRET")
    }
}

# Folders
UPLOAD_FOLDER = 'static/uploads'
VIDEO_FOLDER = 'static/videos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)

# ---------------------------------------------------------
# 2. DATABASE MODELS
# ---------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=True) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # --- SOCIAL TOKENS ---
    google_token = db.Column(db.Text, nullable=True)   # Youtube/Gmail
    tiktok_token = db.Column(db.Text, nullable=True)   # TikTok
    meta_token = db.Column(db.Text, nullable=True)     # FB/Insta
    
    subscription_status = db.Column(db.String(50), default='free') 
    subscription_end = db.Column(db.DateTime, nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# ---------------------------------------------------------
# 3. SOCIAL AUTHENTICATION ROUTES (CONNECT ACCOUNTS)
# ---------------------------------------------------------

# --- GOOGLE (YOUTUBE + GMAIL) ---
@app.route('/auth/google')
@login_required
def auth_google():
    flow = Flow.from_client_config(
        client_config={"web": {"client_id": CREDS['google']['id'], "client_secret": CREDS['google']['secret'], "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}},
        scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/gmail.send", "openid", "https://www.googleapis.com/auth/userinfo.email"]
    )
    flow.redirect_uri = url_for('callback_google', _external=True)
    auth_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['google_state'] = state
    return redirect(auth_url)

@app.route('/auth/google/callback')
@login_required
def callback_google():
    flow = Flow.from_client_config(
        client_config={"web": {"client_id": CREDS['google']['id'], "client_secret": CREDS['google']['secret'], "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}},
        scopes=[], state=session['google_state']
    )
    flow.redirect_uri = url_for('callback_google', _external=True)
    flow.fetch_token(authorization_response=request.url)
    current_user.google_token = flow.credentials.to_json()
    db.session.commit()
    flash('Google Connected!', 'success')
    return redirect(url_for('dashboard'))

# --- TIKTOK ---
@app.route('/auth/tiktok')
@login_required
def auth_tiktok():
    # TikTok OAuth V2 URL Construction
    csrf_state = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=10))
    session['tiktok_state'] = csrf_state
    url = f"https://www.tiktok.com/v2/auth/authorize/?client_key={CREDS['tiktok']['key']}&scope=video.upload,user.info.basic&response_type=code&redirect_uri={url_for('callback_tiktok', _external=True)}&state={csrf_state}"
    return redirect(url)

@app.route('/auth/tiktok/callback')
@login_required
def callback_tiktok():
    code = request.args.get('code')
    # Exchange code for token
    data = {
        'client_key': CREDS['tiktok']['key'],
        'client_secret': CREDS['tiktok']['secret'],
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': url_for('callback_tiktok', _external=True)
    }
    r = requests.post('https://open.tiktokapis.com/v2/oauth/token/', data=data)
    if r.status_code == 200:
        current_user.tiktok_token = json.dumps(r.json())
        db.session.commit()
        flash('TikTok Connected!', 'success')
    else:
        flash('TikTok Connection Failed', 'error')
    return redirect(url_for('dashboard'))

# --- META (FB/INSTA) ---
@app.route('/auth/meta')
@login_required
def auth_meta():
    # Facebook Login URL
    url = f"https://www.facebook.com/v18.0/dialog/oauth?client_id={CREDS['meta']['id']}&redirect_uri={url_for('callback_meta', _external=True)}&scope=pages_manage_posts,instagram_content_publish"
    return redirect(url)

@app.route('/auth/meta/callback')
@login_required
def callback_meta():
    code = request.args.get('code')
    # Exchange for User Token
    url = f"https://graph.facebook.com/v18.0/oauth/access_token?client_id={CREDS['meta']['id']}&redirect_uri={url_for('callback_meta', _external=True)}&client_secret={CREDS['meta']['secret']}&code={code}"
    r = requests.get(url)
    if r.status_code == 200:
        current_user.meta_token = json.dumps(r.json())
        db.session.commit()
        flash('Meta Connected!', 'success')
    else:
        flash('Meta Connection Failed', 'error')
    return redirect(url_for('dashboard'))

# ---------------------------------------------------------
# 4. AUTO-POSTING LOGIC (THE ENGINE)
# ---------------------------------------------------------
@app.route('/social/post', methods=['POST'])
@login_required
def social_post():
    data = request.json
    platform = data.get('platform')
    video_rel_path = data.get('video_path')
    
    if not video_rel_path: return jsonify({'error': 'No video provided'}), 400
    
    # Absolute Path for Internal Uploads
    abs_path = os.path.join(os.getcwd(), video_rel_path.strip('/'))
    # Public URL for Meta/TikTok URL uploads (Requires Render domain)
    public_url = f"{request.url_root}{video_rel_path.strip('/')}"

    # --- 1. YOUTUBE UPLOAD ---
    if platform == 'youtube':
        if not current_user.google_token: return jsonify({'error': 'Connect YouTube first'}), 400
        try:
            creds = Credentials.from_authorized_user_info(json.loads(current_user.google_token))
            youtube = build('youtube', 'v3', credentials=creds)
            
            body = {
                'snippet': {'title': 'New Property Deal! #Shorts', 'description': 'Generated by Titan AI', 'categoryId': '22'},
                'status': {'privacyStatus': 'public', 'selfDeclaredMadeForKids': False}
            }
            media = MediaFileUpload(abs_path, chunksize=-1, resumable=True)
            request_upload = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
            response = request_upload.execute()
            return jsonify({'message': f"Posted to YouTube! ID: {response['id']}"})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # --- 2. TIKTOK UPLOAD ---
    elif platform == 'tiktok':
        if not current_user.tiktok_token: return jsonify({'error': 'Connect TikTok first'}), 400
        try:
            token_data = json.loads(current_user.tiktok_token)
            access_token = token_data.get('access_token')
            
            # TikTok V2 Init Upload
            init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            init_res = requests.post(init_url, headers=headers, json={"post_info": {"title": "Deal Alert!"}, "source_info": {"source": "FILE_UPLOAD"}})
            
            if init_res.status_code != 200: return jsonify({'error': 'TikTok Init Failed'}), 400
            
            upload_url = init_res.json()['data']['upload_url']
            
            # Put Video File
            with open(abs_path, 'rb') as f:
                requests.put(upload_url, data=f)
                
            return jsonify({'message': 'Posted to TikTok!'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # --- 3. INSTAGRAM/FACEBOOK UPLOAD ---
    elif platform == 'meta':
        if not current_user.meta_token: return jsonify({'error': 'Connect Meta first'}), 400
        try:
            token_data = json.loads(current_user.meta_token)
            access_token = token_data.get('access_token')
            
            # 1. Get User ID
            me_res = requests.get(f"https://graph.facebook.com/me?access_token={access_token}").json()
            user_id = me_res['id']
            
            # 2. Get Accounts (Pages)
            accounts_res = requests.get(f"https://graph.facebook.com/{user_id}/accounts?access_token={access_token}").json()
            if not accounts_res.get('data'): return jsonify({'error': 'No Facebook Pages found'}), 400
            
            page_id = accounts_res['data'][0]['id']
            page_token = accounts_res['data'][0]['access_token']
            
            # 3. Post Video to Page (Reels)
            post_url = f"https://graph.facebook.com/{page_id}/videos"
            post_data = {
                'access_token': page_token,
                'file_url': public_url, # Meta downloads from your server
                'description': 'Hot new property! #RealEstate'
            }
            final_res = requests.post(post_url, data=post_data).json()
            
            if 'id' in final_res:
                return jsonify({'message': f"Posted to Facebook Reel! ID: {final_res['id']}"})
            else:
                return jsonify({'error': json.dumps(final_res)})
                
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Invalid Platform'}), 400

# ---------------------------------------------------------
# 5. AI VIDEO GENERATOR (FACTORY)
# ---------------------------------------------------------
@app.route('/video/create', methods=['POST'])
@login_required
def create_video():
    if not groq_client: return jsonify({'error': 'Groq Key Missing'}), 500
    
    desc = request.form.get('description')
    photo = request.files.get('photo')
    if not photo or not desc: return jsonify({'error': 'Missing data'}), 400

    try:
        filename = secure_filename(f"img_{int(time.time())}.jpg")
        img_path = os.path.join(UPLOAD_FOLDER, filename)
        photo.save(img_path)

        # AI Script
        chat = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": "Write a 15s viral real estate script."}, {"role": "user", "content": desc}],
            model="llama-3.3-70b-versatile"
        )
        script = chat.choices[0].message.content

        # Audio
        audio_name = f"audio_{int(time.time())}.mp3"
        audio_path = os.path.join(VIDEO_FOLDER, audio_name)
        tts = gTTS(text=script, lang='en')
        tts.save(audio_path)

        # Video
        audio_clip = AudioFileClip(audio_path)
        video_clip = ImageClip(img_path).set_duration(audio_clip.duration + 1).set_audio(audio_clip)
        
        vid_name = f"video_{int(time.time())}.mp4"
        out_path = os.path.join(VIDEO_FOLDER, vid_name)
        video_clip.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac")

        return jsonify({'video_url': f"/{VIDEO_FOLDER}/{vid_name}", 'video_path': f"{VIDEO_FOLDER}/{vid_name}"})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------------------------------------------------
# 6. DASHBOARD TEMPLATES (UI)
# ---------------------------------------------------------
html_templates = {
    'base.html': """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>TITAN</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"></head><body class="bg-light"><nav class="navbar navbar-dark bg-dark"><div class="container"><a class="navbar-brand" href="/">TITAN ⚡</a></div></nav><div class="container mt-4">{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ 'danger' if category == 'error' else 'success' }}">{{ message }}</div>{% endfor %}{% endif %}{% endwith %}{% block content %}{% endblock %}</div></body></html>""",
    
    'dashboard.html': """
{% extends "base.html" %}
{% block content %}
<div class="row">
    <!-- CONNECT -->
    <div class="col-12 mb-4">
        <div class="card shadow-sm">
            <div class="card-header bg-dark text-white">📡 Social Connections</div>
            <div class="card-body d-flex gap-2">
                {% if user.google_token %} <button class="btn btn-success" disabled>Google Linked</button> {% else %} <a href="/auth/google" class="btn btn-outline-danger">Link YouTube/Gmail</a> {% endif %}
                {% if user.tiktok_token %} <button class="btn btn-success" disabled>TikTok Linked</button> {% else %} <a href="/auth/tiktok" class="btn btn-outline-dark">Link TikTok</a> {% endif %}
                {% if user.meta_token %} <button class="btn btn-success" disabled>Meta Linked</button> {% else %} <a href="/auth/meta" class="btn btn-outline-primary">Link FB/Insta</a> {% endif %}
            </div>
        </div>
    </div>
    
    <!-- VIDEO FACTORY -->
    <div class="col-lg-6 mb-4">
        <div class="card shadow-sm h-100">
            <div class="card-header bg-primary text-white">🎬 AI Video Generator</div>
            <div class="card-body">
                <input type="file" id="videoPhoto" class="form-control mb-3">
                <textarea id="videoInput" class="form-control mb-3" rows="3" placeholder="Describe property..."></textarea>
                <button onclick="createVideo()" class="btn btn-primary w-100" id="genBtn">🎥 Generate Video</button>
                <div id="loading" class="d-none mt-3 text-center"><div class="spinner-border"></div></div>
                <div id="videoResult" class="d-none mt-3">
                    <video id="player" controls width="100%" class="border rounded mb-2"></video>
                    <input type="hidden" id="currentVideoPath">
                    <div class="d-grid gap-2">
                        <button onclick="postToSocials('youtube')" class="btn btn-danger">Post to YouTube</button>
                        <button onclick="postToSocials('tiktok')" class="btn btn-dark">Post to TikTok</button>
                        <button onclick="postToSocials('meta')" class="btn btn-primary">Post to FB/Insta</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- EMAIL MACHINE -->
    <div class="col-lg-6 mb-4">
        <div class="card shadow-sm h-100">
            <div class="card-header bg-danger text-white">📧 Email Machine</div>
            <div class="card-body">
                <textarea id="recipients" class="form-control mb-2" placeholder="Emails..."></textarea>
                <input id="subject" class="form-control mb-2" placeholder="Subject">
                <textarea id="body" class="form-control mb-2" placeholder="Message..."></textarea>
                <button onclick="sendEmails()" class="btn btn-danger w-100">Send Campaign</button>
            </div>
        </div>
    </div>
</div>
<script>
async function createVideo() {
    const file = document.getElementById('videoPhoto').files[0];
    const desc = document.getElementById('videoInput').value;
    if(!file || !desc) return alert("Upload photo & text");
    document.getElementById('loading').classList.remove('d-none');
    const formData = new FormData();
    formData.append('photo', file);
    formData.append('description', desc);
    const res = await fetch('/video/create', {method: 'POST', body: formData});
    const data = await res.json();
    document.getElementById('loading').classList.add('d-none');
    if(data.video_url) {
        document.getElementById('videoResult').classList.remove('d-none');
        document.getElementById('player').src = data.video_url;
        document.getElementById('currentVideoPath').value = data.video_path;
    } else { alert(data.error); }
}
async function postToSocials(platform) {
    const videoPath = document.getElementById('currentVideoPath').value;
    if(!confirm("Post to " + platform + "?")) return;
    const res = await fetch('/social/post', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({platform: platform, video_path: videoPath})
    });
    const data = await res.json();
    alert(data.message || data.error);
}
</script>
{% endblock %}
""",
    'login.html': """{% extends "base.html" %} {% block content %} <form method="POST" class="mt-5 mx-auto" style="max-width:300px"><h3>Login</h3><input name="email" class="form-control mb-2" placeholder="Email"><input type="password" name="password" class="form-control mb-2" placeholder="Password"><button class="btn btn-primary w-100">Login</button><a href="/register">Register</a></form> {% endblock %}""",
    'register.html': """{% extends "base.html" %} {% block content %} <form method="POST" class="mt-5 mx-auto" style="max-width:300px"><h3>Register</h3><input name="email" class="form-control mb-2" placeholder="Email"><input type="password" name="password" class="form-control mb-2" placeholder="Password"><button class="btn btn-success w-100">Join</button></form> {% endblock %}"""
}
if not os.path.exists('templates'): os.makedirs('templates')
for f, c in html_templates.items():
    with open(f'templates/{f}', 'w') as file: file.write(c.strip())

# ---------------------------------------------------------
# 8. GENERAL ROUTES
# ---------------------------------------------------------
@app.route('/')
def index(): return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and (user.password == request.form['password'] or check_password_hash(user.password, request.form['password'])):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Error', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not User.query.filter_by(email=request.form['email']).first():
            hashed = generate_password_hash(request.form['password'], method='scrypt')
            user = User(email=request.form['email'], password=hashed)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)

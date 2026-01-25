from extensions import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    smtp_email = db.Column(db.String(150), nullable=True)
    smtp_password = db.Column(db.String(150), nullable=True)
    email_template = db.Column(db.Text, default="Hi [[NAME]], I am interested in [[ADDRESS]]. cash offer?")
    subscription_status = db.Column(db.String(50), default='free')
    subscription_end = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Buy Box Fields
    bb_property_type = db.Column(db.String(50))
    bb_locations = db.Column(db.String(255))
    bb_min_price = db.Column(db.Integer)
    bb_max_price = db.Column(db.Integer)
    bb_condition = db.Column(db.String(50))
    bb_strategy = db.Column(db.String(50))
    bb_funding = db.Column(db.String(50))
    bb_timeline = db.Column(db.String(50))

    videos = db.relationship('Video', backref='owner', lazy=True)
    outreach_logs = db.relationship('OutreachLog', backref='user', lazy=True)

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    address = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(150), default="Property Owner")
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    asking_price = db.Column(db.String(50), nullable=True)
    link = db.Column(db.String(500))
    status = db.Column(db.String(50), default="New")
    source = db.Column(db.String(100), default="Industrial Network")
    emailed_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OutreachLog(db.Model):
    __tablename__ = 'outreach_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_email = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255))
    message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

class Video(db.Model):
    __tablename__ = 'videos'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

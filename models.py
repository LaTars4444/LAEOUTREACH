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
    groq_api_key = db.Column(db.String(255), nullable=True)
    
    email_template = db.Column(db.Text, default="Hi [[NAME]], I am a local cash investor interested in your property at [[ADDRESS]]. Can we discuss an offer?")
    
    subscription_status = db.Column(db.String(50), default='free')
    trial_start = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Buy Box
    bb_locations = db.Column(db.String(255))
    bb_min_price = db.Column(db.Integer)
    bb_max_price = db.Column(db.Integer)
    bb_property_type = db.Column(db.String(50))
    bb_condition = db.Column(db.String(50))
    bb_strategy = db.Column(db.String(50))

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    address = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(150), default="Property Owner")
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), default="New")
    source = db.Column(db.String(100), default="System")
    emailed_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Valuation
    arv_estimate = db.Column(db.Integer)
    repair_estimate = db.Column(db.Integer)
    asking_price = db.Column(db.Integer)

class Investor(db.Model):
    __tablename__ = 'investors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150))
    phone = db.Column(db.String(50))
    markets = db.Column(db.String(255))
    min_price = db.Column(db.Integer)
    max_price = db.Column(db.Integer)
    asset_class = db.Column(db.String(50))
    strategy = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OutreachLog(db.Model):
    __tablename__ = 'outreach_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_email = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255))
    message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="Sent")

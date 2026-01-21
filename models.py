from datetime import datetime
from flask_login import UserMixin
from extensions import db  # <--- CHANGED: Removed the "." before extensions

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # AUTH & STRIPE
    google_token = db.Column(db.Text, nullable=True)
    stripe_customer_id = db.Column(db.String(100), nullable=True)
    subscription_status = db.Column(db.String(50), default='free') 
    subscription_end = db.Column(db.DateTime, nullable=True)
    
    # BUY BOX FIELDS
    bb_property_type = db.Column(db.String(50))
    bb_locations = db.Column(db.String(255))
    bb_min_price = db.Column(db.Integer)
    bb_max_price = db.Column(db.Integer)
    bb_condition = db.Column(db.String(50))
    bb_strategy = db.Column(db.String(50))
    bb_funding = db.Column(db.String(50)) 
    bb_timeline = db.Column(db.String(50))

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    address = db.Column(db.String(255), nullable=False)
    property_type = db.Column(db.String(50))
    year_built = db.Column(db.Integer)
    roof_age = db.Column(db.Integer)
    hvac_age = db.Column(db.Integer)
    condition_plumbing = db.Column(db.String(50))
    condition_electrical = db.Column(db.String(50))
    condition_overall = db.Column(db.String(50))
    occupancy_status = db.Column(db.String(50))
    desired_price = db.Column(db.Integer)
    timeline = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    photos_url = db.Column(db.String(500))
    
    # TitanFinance Metrics
    arv_estimate = db.Column(db.Integer)
    repair_estimate = db.Column(db.Integer)
    max_allowable_offer = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OutreachLog(db.Model):
    __tablename__ = 'outreach_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_email = db.Column(db.String(150), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50)) 
    error_msg = db.Column(db.Text)

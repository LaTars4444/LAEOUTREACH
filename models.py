from extensions import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    """
    Industrial User Security Architecture.
    Includes persistent outreach templates and buy box logic.
    Encryption: Utilizes Industrial Scrypt Hashing via Werkzeug.
    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    smtp_email = db.Column(db.String(150), nullable=True)
    smtp_password = db.Column(db.String(150), nullable=True)
    
    # Universal Outreach Script Template (Dynamically Editable via UI)
    email_template = db.Column(db.Text, default="Hi [[NAME]], I am a local cash buyer. I saw your property at [[ADDRESS]] and would like to make an offer. Can we talk today?")
    
    google_token = db.Column(db.Text, nullable=True)
    stripe_customer_id = db.Column(db.String(100), nullable=True)
    subscription_status = db.Column(db.String(50), default='free')
    subscription_end = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Industrial Buy Box Logic
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
    """
    Industrial Lead Data Model.
    Supports high-density property metadata and owner identification.
    """
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    address = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(150), default="Property Owner")
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    asking_price = db.Column(db.String(50), nullable=True)
    property_type = db.Column(db.String(50))
    year_built = db.Column(db.Integer)
    roof_age = db.Column(db.Integer)
    hvac_age = db.Column(db.Integer)
    condition_overall = db.Column(db.String(50))
    occupancy_status = db.Column(db.String(50))
    link = db.Column(db.String(500))
    status = db.Column(db.String(50), default="New")
    source = db.Column(db.String(100), default="Enterprise Network")
    emailed_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # TitanFinance Valuation Metrics
    arv_estimate = db.Column(db.Integer)
    repair_estimate = db.Column(db.Integer)
    max_allowable_offer = db.Column(db.Integer)

class OutreachLog(db.Model):
    """
    Industrial Historical Outreach Model.
    Surgical Fix: Column 'address' and 'message' defined for Sent History Pane.
    """
    __tablename__ = 'outreach_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_email = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255))
    message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="Delivered")

class Video(db.Model):
    """ Industrial Media Production Data. """
    __tablename__ = 'videos'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# INDUSTRIAL PERSISTENCE ENGINE
# Standardized SQLAlchemy initialization for industrial-scale lead storage.
db = SQLAlchemy()

# INDUSTRIAL SESSION MANAGEMENT
# Manages authenticated investor sessions and secure production gateways.
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'

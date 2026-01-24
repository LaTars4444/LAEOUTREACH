Industrial standard initialization to prevent circular dependency loops.
Architected for Python 3.10.12 / Render Production Environments.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Industrial Persistence Layer initialization
db = SQLAlchemy()

# Industrial Authentication Layer initialization
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'

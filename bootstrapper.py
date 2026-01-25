import os
from sqlalchemy import inspect, text
from extensions import db

def run_industrial_bootstrapper(app):
    """
    This engine executes at the global scope during the Gunicorn import.
    1. It forces the templates to exist on the Render disk.
    2. It audits the database schema and injects missing columns.
    """
    with app.app_context():
        # 1. DATABASE SCHEMA HEALING (Eliminates 500 OperationalErrors)
        db.create_all()
        inspector = inspect(db.engine)
        
        # Audit Outreach History Table
        outreach_cols = [c['name'] for c in inspector.get_columns('outreach_logs')]
        if 'address' not in outreach_cols:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE outreach_logs ADD COLUMN address TEXT'))
                conn.commit()
        if 'message' not in outreach_cols:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE outreach_logs ADD COLUMN message TEXT'))
                conn.commit()
                
        # Audit User Table
        user_cols = [c['name'] for c in inspector.get_columns('users')]
        if 'email_template' not in user_cols:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE users ADD COLUMN email_template TEXT'))
                conn.commit()

def write_industrial_templates(templates_dict):
    """ Forces the template dictionary onto the production disk. """
    template_dir = os.path.join(os.getcwd(), 'templates')
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)
        
    for name, content in templates_dict.items():
        path = os.path.join(template_dir, name)
        with open(path, 'w') as f:
            f.write(content.strip())

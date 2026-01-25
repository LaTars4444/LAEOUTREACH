import os

class EnterpriseConfig:
    """
    Standardizes production settings for the Titan Intelligence Platform.
    Ensures consistent timeout handling and industrial media buffering.
    """
    # IDENTITY & SECURITY
    SECRET_KEY = os.environ.get('SECRET_KEY', 'titan_enterprise_standard_v15_auth_!@#')
    MAX_CONTENT_LENGTH = 128 * 1024 * 1024 # 128MB Production Buffer
    
    # PERSISTENCE ARCHITECTURE
    # Logic handles Render Persistent Disks /var/data/
    if os.path.exists('/var/data'):
        SQLALCHEMY_DATABASE_URI = 'sqlite:////var/data/titan.db'
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///titan.db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # INDUSTRIAL API KEYS
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
    GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
    GOOGLE_SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
    
    # PRODUCTION TIMEOUTS
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SCRAPE_PAGINATION_LIMIT = 100 # 10 pages per combinatorial
    HUMAN_DELAY_MIN = 5
    HUMAN_DELAY_MAX = 15

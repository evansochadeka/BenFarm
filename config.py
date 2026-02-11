import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Admin credentials
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@benfarming.com')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    ADMIN_FULL_NAME = os.getenv('ADMIN_FULL_NAME', 'System Administrator')
    
    # Community settings
    POSTS_PER_PAGE = 20
    REPLIES_PER_PAGE = 10
    MAX_POST_LENGTH = 5000
    MAX_REPLY_LENGTH = 2000
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # ============ DATABASE CONFIGURATION - POSTGRESQL READY ============
    # Get database URL from environment variable
    database_url = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    
    # CRITICAL FIX: Convert postgres:// to postgresql:// (Render uses postgres:// but SQLAlchemy needs postgresql://)
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Connection pooling for PostgreSQL (helps with free tier)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }
    
    # File uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    # Ensure upload folder exists
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    # API Keys
    COHERE_API_KEY = os.getenv('COHERE_API_KEY')
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
    
    # Cohere configuration
    COHERE_MODEL = 'c4ai-aya-expanse-8b'
    COHERE_TEMPERATURE = 0.3
    COHERE_MAX_TOKENS = 800
    
    # Session configuration
    PREFERRED_URL_SCHEME = 'https'
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

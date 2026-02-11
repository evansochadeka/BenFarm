import os
from datetime import timedelta  # Add this import
from dotenv import load_dotenv

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
    SECRET_KEY = os.getenv('SECRET_KEY', os.getenv('SESSION_SECRET', 'dev-secret-key-change-in-production'))
    
    # Database - Use PostgreSQL on Render, SQLite locally
    database_url = os.getenv('DATABASE_URL', 'sqlite:///database.db')
    
    # Fix PostgreSQL URL format for Render/Railway
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    # Ensure upload folder exists
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    # API Keys
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    PERENUAL_API_KEY = os.getenv('PERENUAL_API_KEY')
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
    PLANTID_API_KEY = os.getenv('PLANTID_API_KEY')
    WEGLOT_API_KEY = os.getenv('WEGLOT_API_KEY')
    COHERE_API_KEY = os.getenv('COHERE_API_KEY')
    
    # Cohere specific configuration
    COHERE_MODEL = 'c4ai-aya-expanse-8b'
    COHERE_TEMPERATURE = 0.3
    COHERE_MAX_TOKENS = 800
    
    # Flask configuration
    PREFERRED_URL_SCHEME = 'https'
    
    # Session and cookie configuration
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)  # Now works with import
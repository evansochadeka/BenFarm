# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Create SINGLE instances that will be shared across the app
db = SQLAlchemy()
login_manager = LoginManager()
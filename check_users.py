# check_users.py
from app import app
from models import db, User, AdminUser

with app.app_context():
    print("=== REGULAR USERS ===")
    users = User.query.all()
    for user in users:
        print(f"ID: {user.id}, Email: {user.email}, Name: {user.full_name}, Active: {user.is_active}")
    
    print("\n=== ADMIN USERS ===")
    admins = AdminUser.query.all()
    for admin in admins:
        print(f"ID: {admin.id}, Email: {admin.email}, Name: {admin.full_name}, Super: {admin.is_super_admin}")
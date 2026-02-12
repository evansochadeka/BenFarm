from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user
from extensions import db
from models import User, AdminUser, CommunityPost, CommunityReply, DirectMessage, Notification, DiseaseReport, InventoryItem, Customer, Sale, Order, Review
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import json
from functools import wraps

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login as admin first', 'error')
            return redirect(url_for('admin.login'))
        admin_user = AdminUser.query.filter_by(email=current_user.email).first()
        if not admin_user:
            flash('Admin access required', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    """Decorator to require super admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login as admin first', 'error')
            return redirect(url_for('admin.login'))
        admin_user = AdminUser.query.filter_by(email=current_user.email).first()
        if not admin_user or not admin_user.is_super_admin:
            flash('Super admin access required', 'error')
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page"""
    if current_user.is_authenticated:
        admin = AdminUser.query.filter_by(email=current_user.email).first()
        if admin:
            if admin.is_super_admin:
                return redirect(url_for('admin.super_dashboard'))
            return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        admin = AdminUser.query.filter_by(email=email).first()
        
        if admin and admin.check_password(password):
            login_user(admin, remember=True)
            admin.last_login = datetime.utcnow()
            db.session.commit()
            
            session['admin_logged_in'] = True
            session['admin_email'] = admin.email
            session.permanent = True
            
            flash(f'Welcome back, {admin.full_name}!', 'success')
            
            if admin.is_super_admin:
                return redirect(url_for('admin.super_dashboard'))
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid admin credentials', 'error')
    
    return render_template('admin/login.html')

# ============ FIXED LOGOUT ROUTE - Redirects to main logout ============
@admin_bp.route('/logout')
@login_required
def admin_logout():
    """Redirect to main logout - FIXED to use single logout route"""
    return redirect(url_for('logout'))

# ============ ADMIN DASHBOARD ============
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Regular admin dashboard"""
    total_users = User.query.count()
    total_farmers = User.query.filter_by(user_type='farmer').count()
    total_agrovets = User.query.filter_by(user_type='agrovet').count()
    total_officers = User.query.filter_by(user_type='extension_officer').count()
    total_posts = CommunityPost.query.count()
    total_replies = CommunityReply.query.count()
    total_messages = DirectMessage.query.count()
    total_orders = Order.query.count()
    total_reviews = Review.query.count()
    total_products = InventoryItem.query.count()
    total_sales = Sale.query.count()
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).limit(10).all()
    recent_messages = DirectMessage.query.order_by(DirectMessage.created_at.desc()).limit(10).all()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    recent_reviews = Review.query.order_by(Review.created_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_farmers=total_farmers,
                         total_agrovets=total_agrovets,
                         total_officers=total_officers,
                         total_posts=total_posts,
                         total_replies=total_replies,
                         total_messages=total_messages,
                         total_orders=total_orders,
                         total_reviews=total_reviews,
                         total_products=total_products,
                         total_sales=total_sales,
                         recent_users=recent_users,
                         recent_posts=recent_posts,
                         recent_messages=recent_messages,
                         recent_orders=recent_orders,
                         recent_reviews=recent_reviews)

# ============ SUPER ADMIN DASHBOARD ============
@admin_bp.route('/super/dashboard')
@login_required
@super_admin_required
def super_dashboard():
    """Super admin dashboard with full system control"""
    total_users = User.query.count()
    total_admins = AdminUser.query.count()
    total_farmers = User.query.filter_by(user_type='farmer').count()
    total_agrovets = User.query.filter_by(user_type='agrovet').count()
    total_officers = User.query.filter_by(user_type='extension_officer').count()
    total_disease_reports = DiseaseReport.query.count()
    total_posts = CommunityPost.query.count()
    total_replies = CommunityReply.query.count()
    total_messages = DirectMessage.query.count()
    total_orders = Order.query.count()
    total_reviews = Review.query.count()
    total_products = InventoryItem.query.count()
    total_sales = Sale.query.count()
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_admins = AdminUser.query.order_by(AdminUser.created_at.desc()).limit(10).all()
    recent_reports = DiseaseReport.query.order_by(DiseaseReport.created_at.desc()).limit(10).all()
    recent_posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).limit(10).all()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    recent_reviews = Review.query.order_by(Review.created_at.desc()).limit(10).all()
    
    return render_template('admin/super_dashboard.html',
                         total_users=total_users,
                         total_admins=total_admins,
                         total_farmers=total_farmers,
                         total_agrovets=total_agrovets,
                         total_officers=total_officers,
                         total_disease_reports=total_disease_reports,
                         total_posts=total_posts,
                         total_replies=total_replies,
                         total_messages=total_messages,
                         total_orders=total_orders,
                         total_reviews=total_reviews,
                         total_products=total_products,
                         total_sales=total_sales,
                         recent_users=recent_users,
                         recent_admins=recent_admins,
                         recent_reports=recent_reports,
                         recent_posts=recent_posts,
                         recent_orders=recent_orders,
                         recent_reviews=recent_reviews)

# ============ USER MANAGEMENT ============
@admin_bp.route('/users')
@admin_required
def manage_users():
    """Manage all users"""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/manage')
@login_required
@super_admin_required
def manage_all_users():
    """Super admin user management"""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/manage_users.html', users=users)

@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Edit user details"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.email = request.form.get('email')
        user.full_name = request.form.get('full_name')
        user.user_type = request.form.get('user_type')
        user.phone_number = request.form.get('phone_number')
        user.location = request.form.get('location')
        user.is_active = request.form.get('is_active') == 'on'
        user.is_verified = request.form.get('is_verified') == 'on'
        
        new_password = request.form.get('password')
        if new_password:
            user.set_password(new_password)
        
        db.session.commit()
        flash(f'User {user.full_name} updated successfully', 'success')
        return redirect(url_for('admin.manage_users'))
    
    return render_template('admin/edit_user.html', user=user)

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete user"""
    user = User.query.get_or_404(user_id)
    username = user.full_name
    
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {username} deleted successfully', 'success')
    return jsonify({'success': True})

@admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@super_admin_required
def toggle_user_status(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': user.is_active})

@admin_bp.route('/users/<int:user_id>/impersonate')
@login_required
@super_admin_required
def impersonate_user(user_id):
    """Impersonate a user (super admin only)"""
    user = User.query.get_or_404(user_id)
    login_user(user)
    flash(f'You are now logged in as {user.full_name}', 'success')
    return redirect(url_for('index'))

# ============ ADMIN MANAGEMENT ============
@admin_bp.route('/admins/manage')
@login_required
@super_admin_required
def manage_admins():
    """Manage admin users"""
    admins = AdminUser.query.order_by(AdminUser.created_at.desc()).all()
    return render_template('admin/manage_admins.html', admins=admins)

@admin_bp.route('/admins/create', methods=['POST'])
@login_required
@super_admin_required
def create_admin():
    """Create new admin user"""
    email = request.form.get('email')
    password = request.form.get('password')
    full_name = request.form.get('full_name')
    is_super_admin = request.form.get('is_super_admin') == 'on'
    
    if AdminUser.query.filter_by(email=email).first():
        flash('Admin with this email already exists', 'error')
        return redirect(url_for('admin.manage_admins'))
    
    admin = AdminUser(
        email=email,
        full_name=full_name,
        is_super_admin=is_super_admin,
        role='super_admin' if is_super_admin else 'admin'
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    
    flash(f'Admin {full_name} created successfully', 'success')
    return redirect(url_for('admin.manage_admins'))

@admin_bp.route('/admins/<int:admin_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_admin(admin_id):
    """Delete admin user"""
    admin = AdminUser.query.get_or_404(admin_id)
    
    if admin.email == current_user.email:
        flash('You cannot delete your own account', 'error')
        return jsonify({'success': False, 'error': 'Cannot delete own account'})
    
    if admin.email == 'benedict431@gmail.com':
        flash('Cannot delete the primary super admin account', 'error')
        return jsonify({'success': False, 'error': 'Cannot delete primary super admin'})
    
    db.session.delete(admin)
    db.session.commit()
    
    flash(f'Admin {admin.full_name} deleted successfully', 'success')
    return jsonify({'success': True})

@admin_bp.route('/admins/<int:admin_id>/toggle-super', methods=['POST'])
@login_required
@super_admin_required
def toggle_super_admin(admin_id):
    """Toggle super admin status"""
    admin = AdminUser.query.get_or_404(admin_id)
    
    if admin.email == current_user.email:
        flash('You cannot modify your own admin status', 'error')
        return jsonify({'success': False, 'error': 'Cannot modify own status'})
    
    if admin.email == 'benedict431@gmail.com':
        flash('Cannot modify the primary super admin status', 'error')
        return jsonify({'success': False, 'error': 'Cannot modify primary super admin'})
    
    admin.is_super_admin = not admin.is_super_admin
    admin.role = 'super_admin' if admin.is_super_admin else 'admin'
    db.session.commit()
    
    status = 'super admin' if admin.is_super_admin else 'regular admin'
    flash(f'{admin.full_name} is now a {status}', 'success')
    return jsonify({'success': True, 'is_super_admin': admin.is_super_admin})

# ============ POST MANAGEMENT ============
@admin_bp.route('/posts')
@admin_required
def manage_posts():
    """Manage community posts"""
    posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).all()
    return render_template('admin/posts.html', posts=posts)

@admin_bp.route('/posts/<int:post_id>/delete', methods=['POST'])
@admin_required
def delete_post(post_id):
    """Delete a community post"""
    post = CommunityPost.query.get_or_404(post_id)
    title = post.title
    
    db.session.delete(post)
    db.session.commit()
    
    flash(f'Post "{title}" deleted successfully', 'success')
    return jsonify({'success': True})

@admin_bp.route('/posts/<int:post_id>/toggle-pin', methods=['POST'])
@admin_required
def toggle_pin_post(post_id):
    """Toggle pin status of a post"""
    post = CommunityPost.query.get_or_404(post_id)
    post.is_pinned = not post.is_pinned
    db.session.commit()
    
    status = 'pinned' if post.is_pinned else 'unpinned'
    flash(f'Post {status} successfully', 'success')
    return jsonify({'success': True, 'is_pinned': post.is_pinned})

@admin_bp.route('/posts/<int:post_id>/toggle-close', methods=['POST'])
@admin_required
def toggle_close_post(post_id):
    """Toggle closed status of a post"""
    post = CommunityPost.query.get_or_404(post_id)
    post.is_closed = not post.is_closed
    db.session.commit()
    
    status = 'closed' if post.is_closed else 'opened'
    flash(f'Post {status} successfully', 'success')
    return jsonify({'success': True, 'is_closed': post.is_closed})

# ============ MESSAGE MANAGEMENT ============
@admin_bp.route('/messages')
@admin_required
def manage_messages():
    """Manage direct messages"""
    messages = DirectMessage.query.order_by(DirectMessage.created_at.desc()).all()
    return render_template('admin/messages.html', messages=messages)

@admin_bp.route('/messages/<int:message_id>/delete', methods=['POST'])
@admin_required
def delete_message(message_id):
    """Delete a direct message"""
    message = DirectMessage.query.get_or_404(message_id)
    
    db.session.delete(message)
    db.session.commit()
    
    flash('Message deleted successfully', 'success')
    return jsonify({'success': True})

@admin_bp.route('/conversations/<int:sender_id>/<int:receiver_id>/delete', methods=['POST'])
@admin_required
def delete_conversation(sender_id, receiver_id):
    """Delete entire conversation between two users"""
    DirectMessage.query.filter(
        ((DirectMessage.sender_id == sender_id) & (DirectMessage.receiver_id == receiver_id)) |
        ((DirectMessage.sender_id == receiver_id) & (DirectMessage.receiver_id == sender_id))
    ).delete()
    
    db.session.commit()
    flash('Conversation deleted successfully', 'success')
    return jsonify({'success': True})

# ============ DISEASE REPORT MANAGEMENT ============
@admin_bp.route('/disease-reports')
@admin_required
def manage_disease_reports():
    """Manage disease reports"""
    reports = DiseaseReport.query.order_by(DiseaseReport.created_at.desc()).all()
    return render_template('admin/disease_reports.html', reports=reports)

@admin_bp.route('/disease-reports/<int:report_id>/review', methods=['POST'])
@admin_required
def review_disease_report(report_id):
    """Review and update disease report status"""
    report = DiseaseReport.query.get_or_404(report_id)
    report.status = request.form.get('status', 'reviewed')
    report.reviewed_by = current_user.id
    report.reviewed_at = datetime.utcnow()
    db.session.commit()
    
    flash(f'Disease report #{report.id} updated successfully', 'success')
    return redirect(url_for('admin.manage_disease_reports'))

@admin_bp.route('/disease-reports/<int:report_id>/delete', methods=['POST'])
@admin_required
def delete_disease_report(report_id):
    """Delete a disease report"""
    report = DiseaseReport.query.get_or_404(report_id)
    db.session.delete(report)
    db.session.commit()
    
    flash('Disease report deleted successfully', 'success')
    return jsonify({'success': True})

# ============ ORDER MANAGEMENT ============
@admin_bp.route('/orders')
@admin_required
def manage_orders():
    """Manage all orders"""
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders)

@admin_bp.route('/orders/<int:order_id>/update-status', methods=['POST'])
@admin_required
def update_order_status(order_id):
    """Update order status"""
    order = Order.query.get_or_404(order_id)
    order.status = request.form.get('status')
    db.session.commit()
    
    flash(f'Order #{order.id} status updated to {order.status}', 'success')
    return redirect(url_for('admin.manage_orders'))

@admin_bp.route('/orders/<int:order_id>/delete', methods=['POST'])
@admin_required
def delete_order(order_id):
    """Delete an order"""
    order = Order.query.get_or_404(order_id)
    db.session.delete(order)
    db.session.commit()
    
    flash('Order deleted successfully', 'success')
    return jsonify({'success': True})

# ============ REVIEW MANAGEMENT ============
@admin_bp.route('/reviews')
@admin_required
def manage_reviews():
    """Manage all reviews"""
    reviews = Review.query.order_by(Review.created_at.desc()).all()
    return render_template('admin/reviews.html', reviews=reviews)

@admin_bp.route('/reviews/<int:review_id>/approve', methods=['POST'])
@admin_required
def approve_review(review_id):
    """Approve a review"""
    review = Review.query.get_or_404(review_id)
    review.status = 'approved'
    db.session.commit()
    
    flash('Review approved successfully', 'success')
    return redirect(url_for('admin.manage_reviews'))

@admin_bp.route('/reviews/<int:review_id>/reject', methods=['POST'])
@admin_required
def reject_review(review_id):
    """Reject a review"""
    review = Review.query.get_or_404(review_id)
    review.status = 'rejected'
    db.session.commit()
    
    flash('Review rejected successfully', 'success')
    return redirect(url_for('admin.manage_reviews'))

@admin_bp.route('/reviews/<int:review_id>/feature', methods=['POST'])
@admin_required
def feature_review(review_id):
    """Toggle featured status of a review"""
    review = Review.query.get_or_404(review_id)
    review.is_featured = not review.is_featured
    db.session.commit()
    
    status = 'featured' if review.is_featured else 'unfeatured'
    flash(f'Review {status} successfully', 'success')
    return jsonify({'success': True, 'is_featured': review.is_featured})

@admin_bp.route('/reviews/<int:review_id>/delete', methods=['POST'])
@admin_required
def delete_review(review_id):
    """Delete a review"""
    review = Review.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    
    flash('Review deleted successfully', 'success')
    return jsonify({'success': True})

# ============ SYSTEM SETTINGS ============
@admin_bp.route('/system-settings', methods=['GET', 'POST'])
@admin_required
def system_settings():
    """System settings page"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            admin = AdminUser.query.filter_by(email=current_user.email).first()
            
            if not admin.check_password(current_password):
                flash('Current password is incorrect', 'error')
            elif new_password != confirm_password:
                flash('New passwords do not match', 'error')
            elif len(new_password) < 8:
                flash('Password must be at least 8 characters', 'error')
            else:
                admin.set_password(new_password)
                db.session.commit()
                flash('Admin password updated successfully', 'success')
        
        elif action == 'clear_notifications':
            Notification.query.filter_by(user_id=current_user.id).delete()
            db.session.commit()
            flash('All notifications cleared', 'success')
        
        flash('Settings updated successfully', 'success')
        return redirect(url_for('admin.system_settings'))
    
    return render_template('admin/system_settings.html')

# ============ ADMIN PROFILE ============
@admin_bp.route('/profile', methods=['GET', 'POST'])
@admin_required
def profile():
    """Admin profile page"""
    admin = AdminUser.query.filter_by(email=current_user.email).first()
    
    if request.method == 'POST':
        admin.full_name = request.form.get('full_name')
        
        current_pw = request.form.get('current_password')
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_password')
        
        if current_pw and new_pw:
            if not admin.check_password(current_pw):
                flash('Current password is incorrect', 'error')
            elif new_pw != confirm_pw:
                flash('New passwords do not match', 'error')
            elif len(new_pw) < 8:
                flash('Password must be at least 8 characters', 'error')
            else:
                admin.set_password(new_pw)
                flash('Password updated successfully', 'success')
        
        db.session.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('admin.profile'))
    
    return render_template('admin/profile.html', admin=admin)

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import db, User, CommunityPost, CommunityReply, PostLike, ReplyMention, Notification
from datetime import datetime
import re

community_bp = Blueprint('community', __name__, url_prefix='/community')

def create_notification(user_id, title, message, notification_type='community', link=None):
    """Helper function to create notifications"""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link
    )
    db.session.add(notification)
    return notification

def extract_mentions(text):
    """Extract @mentions from text"""
    mention_pattern = r'@(\w+)'
    return re.findall(mention_pattern, text)

@community_bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', 'all')
    
    query = CommunityPost.query.filter_by(is_public=True)
    
    if category != 'all':
        query = query.filter_by(category=category)
    
    posts = query.order_by(
        CommunityPost.is_pinned.desc(),
        CommunityPost.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    categories = ['general', 'farming', 'livestock', 'crops', 'questions', 'help']
    
    return render_template('community/index.html', 
                         posts=posts, 
                         categories=categories, 
                         selected_category=category)

@community_bp.route('/post/<int:post_id>')
def view_post(post_id):
    post = CommunityPost.query.get_or_404(post_id)
    
    post.view_count += 1
    db.session.commit()
    
    replies = CommunityReply.query.filter_by(post_id=post_id)\
        .order_by(CommunityReply.is_solution.desc(), CommunityReply.created_at.asc())\
        .all()
    
    return render_template('community/view_post.html', post=post, replies=replies)

@community_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category', 'general')
        post_type = request.form.get('post_type', 'question')
        
        if not title or not content:
            flash('Title and content are required', 'error')
            return redirect(url_for('community.create_post'))
        
        post = CommunityPost(
            user_id=current_user.id,
            title=title,
            content=content,
            category=category,
            post_type=post_type
        )
        
        db.session.add(post)
        db.session.commit()
        
        flash('Post created successfully!', 'success')
        return redirect(url_for('community.view_post', post_id=post.id))
    
    return render_template('community/create_post.html')

@community_bp.route('/post/<int:post_id>/reply', methods=['POST'])
@login_required
def reply_post(post_id):
    post = CommunityPost.query.get_or_404(post_id)
    content = request.form.get('content')
    
    if not content:
        flash('Reply content is required', 'error')
        return redirect(url_for('community.view_post', post_id=post_id))
    
    reply = CommunityReply(
        post_id=post_id,
        user_id=current_user.id,
        content=content
    )
    
    db.session.add(reply)
    db.session.commit()
    
    if post.user_id != current_user.id:
        create_notification(
            user_id=post.user_id,
            title='New Reply to Your Post',
            message=f'{current_user.full_name} replied to your post: {post.title[:50]}...',
            link=f'/community/post/{post_id}#reply-{reply.id}'
        )
    
    mentions = extract_mentions(content)
    for username in mentions:
        mentioned_user = User.query.filter_by(full_name=username).first()
        if mentioned_user and mentioned_user.id != current_user.id:
            mention = ReplyMention(
                reply_id=reply.id,
                mentioned_user_id=mentioned_user.id
            )
            db.session.add(mention)
            
            create_notification(
                user_id=mentioned_user.id,
                title='You were mentioned in a reply',
                message=f'{current_user.full_name} mentioned you in a reply',
                link=f'/community/post/{post_id}#reply-{reply.id}'
            )
    
    db.session.commit()
    flash('Reply posted successfully!', 'success')
    return redirect(url_for('community.view_post', post_id=post_id))

@community_bp.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = CommunityPost.query.get_or_404(post_id)
    
    existing_like = PostLike.query.filter_by(
        post_id=post_id, 
        user_id=current_user.id
    ).first()
    
    if existing_like:
        db.session.delete(existing_like)
        liked = False
    else:
        like = PostLike(post_id=post_id, user_id=current_user.id)
        db.session.add(like)
        liked = True
        
        if post.user_id != current_user.id:
            create_notification(
                user_id=post.user_id,
                title='Your Post Got a Like!',
                message=f'{current_user.full_name} liked your post: {post.title[:50]}...',
                link=f'/community/post/{post_id}'
            )
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'liked': liked,
        'likes_count': PostLike.query.filter_by(post_id=post_id).count()
    })

@community_bp.route('/reply/<int:reply_id>/mark-solution', methods=['POST'])
@login_required
def mark_as_solution(reply_id):
    reply = CommunityReply.query.get_or_404(reply_id)
    post = CommunityPost.query.get_or_404(reply.post_id)
    
    if post.user_id != current_user.id:
        return jsonify({'error': 'Only post author can mark as solution'}), 403
    
    reply.is_solution = not reply.is_solution
    
    if reply.is_solution:
        create_notification(
            user_id=reply.user_id,
            title='Your Reply Was Marked as Solution!',
            message=f'Your reply was marked as the solution for: {post.title[:50]}...',
            link=f'/community/post/{post.id}#reply-{reply.id}'
        )
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_solution': reply.is_solution
    })

@community_bp.route('/my-posts')
@login_required
def my_posts():
    posts = CommunityPost.query.filter_by(user_id=current_user.id)\
        .order_by(CommunityPost.created_at.desc())\
        .all()
    
    return render_template('community/my_posts.html', posts=posts)

@community_bp.route('/search')
def search():
    query = request.args.get('q', '')
    
    if query:
        posts = CommunityPost.query.filter(
            (CommunityPost.title.ilike(f'%{query}%')) |
            (CommunityPost.content.ilike(f'%{query}%'))
        ).order_by(CommunityPost.created_at.desc()).all()
    else:
        posts = []
    
    return render_template('community/search.html', posts=posts, query=query)

@community_bp.route('/notifications')
@login_required
def notifications():
    user_notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()
    
    return render_template('community/notifications.html', notifications=user_notifications)

@community_bp.route('/notifications/clear', methods=['POST'])
@login_required
def clear_notifications():
    Notification.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    
    flash('All notifications cleared', 'success')
    return redirect(url_for('community.notifications'))

@community_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    
    db.session.commit()
    
    flash('All notifications marked as read', 'success')
    return redirect(url_for('community.notifications'))
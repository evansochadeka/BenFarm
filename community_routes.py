from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from extensions import db  # IMPORT shared db instance
from models import User, CommunityPost, CommunityReply, PostLike, ReplyMention, Notification
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
        
        if post.user_id

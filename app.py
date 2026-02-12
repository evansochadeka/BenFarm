import os
import json
import re
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import requests
from functools import wraps
from sqlalchemy import inspect

# ============ GLOBAL EXTENSIONS ============
db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    """Application factory - creates Flask app instance"""
    app = Flask(__name__)
    app.config.from_object('config.Config')
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    # Register blueprints
    with app.app_context():
        try:
            from admin_routes import admin_bp
            from community_routes import community_bp
            app.register_blueprint(admin_bp)
            app.register_blueprint(community_bp)
            print("✅ Blueprints registered successfully")
        except ImportError as e:
            print(f"⚠️ Blueprint import error: {e}")
    
    return app

# ============ CREATE APP INSTANCE ============
app = create_app()

# ============ IMPORT MODELS AFTER APP CREATION ============
with app.app_context():
    from models import User, AdminUser, InventoryItem, Customer, Sale, SaleItem, Communication, DiseaseReport, Notification, WeatherData, CommunityPost, PostLike, ReplyLike, ReplyMention, DirectMessage, FAQ, PostTag
    
    # ============ DATABASE AUTO-CREATION ============
    try:
        inspector = inspect(db.engine)
        if not inspector.has_table('users'):
            print("📦 Creating database tables...")
            db.create_all()
            print("✅ Database tables created successfully!")
            
            # Create default admin
            admin_email = os.environ.get('ADMIN_EMAIL', 'admin@benfarming.com')
            if not AdminUser.query.filter_by(email=admin_email).first():
                admin = AdminUser(
                    email=admin_email,
                    full_name='System Administrator',
                    is_super_admin=True,
                    role='super_admin'
                )
                admin.set_password(os.environ.get('ADMIN_PASSWORD', 'admin123'))
                db.session.add(admin)
            
            # Create superadmin
            super_admin_email = 'benedict431@gmail.com'
            if not AdminUser.query.filter_by(email=super_admin_email).first():
                super_admin = AdminUser(
                    email=super_admin_email,
                    full_name='Benedict Super Admin',
                    is_super_admin=True,
                    role='super_admin'
                )
                super_admin.set_password('28734495')
                db.session.add(super_admin)
            
            db.session.commit()
            print("✅ Admin users created!")
    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")

# ============ USER LOADER ============
@login_manager.user_loader
def load_user(user_id):
    """Load user by ID - handles both regular and admin users"""
    from models import User, AdminUser
    with app.app_context():
        user = db.session.get(User, int(user_id))
        if user:
            return user
        admin = db.session.get(AdminUser, int(user_id))
        return admin

# ============ CONFIGURE COHERE ============
COHERE_API_KEY = os.environ.get('COHERE_API_KEY', '')
COHERE_MODEL = os.environ.get('COHERE_MODEL', 'c4ai-aya-expanse-8b')

# ============ DECORATORS ============
def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login as admin first', 'error')
            return redirect(url_for('admin.login'))
        
        from models import AdminUser
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
        
        from models import AdminUser
        admin_user = AdminUser.query.filter_by(email=current_user.email).first()
        if not admin_user or not admin_user.is_super_admin:
            flash('Super admin access required', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# ============ COHERE DISEASE ANALYSIS ============
def analyze_plant_with_cohere(image_description, user_description=""):
    """Enhanced plant disease analysis with Cohere API"""
    
    default_result = {
        'plant_name': 'Unknown',
        'plant_scientific_name': 'Unknown',
        'disease_name': 'Analysis Pending',
        'disease_scientific_name': 'Unknown',
        'confidence': 'Medium',
        'symptoms': ['Unable to extract specific symptoms'],
        'cause_of_disease': 'Information not available',
        'disease_cycle': 'Information not available',
        'medications': ['Please consult with a local agricultural officer'],
        'organic_alternatives': ['Contact KALRO for organic solutions'],
        'cultural_control': ['Practice crop rotation', 'Improve air circulation'],
        'prevention_tips': ['Use disease-resistant varieties', 'Maintain field hygiene'],
        'environmental_conditions': {},
        'general_guidelines': 'Consult your local agricultural extension officer.',
        'additional_advice': 'Take clear photos of affected leaves, stems, and fruits.',
        'raw_response': ''
    }
    
    if not COHERE_API_KEY or COHERE_API_KEY == '':
        default_result['additional_advice'] = 'Cohere API key is not configured.'
        return default_result
    
    try:
        headers = {
            'Authorization': f'Bearer {COHERE_API_KEY}',
            'Content-Type': 'application/json',
        }
        
        prompt = f"""You are BenFarm, an AI agricultural assistant created by Benedict Odhiambo (Phone: +254713593573).

FARMER'S DESCRIPTION: {user_description}
IMAGE ANALYSIS: {image_description}

Identify the plant and disease based on the farmer's description FIRST.

PLANT NAME: [Common English name of the plant]
SCIENTIFIC NAME: [Scientific name of the plant]
DISEASE NAME: [Most likely disease name]
DISEASE SCIENTIFIC NAME: [Scientific name of the pathogen]
CONFIDENCE: [High/Medium/Low]

SYMPTOMS:
• [Symptom 1]
• [Symptom 2]

CAUSE OF DISEASE:
[Brief explanation]

DISEASE CYCLE:
[Brief explanation]

RECOMMENDED MEDICATIONS (Available in Kenya):
1. [Product Name] - [Manufacturer] - [Dosage]

ORGANIC ALTERNATIVES:
• [Organic solution 1]

CULTURAL CONTROL METHODS:
• [Method 1]

PREVENTION TIPS:
• [Tip 1]
• [Tip 2]

ENVIRONMENTAL CONDITIONS:
• Temperature: [Range]
• Humidity: [Risk level]

GENERAL GUIDELINES FOR KENYAN FARMERS:
[Brief advice]

ADDITIONAL ADVICE:
[Brief recommendation]"""
        
        chat_payload = {
            'model': COHERE_MODEL,
            'message': prompt,
            'temperature': 0.2,
            'max_tokens': 1000,
        }
        
        response = requests.post('https://api.cohere.ai/v1/chat', json=chat_payload, headers=headers)
        result = response.json()
        
        if response.status_code == 200 and 'text' in result:
            parsed_result = parse_cohere_analysis(result['text'])
            parsed_result['raw_response'] = result['text']
            return parsed_result
        else:
            default_result['raw_response'] = f"API Error: {result.get('message', 'Unknown error')}"
            return default_result
            
    except Exception as e:
        default_result['raw_response'] = f"Exception: {str(e)}"
        return default_result

def parse_cohere_analysis(analysis_text):
    """Parse Cohere analysis into dictionary"""
    result = {
        'plant_name': 'Unknown',
        'plant_scientific_name': 'Unknown',
        'disease_name': 'Unknown',
        'disease_scientific_name': 'Unknown',
        'confidence': 'Medium',
        'symptoms': [],
        'cause_of_disease': 'Information not available',
        'disease_cycle': 'Information not available',
        'medications': [],
        'organic_alternatives': [],
        'cultural_control': [],
        'prevention_tips': [],
        'environmental_conditions': {},
        'general_guidelines': '',
        'additional_advice': ''
    }
    
    if not analysis_text:
        return result
    
    # Extract plant name
    plant_match = re.search(r'PLANT NAME:\s*(.+?)(?:\n|$)', analysis_text, re.IGNORECASE)
    if plant_match:
        result['plant_name'] = plant_match.group(1).strip()
    
    # Extract scientific name
    sci_match = re.search(r'SCIENTIFIC NAME:\s*(.+?)(?:\n|$)', analysis_text, re.IGNORECASE)
    if sci_match:
        result['plant_scientific_name'] = sci_match.group(1).strip()
    
    # Extract disease name
    disease_match = re.search(r'DISEASE NAME:\s*(.+?)(?:\n|$)', analysis_text, re.IGNORECASE)
    if disease_match:
        result['disease_name'] = disease_match.group(1).strip()
    
    # Extract confidence
    conf_match = re.search(r'CONFIDENCE:\s*(.+?)(?:\n|$)', analysis_text, re.IGNORECASE)
    if conf_match:
        result['confidence'] = conf_match.group(1).strip()
    
    # Extract symptoms
    symptoms_section = re.search(r'SYMPTOMS?:?(.*?)(?:\n\n|\n[A-Z]|\Z)', analysis_text, re.IGNORECASE | re.DOTALL)
    if symptoms_section:
        symptoms = re.findall(r'[•\-*]\s*(.+?)(?:\n|$)', symptoms_section.group(1))
        result['symptoms'] = [s.strip() for s in symptoms if s.strip()]
    
    # Extract medications
    meds_section = re.search(r'RECOMMENDED MEDICATIONS?:?(.*?)(?:\n\n|\n[A-Z]|\Z)', analysis_text, re.IGNORECASE | re.DOTALL)
    if meds_section:
        meds = re.findall(r'\d+\.\s*(.+?)(?:\n|$)', meds_section.group(1))
        result['medications'] = [m.strip() for m in meds if m.strip()]
    
    return result

# ============ ROUTES ============

@app.route('/')
def index():
    resp = make_response(render_template('index.html'))
    if not session.get('visited'):
        session['visited'] = True
        session.permanent = True
    
    if current_user.is_authenticated:
        if hasattr(current_user, 'user_type'):
            if current_user.user_type == 'farmer':
                return redirect(url_for('farmer_dashboard'))
            elif current_user.user_type == 'agrovet':
                return redirect(url_for('agrovet_dashboard'))
            elif current_user.user_type == 'extension_officer':
                return redirect(url_for('officer_dashboard'))
            elif current_user.user_type == 'learning_institution':
                return redirect(url_for('institution_dashboard'))
    return resp

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        from models import AdminUser, User
        
        # Check admin
        admin = AdminUser.query.filter_by(email=email).first()
        if admin and admin.check_password(password):
            login_user(admin, remember=True)
            admin.last_login = datetime.utcnow()
            db.session.commit()
            flash(f'Welcome back, {admin.full_name}!', 'success')
            return redirect(url_for('admin.super_dashboard') if admin.is_super_admin else url_for('admin.dashboard'))
        
        # Check regular user
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.is_active:
                flash('Account deactivated. Contact admin.', 'error')
                return redirect(url_for('login'))
            
            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash(f'Welcome back, {user.full_name}!', 'success')
            
            if user.user_type == 'farmer':
                return redirect(url_for('farmer_dashboard'))
            elif user.user_type == 'agrovet':
                return redirect(url_for('agrovet_dashboard'))
            elif user.user_type == 'extension_officer':
                return redirect(url_for('officer_dashboard'))
            elif user.user_type == 'learning_institution':
                return redirect(url_for('institution_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        user_type = request.form.get('user_type')
        phone_number = request.form.get('phone_number')
        location = request.form.get('location')
        
        from models import User
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        
        user = User(
            email=email,
            full_name=full_name,
            user_type=user_type,
            phone_number=phone_number,
            location=location
        )
        user.set_password(password)
        
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{email}_{file.filename}")
                upload_dir = app.config.get('UPLOAD_FOLDER', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                user.profile_picture = filename
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# ============ FARMER ROUTES ============
@app.route('/farmer/dashboard')
@login_required
def farmer_dashboard():
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    from models import DiseaseReport, Notification
    
    disease_reports = DiseaseReport.query.filter_by(farmer_id=current_user.id)\
        .order_by(DiseaseReport.created_at.desc())\
        .limit(10)\
        .all()
    
    notifications = Notification.query.filter_by(
        user_id=current_user.id, 
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('farmer/dashboard.html',
                         disease_reports=disease_reports,
                         notifications=notifications)

@app.route('/farmer/detect-disease', methods=['GET', 'POST'])
@login_required
def detect_disease():
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        if 'plant_image' not in request.files:
            return jsonify({'error': 'No image provided', 'success': False}), 400
        
        file = request.files['plant_image']
        description = request.form.get('description', '').strip()
        
        if not description:
            return jsonify({'error': 'Plant description is required', 'success': False}), 400
        
        if file.filename == '':
            return jsonify({'error': 'No file selected', 'success': False}), 400
            
        if file and allowed_file(file.filename):
            try:
                from models import DiseaseReport
                
                upload_dir = app.config.get('UPLOAD_FOLDER', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                
                timestamp = datetime.utcnow().timestamp()
                filename = secure_filename(f"plant_{current_user.id}_{timestamp}_{file.filename}")
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                
                image_description = f"Plant image of {description[:50]}"
                analysis_result = analyze_plant_with_cohere(image_description, description)
                
                raw_response = analysis_result.pop('raw_response', '')
                
                report = DiseaseReport(
                    farmer_id=current_user.id,
                    plant_image=filename,
                    plant_description=description,
                    disease_detected=analysis_result.get('disease_name', 'Unknown'),
                    scientific_name=analysis_result.get('disease_scientific_name', 'Unknown'),
                    confidence=0.85 if analysis_result.get('confidence') == 'High' else 0.65,
                    treatment_recommendation='\n'.join(analysis_result.get('medications', [])),
                    medications_available=analysis_result.get('medications', []),
                    prevention_tips='\n'.join(analysis_result.get('prevention_tips', [])),
                    environmental_conditions=analysis_result.get('environmental_conditions', {}),
                    location=current_user.location,
                    status='analyzed'
                )
                db.session.add(report)
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'analysis': analysis_result,
                    'raw_response': raw_response,
                    'report_id': report.id
                })
                
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                return jsonify({'error': str(e), 'success': False}), 500
        else:
            return jsonify({'error': 'Invalid file type', 'success': False}), 400
    
    return render_template('farmer/detect_disease.html')

@app.route('/farmer/weather')
@login_required
def farmer_weather():
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    location = request.args.get('location', current_user.location or 'Nairobi')
    
    try:
        weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={app.config.get('OPENWEATHER_API_KEY')}&units=metric"
        response = requests.get(weather_url)
        weather_data = response.json()
        
        return render_template('farmer/weather.html', weather=weather_data)
    except Exception as e:
        flash(f'Error fetching weather: {str(e)}', 'error')
        return render_template('farmer/weather.html', weather=None)

@app.route('/farmer/agrovets')
@login_required
def farmer_agrovets():
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    from models import User
    
    agrovets = User.query.filter_by(
        user_type='agrovet',
        is_active=True
    ).all()
    
    return render_template('farmer/agrovets.html', agrovets=agrovets)

# ============ BENFARM CHAT API ============
@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    """BenFarm AI Chat Assistant"""
    data = request.get_json()
    message = data.get('message', '')
    
    if not message:
        return jsonify({'success': False, 'error': 'No message provided'})
    
    if not COHERE_API_KEY:
        return jsonify({
            'success': False,
            'error': 'BenFarm is offline. Contact Benedict at +254713593573'
        })
    
    try:
        headers = {
            'Authorization': f'Bearer {COHERE_API_KEY}',
            'Content-Type': 'application/json',
        }
        
        system_prompt = f"""You are BenFarm, an AI agricultural assistant created by Benedict Odhiambo (+254713593573).

Answer this farmer's question: {message}

If asked about human expert, provide: +254713593573
Keep response concise and helpful.
Use emojis occasionally.
End with "Ubarikiwe! - BenFarm 🤖" """
        
        payload = {
            'model': COHERE_MODEL,
            'message': system_prompt,
            'temperature': 0.7,
            'max_tokens': 500
        }
        
        response = requests.post('https://api.cohere.ai/v1/chat', json=payload, headers=headers)
        result = response.json()
        
        if response.status_code == 200 and 'text' in result:
            return jsonify({
                'success': True,
                'response': result['text'],
                'assistant': 'BenFarm',
                'creator': 'Benedict Odhiambo'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'BenFarm is busy. Contact Benedict at +254713593573'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'BenFarm offline. Call +254713593573'
        })

# ============ NOTIFICATIONS ============
@app.route('/notifications/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    from models import Notification
    
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'success': True})

# ============ SITEMAP & ROBOTS ============
@app.route('/sitemap.xml')
def sitemap():
    urls = []
    static_pages = ['', 'login', 'register', 'farmer/dashboard', 'farmer/detect-disease', 
                   'farmer/weather', 'farmer/agrovets']
    
    for page in static_pages:
        urls.append({
            'loc': url_for('index', _external=True) + (page if page else ''),
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': 'daily',
            'priority': '1.0' if page == '' else '0.8'
        })
    
    sitemap_xml = render_template('sitemap_template.xml', urls=urls)
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    return response

@app.route('/robots.txt')
def robots():
    robots_txt = f"""User-agent: *
Allow: /
Sitemap: {url_for('sitemap', _external=True)}
"""
    response = make_response(robots_txt)
    response.headers["Content-Type"] = "text/plain"
    return response

# ============ TEMPLATE FILTERS ============
@app.template_filter('datetime')
def format_datetime(value):
    if value is None:
        return ""
    return value.strftime('%Y-%m-%d %H:%M')

@app.template_filter('format_currency')
def format_currency(value):
    if value is None:
        return "KES 0.00"
    return f"KES {value:,.2f}"

@app.template_filter('is_admin')
def is_admin(user):
    if not user.is_authenticated:
        return False
    from models import AdminUser
    admin = AdminUser.query.filter_by(email=user.email).first()
    return admin is not None

@app.template_filter('is_super_admin')
def is_super_admin(user):
    if not user.is_authenticated:
        return False
    from models import AdminUser
    admin = AdminUser.query.filter_by(email=user.email).first()
    return admin is not None and admin.is_super_admin

@app.route('/favicon.ico')
def favicon():
    return '', 404

# ============ AGROVET ROUTES (Add these) ============
@app.route('/agrovet/dashboard')
@login_required
def agrovet_dashboard():
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    return render_template('agrovet/dashboard.html')

@app.route('/agrovet/inventory')
@login_required
def agrovet_inventory():
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    return render_template('agrovet/inventory.html')

@app.route('/agrovet/pos')
@login_required
def agrovet_pos():
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    return render_template('agrovet/pos.html')

@app.route('/agrovet/crm')
@login_required
def agrovet_crm():
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    return render_template('agrovet/crm.html')

# ============ OFFICER ROUTES ============
@app.route('/officer/dashboard')
@login_required
def officer_dashboard():
    if current_user.user_type != 'extension_officer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    return render_template('officer/dashboard.html')

# ============ INSTITUTION ROUTES ============
@app.route('/institution/dashboard')
@login_required
def institution_dashboard():
    if current_user.user_type != 'learning_institution':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    return render_template('institution/dashboard.html')

# ============ MAIN ============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

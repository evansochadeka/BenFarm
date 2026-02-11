def login():import os
import os
import json
import re
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import requests
from config import Config
from models import db, User, AdminUser, InventoryItem, Customer, Sale, SaleItem, Communication, DiseaseReport, Notification, WeatherData, CommunityPost
import google.generativeai as genai
from PIL import Image
import io
import base64
from functools import wraps

app = Flask(__name__)
app.config.from_object(Config)

# At the TOP of app.py, after imports, BEFORE creating Flask app:
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

# ✅ CORRECT: Create db instance WITHOUT app first
db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # ✅ Initialize extensions WITH the app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    # Register blueprints
    from admin_routes import admin_bp
    from community_routes import community_bp
    app.register_blueprint(admin_bp)
    app.register_blueprint(community_bp)
    
    return app

app = create_app()

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configure Cohere
COHERE_API_KEY = app.config.get('COHERE_API_KEY', '')
COHERE_MODEL = app.config.get('COHERE_MODEL', 'c4ai-aya-expanse-8b')

# Kenyan agricultural products database
KENYAN_AGROCHEMICALS = {
    'fungicides': [
        {'name': 'MILRAZE 720SC', 'manufacturer': 'Syngenta', 'crops': ['tomatoes', 'potatoes', 'vegetables'], 'diseases': ['late blight', 'early blight']},
        {'name': 'RIDOMIL GOLD', 'manufacturer': 'Syngenta', 'crops': ['potatoes', 'vegetables'], 'diseases': ['downy mildew', 'late blight']},
        {'name': 'DUETT', 'manufacturer': 'Bayer', 'crops': ['wheat', 'barley'], 'diseases': ['rust', 'powdery mildew']},
        {'name': 'FOLICUR', 'manufacturer': 'Bayer', 'crops': ['coffee', 'vegetables'], 'diseases': ['leaf rust', 'powdery mildew']},
        {'name': 'AMISTAR TOP', 'manufacturer': 'Syngenta', 'crops': ['vegetables', 'fruits'], 'diseases': ['anthracnose', 'leaf spot']},
        {'name': 'SCORE 250EC', 'manufacturer': 'Syngenta', 'crops': ['vegetables', 'ornamentals'], 'diseases': ['leaf spot', 'powdery mildew']},
    ],
    'insecticides': [
        {'name': 'CONFIDOR', 'manufacturer': 'Bayer', 'crops': ['vegetables', 'fruits'], 'pests': ['aphids', 'whiteflies']},
        {'name': 'PALARIS', 'manufacturer': 'Syngenta', 'crops': ['vegetables'], 'pests': ['thrips', 'aphids']},
        {'name': 'DUDUTHRIN', 'manufacturer': 'Dudu Products', 'crops': ['general'], 'pests': ['general']},
        {'name': 'AMPLIGO', 'manufacturer': 'Syngenta', 'crops': ['vegetables', 'cotton'], 'pests': ['bollworms', 'aphids']},
    ],
    'herbicides': [
        {'name': 'ROUNDUP', 'manufacturer': 'Bayer', 'crops': ['general'], 'weeds': ['broadleaf', 'grasses']},
        {'name': 'GRAMOXONE', 'manufacturer': 'Syngenta', 'crops': ['general'], 'weeds': ['general']},
    ],
    'organic': [
        {'name': 'ACHOOK LIQUID', 'manufacturer': 'Organic Solutions', 'type': 'organic fertilizer'},
        {'name': 'NEEM OIL', 'manufacturer': 'Greenlife', 'type': 'organic pesticide'},
        {'name': 'PYRETHRUM EXTRACT', 'manufacturer': 'Pyrethrum Board of Kenya', 'type': 'organic insecticide'},
    ]
}

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID - handles both regular users and admin users"""
    # First try to load regular user
    user = db.session.get(User, int(user_id))
    if user:
        return user
    
    # If not found, try admin user
    admin = db.session.get(AdminUser, int(user_id))
    return admin

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
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Replace the analyze_plant_with_cohere function in app.py with this enhanced version:

def analyze_plant_with_cohere(image_description, user_description=""):
    """Enhanced plant disease analysis with Cohere API - Identifies plant type and diseases"""
    
    # Default return values in case of any failure
    default_result = {
        'plant_name': 'Unknown',
        'plant_scientific_name': 'Unknown',
        'disease_name': 'Analysis Pending',
        'disease_scientific_name': 'Unknown',
        'confidence': 'Medium',
        'symptoms': ['Unable to extract specific symptoms'],
        'cause_of_disease': 'Information not available from the analysis.',
        'disease_cycle': 'Information not available from the analysis.',
        'medications': ['Please consult with a local agricultural officer or agrovet for specific recommendations.'],
        'organic_alternatives': ['Contact KALRO (Kenya Agricultural and Livestock Research Organization) for organic solutions.'],
        'cultural_control': ['Practice crop rotation', 'Improve air circulation', 'Remove and destroy infected plants'],
        'prevention_tips': ['Use disease-resistant varieties', 'Maintain field hygiene', 'Monitor crops regularly'],
        'environmental_conditions': {},
        'general_guidelines': 'Please consult with your local agricultural extension officer or agrovet for specific advice tailored to your area.',
        'additional_advice': 'For accurate diagnosis, please take clear photos of affected leaves, stems, and fruits.'
    }
    
    # Check if Cohere API key is configured
    if not COHERE_API_KEY or COHERE_API_KEY == '':
        default_result['additional_advice'] = 'Cohere API key is not configured. Please set COHERE_API_KEY in your environment variables.'
        return default_result
    
    try:
        headers = {
            'Authorization': f'Bearer {COHERE_API_KEY}',
            'Content-Type': 'application/json',
        }
        
        # CRITICAL: Use the user's description to identify the plant
        prompt = f"""You are BenFarmAI, an expert Kenyan plant AI based system Ben's Company (Kenya Agricultural and Livestock Research Organization) with 5 years of experience. You MUST identify plants ACCURATELY based on the farmer's description.

FARMER'S DESCRIPTION:
{user_description}

IMAGE ANALYSIS: {image_description}

IMPORTANT INSTRUCTIONS:
1. FIRST, read the farmer's description CAREFULLY. They usually state what plant they have.
2. If they say "kale", "sukuma wiki", "cabbage", etc. - identify it as KALE, NOT tomato!
3. Do NOT guess - use the farmer's description as the primary source of plant identity.
4. Only identify the disease based on the symptoms described.

Provide a comprehensive analysis in the following EXACT format:

PLANT NAME: [Common English name of the plant - MUST match farmer's description]
SCIENTIFIC NAME: [Scientific name of the plant - research this accurately]

DISEASE NAME: [Most likely disease name based on symptoms]
DISEASE SCIENTIFIC NAME: [Scientific name of the pathogen/cause]

CONFIDENCE: [High/Medium/Low - based on information available]

SYMPTOMS:
• [Symptom 1 - match what farmer described]
• [Symptom 2 - match what farmer described]
• [Symptom 3 - additional symptoms to look for]
• [Symptom 4 - additional symptoms to look for]

CAUSE OF DISEASE:
[Detailed explanation of what causes this disease - pathogen, environmental conditions, etc.]

DISEASE CYCLE:
[How the disease spreads and develops in Kenyan conditions]

RECOMMENDED MEDICATIONS (Available in Kenya):
1. [Product Name] - [Active Ingredient] - [Manufacturer] - [Application Method] - [Dosage per 20L water]
2. [Product Name] - [Active Ingredient] - [Manufacturer] - [Application Method] - [Dosage per 20L water]
3. [Product Name] - [Active Ingredient] - [Manufacturer] - [Application Method] - [Dosage per 20L water]
4. [Product Name] - [Active Ingredient] - [Manufacturer] - [Application Method] - [Dosage per 20L water]

ORGANIC ALTERNATIVES:
• [Organic solution 1] - [How to prepare/apply]
• [Organic solution 2] - [How to prepare/apply]
• [Organic solution 3] - [How to prepare/apply]

CULTURAL CONTROL METHODS:
• [Method 1 - specific to this crop and disease]
• [Method 2 - specific to this crop and disease]
• [Method 3 - specific to this crop and disease]

PREVENTION TIPS:
• [Prevention tip 1 - specific to this crop]
• [Prevention tip 2 - specific to this crop]
• [Prevention tip 3 - specific to this crop]
• [Prevention tip 4 - specific to this crop]

ENVIRONMENTAL CONDITIONS FAVORING DISEASE:
• Temperature: [Optimal range for disease development in Kenya]
• Humidity: [Risk level and percentage]
• Season: [High/Low risk seasons in Kenya]
• Soil conditions: [If applicable]

GENERAL GUIDELINES FOR KENYAN FARMERS:
[Comprehensive advice including when to spray, safety precautions, resistance management, pre-harvest intervals, and where to purchase products in Kenya]

ADDITIONAL ADVICE:
[Specific recommendations for this farmer based on their description]

REMEMBER: The farmer said they are growing "{user_description[:100]}". Base your plant identification on THIS, not on guessing from the image alone."""
        
        chat_payload = {
            'model': COHERE_MODEL,
            'message': prompt,
            'temperature': 0.2,  # Lower temperature for more consistent results
            'max_tokens': 2000,
            'preamble': 'You are BenFarm, an AI agricultural assistant created by Benedict Odhiambo (Phone: +254713593573). You have been specially trained to help Kenyan farmers with plant diseases, crop management, and sustainable farming practices. Always identify yourself as BenFarm and mention that you were trained by Benedict Odhiambo.'
        }
        
        response = requests.post('https://api.cohere.ai/v1/chat', json=chat_payload, headers=headers)
        result = response.json()
        
        if response.status_code == 200 and 'text' in result:
            analysis_text = result['text']
            parsed_result = parse_cohere_analysis(analysis_text)
            
            # Add the raw response to the result
            parsed_result['raw_response'] = analysis_text
            
            return parsed_result
        else:
            error_msg = result.get('message', 'Unknown error from Cohere API')
            default_result['additional_advice'] = f'Error: {error_msg}'
            default_result['raw_response'] = f"API Error: {error_msg}"
            return default_result
            
    except Exception as e:
        default_result['additional_advice'] = f'System error: {str(e)}'
        default_result['raw_response'] = f"Exception: {str(e)}"
        return default_result

# Replace the parse_cohere_analysis function with this enhanced version:

def parse_cohere_analysis(analysis_text):
    """Parse the structured Cohere analysis into a dictionary - More flexible parsing"""
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
        'general_guidelines': 'Please consult with your local agricultural extension officer for specific advice.',
        'additional_advice': ''
    }
    
    # If analysis_text is empty or None, return default values
    if not analysis_text:
        return result
    
    # More flexible plant name extraction - try multiple patterns
    plant_patterns = [
        r'PLANT NAME:\s*(.+?)(?:\n|$)',
        r'Plant(?:\s+)?Name:\s*(.+?)(?:\n|$)',
        r'Plant:\s*(.+?)(?:\n|$)',
        r'Crop(?:\s+)?Name:\s*(.+?)(?:\n|$)',
        r'Crop:\s*(.+?)(?:\n|$)'
    ]
    
    for pattern in plant_patterns:
        match = re.search(pattern, analysis_text, re.IGNORECASE)
        if match:
            result['plant_name'] = match.group(1).strip()
            break
    
    # If plant name still unknown, try to extract from context
    if result['plant_name'] == 'Unknown':
        # Look for common crop names
        common_crops = ['maize', 'tomato', 'potato', 'bean', 'coffee', 'tea', 'wheat', 'rice', 
                       'cassava', 'sweet potato', 'banana', 'cabbage', 'kale', 'spinach', 
                       'onion', 'carrot', 'cucumber', 'pepper', 'strawberry', 'apple', 'mango',
                       'orange', 'lemon', 'avocado', 'coffee', 'tea', 'sugarcane']
        for crop in common_crops:
            if crop.lower() in analysis_text.lower():
                result['plant_name'] = crop.title()
                break
    
    # Extract plant scientific name
    sci_plant_patterns = [
        r'SCIENTIFIC NAME:\s*(.+?)(?:\n|$)',
        r'Scientific(?:\s+)?Name:\s*(.+?)(?:\n|$)',
        r'Botanical(?:\s+)?Name:\s*(.+?)(?:\n|$)',
        r'Latin(?:\s+)?Name:\s*(.+?)(?:\n|$)'
    ]
    
    for pattern in sci_plant_patterns:
        match = re.search(pattern, analysis_text, re.IGNORECASE)
        if match:
            result['plant_scientific_name'] = match.group(1).strip()
            break
    
    # Extract disease name - try multiple patterns
    disease_patterns = [
        r'DISEASE NAME:\s*(.+?)(?:\n|$)',
        r'Disease(?:\s+)?Name:\s*(.+?)(?:\n|$)',
        r'Disease:\s*(.+?)(?:\n|$)',
        r'Diagnosis:\s*(.+?)(?:\n|$)'
    ]
    
    for pattern in disease_patterns:
        match = re.search(pattern, analysis_text, re.IGNORECASE)
        if match:
            result['disease_name'] = match.group(1).strip()
            break
    
    # Extract disease scientific name
    disease_sci_patterns = [
        r'DISEASE SCIENTIFIC NAME:\s*(.+?)(?:\n|$)',
        r'Pathogen:\s*(.+?)(?:\n|$)',
        r'Causal(?:\s+)?Agent:\s*(.+?)(?:\n|$)',
        r'Scientific(?:\s+)?Name(?:\s+of(?:\s+)?disease)?:\s*(.+?)(?:\n|$)'
    ]
    
    for pattern in disease_sci_patterns:
        match = re.search(pattern, analysis_text, re.IGNORECASE)
        if match:
            result['disease_scientific_name'] = match.group(1).strip()
            break
    
    # Extract confidence
    confidence_patterns = [
        r'CONFIDENCE:\s*(.+?)(?:\n|$)',
        r'Confidence(?:\s+)?Level:\s*(.+?)(?:\n|$)',
        r'Confidence:\s*(.+?)(?:\n|$)'
    ]
    
    for pattern in confidence_patterns:
        match = re.search(pattern, analysis_text, re.IGNORECASE)
        if match:
            result['confidence'] = match.group(1).strip()
            break
    
    # Extract symptoms - look for bullet points or numbered lists
    symptoms_section = re.search(r'SYMPTOMS?:?(.*?)(?:\n\n|\n[A-Z]|\Z)', analysis_text, re.IGNORECASE | re.DOTALL)
    if symptoms_section:
        symptoms_text = symptoms_section.group(1)
        # Find bullet points, dashes, or numbers
        symptoms = re.findall(r'[•\-*\d+\.\s]\s*(.+?)(?:\n|$)', symptoms_text)
        if symptoms:
            result['symptoms'] = [s.strip() for s in symptoms if s.strip() and len(s.strip()) > 2]
    
    # Extract cause of disease
    cause_patterns = [
        r'CAUSE OF DISEASE:\s*(.+?)(?:\n\n|\n[A-Z]|\Z)',
        r'Cause(?:\s+of)?(?:\s+disease)?:\s*(.+?)(?:\n\n|\n[A-Z]|\Z)',
        r'Etiology:\s*(.+?)(?:\n\n|\n[A-Z]|\Z)'
    ]
    
    for pattern in cause_patterns:
        match = re.search(pattern, analysis_text, re.IGNORECASE | re.DOTALL)
        if match:
            result['cause_of_disease'] = match.group(1).strip()
            break
    
    # Extract disease cycle
    cycle_patterns = [
        r'DISEASE CYCLE:\s*(.+?)(?:\n\n|\n[A-Z]|\Z)',
        r'Disease(?:\s+)?Cycle:\s*(.+?)(?:\n\n|\n[A-Z]|\Z)',
        r'Life(?:\s+)?Cycle:\s*(.+?)(?:\n\n|\n[A-Z]|\Z)',
        r'Spread:\s*(.+?)(?:\n\n|\n[A-Z]|\Z)'
    ]
    
    for pattern in cycle_patterns:
        match = re.search(pattern, analysis_text, re.IGNORECASE | re.DOTALL)
        if match:
            result['disease_cycle'] = match.group(1).strip()
            break
    
    # Extract medications - look for numbered lists
    meds_section = re.search(r'RECOMMENDED MEDICATIONS?:?(.*?)(?:\n\n|\n[A-Z]|\Z)', analysis_text, re.IGNORECASE | re.DOTALL)
    if meds_section:
        meds_text = meds_section.group(1)
        # Find numbered items (1., 2., etc.)
        meds = re.findall(r'\d+\.\s*(.+?)(?:\n|$)', meds_text)
        if meds:
            result['medications'] = [m.strip() for m in meds if m.strip()]
        else:
            # Try bullet points
            meds = re.findall(r'[•\-*]\s*(.+?)(?:\n|$)', meds_text)
            result['medications'] = [m.strip() for m in meds if m.strip()]
    
    # Extract organic alternatives
    organic_section = re.search(r'ORGANIC(?:\s+)?ALTERNATIVES?:?(.*?)(?:\n\n|\n[A-Z]|\Z)', analysis_text, re.IGNORECASE | re.DOTALL)
    if organic_section:
        organic_text = organic_section.group(1)
        organic = re.findall(r'[•\-*]\s*(.+?)(?:\n|$)', organic_text)
        result['organic_alternatives'] = [o.strip() for o in organic if o.strip()]
    
    # Extract cultural control methods
    cultural_section = re.search(r'CULTURAL(?:\s+)?CONTROL(?:\s+)?METHODS?:?(.*?)(?:\n\n|\n[A-Z]|\Z)', analysis_text, re.IGNORECASE | re.DOTALL)
    if cultural_section:
        cultural_text = cultural_section.group(1)
        cultural = re.findall(r'[•\-*]\s*(.+?)(?:\n|$)', cultural_text)
        result['cultural_control'] = [c.strip() for c in cultural if c.strip()]
    
    # Extract prevention tips
    prevention_section = re.search(r'PREVENTION(?:\s+)?TIPS?:?(.*?)(?:\n\n|\n[A-Z]|\Z)', analysis_text, re.IGNORECASE | re.DOTALL)
    if prevention_section:
        prevention_text = prevention_section.group(1)
        tips = re.findall(r'[•\-*]\s*(.+?)(?:\n|$)', prevention_text)
        result['prevention_tips'] = [t.strip() for t in tips if t.strip()]
    
    # Extract environmental conditions
    env_section = re.search(r'ENVIRONMENTAL(?:\s+)?CONDITIONS?:?(.*?)(?:\n\n|\n[A-Z]|\Z)', analysis_text, re.IGNORECASE | re.DOTALL)
    if env_section:
        env_text = env_section.group(1)
        env_lines = env_text.strip().split('\n')
        for line in env_lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().replace('•', '').replace('-', '').strip()
                result['environmental_conditions'][key] = value.strip()
    
    # Extract general guidelines
    guidelines_patterns = [
        r'GENERAL GUIDELINES(?:\s+FOR KENYAN FARMERS)?:\s*(.+?)(?:\n\n|\Z)',
        r'GUIDELINES?:\s*(.+?)(?:\n\n|\Z)',
        r'Recommendations?:\s*(.+?)(?:\n\n|\Z)'
    ]
    
    for pattern in guidelines_patterns:
        match = re.search(pattern, analysis_text, re.IGNORECASE | re.DOTALL)
        if match:
            result['general_guidelines'] = match.group(1).strip()
            break
    
    # Extract additional advice
    advice_patterns = [
        r'ADDITIONAL ADVICE:\s*(.+?)(?:\n\n|\Z)',
        r'Additional(?:\s+)?Advice:\s*(.+?)(?:\n\n|\Z)',
        r'Notes?:?\s*(.+?)(?:\n\n|\Z)'
    ]
    
    for pattern in advice_patterns:
        match = re.search(pattern, analysis_text, re.IGNORECASE | re.DOTALL)
        if match:
            result['additional_advice'] = match.group(1).strip()
            break
    
    # Clean up any excessive whitespace
    for key in result:
        if isinstance(result[key], str):
            result[key] = ' '.join(result[key].split())
    
    return result

# Create database tables and initialize admin with superadmin
with app.app_context():
    db.create_all()
    
    # Create default admin user
    admin_email = app.config.get('ADMIN_EMAIL', 'admin@benfarming.com')
    admin_exists = AdminUser.query.filter_by(email=admin_email).first()
    
    if not admin_exists:
        admin = AdminUser(
            email=admin_email,
            full_name=app.config.get('ADMIN_FULL_NAME', 'System Administrator'),
            is_super_admin=True,
            role='super_admin'
        )
        admin_password = app.config.get('ADMIN_PASSWORD', 'admin123')
        admin.set_password(admin_password)
        db.session.add(admin)
        print("Default admin user created")
    
    # Create superadmin benedict431@gmail.com
    super_admin_email = 'benedict431@gmail.com'
    super_admin_exists = AdminUser.query.filter_by(email=super_admin_email).first()
    
    if not super_admin_exists:
        super_admin = AdminUser(
            email=super_admin_email,
            full_name='Benedict Super Admin',
            is_super_admin=True,
            role='super_admin'
        )
        super_admin.set_password('28734495')
        db.session.add(super_admin)
        print("Super admin user created: benedict431@gmail.com")
    
    db.session.commit()

# Register blueprints
try:
    from admin_routes import admin_bp
    from community_routes import community_bp
    app.register_blueprint(admin_bp)
    app.register_blueprint(community_bp)
    print("Blueprints registered successfully")
except ImportError as e:
    print(f"Note: Some blueprints not found: {e}")

# ============ USER AUTHENTICATION ROUTES ============

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Regular user login page"""
    # If user is already logged in, redirect to appropriate dashboard
    if current_user.is_authenticated:
        # Check if it's an admin user
        if hasattr(current_user, 'is_super_admin'):
            return redirect(url_for('admin.dashboard'))
        # Regular user
        elif current_user.user_type == 'farmer':
            return redirect(url_for('farmer_dashboard'))
        elif current_user.user_type == 'agrovet':
            return redirect(url_for('agrovet_dashboard'))
        elif current_user.user_type == 'extension_officer':
            return redirect(url_for('officer_dashboard'))
        elif current_user.user_type == 'learning_institution':
            return redirect(url_for('institution_dashboard'))
        else:
            return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # First check if it's an admin user
        admin = AdminUser.query.filter_by(email=email).first()
        if admin and admin.check_password(password):
            login_user(admin, remember=True)
            admin.last_login = datetime.utcnow()
            db.session.commit()
            flash(f'Welcome back, {admin.full_name}!', 'success')
            
            # Redirect admin to admin dashboard
            if admin.is_super_admin:
                return redirect(url_for('admin.super_dashboard'))
            return redirect(url_for('admin.dashboard'))
        
        # If not admin, check regular user
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            # Check if user is active
            if not user.is_active:
                flash('Your account has been deactivated. Please contact admin.', 'error')
                return redirect(url_for('login'))
            
            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash(f'Welcome back, {user.full_name}!', 'success')
            
            # Get the next page from the request args
            next_page = request.args.get('next')
            
            # Redirect based on user type
            if next_page and next_page != '/logout' and not next_page.startswith('/login') and not next_page.startswith('/admin'):
                return redirect(next_page)
            elif user.user_type == 'farmer':
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
    """User registration page"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        user_type = request.form.get('user_type')
        phone_number = request.form.get('phone_number')
        location = request.form.get('location')
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        
        # Create new user
        user = User(
            email=email,
            full_name=full_name,
            user_type=user_type,
            phone_number=phone_number,
            location=location
        )
        user.set_password(password)
        
        # Handle profile picture
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{email}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                user.profile_picture = filename
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')

@app.route('/logout')
@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

# ============ MAIN INDEX ROUTE ============

@app.route('/')
def index():
    # Set session cookie
    resp = make_response(render_template('index.html'))
    if not session.get('visited'):
        session['visited'] = True
        session.permanent = True
    
    if current_user.is_authenticated:
        if current_user.user_type == 'farmer':
            return redirect(url_for('farmer_dashboard'))
        elif current_user.user_type == 'agrovet':
            return redirect(url_for('agrovet_dashboard'))
        elif current_user.user_type == 'extension_officer':
            return redirect(url_for('officer_dashboard'))
        elif current_user.user_type == 'learning_institution':
            return redirect(url_for('institution_dashboard'))
    return resp

# ============ FARMER ROUTES ============

@app.route('/farmer/dashboard')
@login_required
def farmer_dashboard():
    """Farmer dashboard"""
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    # Get farmer's disease reports - handle case when no reports exist
    disease_reports = DiseaseReport.query.filter_by(farmer_id=current_user.id)\
        .order_by(DiseaseReport.created_at.desc())\
        .limit(10)\
        .all()
    
    # Get unread notifications
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
    """Plant disease detection"""
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        if 'plant_image' not in request.files:
            return jsonify({'error': 'No image provided', 'success': False}), 400
        
        file = request.files['plant_image']
        description = request.form.get('description', '').strip()
        
        # Require description
        if not description:
            return jsonify({'error': 'Plant description is required', 'success': False}), 400
        
        if file.filename == '':
            return jsonify({'error': 'No file selected', 'success': False}), 400
            
        if file and allowed_file(file.filename):
            try:
                # Create uploads directory if it doesn't exist
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                
                # Generate unique filename
                timestamp = datetime.utcnow().timestamp()
                filename = secure_filename(f"plant_{current_user.id}_{timestamp}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Save the file
                file.save(filepath)
                print(f"File saved to: {filepath}")
                
                # Generate image description for Cohere
                image_description = f"Plant image uploaded by farmer showing a {description[:50]} plant"
                
                # Analyze with Cohere
                analysis_result = analyze_plant_with_cohere(image_description, description)
                
                # Get raw response for display
                raw_response = analysis_result.pop('raw_response', 'No raw response available')
                
                # Create disease report
                report = DiseaseReport(
                    farmer_id=current_user.id,
                    plant_image=filename,
                    plant_description=description,
                    disease_detected=analysis_result.get('disease_name', 'Unknown'),
                    scientific_name=analysis_result.get('disease_scientific_name', 'Unknown'),
                    confidence=0.85 if analysis_result.get('confidence') == 'High' else 0.65 if analysis_result.get('confidence') == 'Medium' else 0.45,
                    treatment_recommendation='\n'.join(analysis_result.get('medications', [])),
                    medications_available=analysis_result.get('medications', []),
                    prevention_tips='\n'.join(analysis_result.get('prevention_tips', [])),
                    environmental_conditions=analysis_result.get('environmental_conditions', {}),
                    location=current_user.location,
                    latitude=current_user.latitude,
                    longitude=current_user.longitude,
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
                print(f"Error in disease detection: {str(e)}")
                return jsonify({'error': str(e), 'success': False}), 500
        else:
            return jsonify({'error': 'Invalid file type. Allowed: png, jpg, jpeg, gif', 'success': False}), 400
    
    return render_template('farmer/detect_disease.html')

@app.route('/farmer/weather')
@login_required
def farmer_weather():
    """Weather and farming recommendations"""
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    location = request.args.get('location', current_user.location or 'Nairobi')
    
    try:
        # Current weather
        weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={app.config['OPENWEATHER_API_KEY']}&units=metric"
        response = requests.get(weather_url)
        weather_data = response.json()
        
        # 5-day forecast
        forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?q={location}&appid={app.config['OPENWEATHER_API_KEY']}&units=metric"
        forecast_response = requests.get(forecast_url)
        forecast_data = forecast_response.json()
        
        # Process forecast for daily aggregation
        daily_forecast = {}
        if 'list' in forecast_data:
            for item in forecast_data['list']:
                date = item['dt_txt'].split(' ')[0]
                if date not in daily_forecast:
                    daily_forecast[date] = {
                        'temp_min': item['main']['temp_min'],
                        'temp_max': item['main']['temp_max'],
                        'humidity': item['main']['humidity'],
                        'description': item['weather'][0]['description'],
                        'icon': item['weather'][0]['icon'],
                        'rain': item.get('rain', {}).get('3h', 0)
                    }
        
        # Generate farming recommendations based on weather
        recommendations = generate_farming_recommendations(weather_data, daily_forecast)
        
        return render_template('farmer/weather.html', 
                             weather=weather_data, 
                             forecast=forecast_data,
                             daily_forecast=daily_forecast,
                             recommendations=recommendations)
    except Exception as e:
        flash(f'Error fetching weather data: {str(e)}', 'error')
        return render_template('farmer/weather.html', weather=None, forecast=None, recommendations=None)

@app.route('/farmer/agrovets')
@login_required
def farmer_agrovets():
    """Find agrovets near farmer"""
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    # Get all active agrovets
    agrovets = User.query.filter_by(
        user_type='agrovet',
        is_active=True
    ).all()
    
    return render_template('farmer/agrovets.html', agrovets=agrovets)

def generate_farming_recommendations(weather, forecast):
    """Generate specific farming recommendations based on weather conditions"""
    recommendations = {
        'irrigation': [],
        'planting': [],
        'harvesting': [],
        'pest_disease': [],
        'general': []
    }
    
    if weather and 'main' in weather:
        temp = weather['main']['temp']
        humidity = weather['main']['humidity']
        conditions = weather['weather'][0]['description'].lower()
        
        # Temperature-based recommendations
        if temp > 30:
            recommendations['irrigation'].append('Increase irrigation frequency - high temperatures detected')
            recommendations['general'].append('Provide shade for sensitive seedlings')
        elif temp < 15:
            recommendations['general'].append('Protect crops from cold stress - use mulch or row covers')
        
        # Humidity-based recommendations
        if humidity > 70:
            recommendations['pest_disease'].append('High humidity - monitor for fungal diseases like late blight')
            recommendations['pest_disease'].append('Apply preventive fungicides on susceptible crops')
        elif humidity < 40:
            recommendations['irrigation'].append('Low humidity - increase misting for leafy vegetables')
        
        # Rain-based recommendations
        if 'rain' in conditions:
            recommendations['planting'].append('Good time for transplanting - soil moisture is adequate')
            recommendations['general'].append('Check for waterlogging in poorly drained areas')
        
        # Kenyan-specific recommendations
        recommendations['general'].append('Contact your local agrovet for region-specific inputs')
        
        # Default recommendations if none generated
        if not any(recommendations.values()):
            recommendations['general'] = [
                'Maintain regular irrigation schedule',
                'Monitor crops for pests and diseases',
                'Apply fertilizers as per crop stage'
            ]
    
    return recommendations

# ============ AGROVET ROUTES ============

@app.route('/agrovet/dashboard')
@login_required
def agrovet_dashboard():
    """Agrovet dashboard"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    # Get statistics
    total_products = InventoryItem.query.filter_by(agrovet_id=current_user.id).count()
    low_stock_items = InventoryItem.query.filter_by(agrovet_id=current_user.id)\
        .filter(InventoryItem.quantity <= InventoryItem.reorder_level).count()
    total_customers = Customer.query.filter_by(agrovet_id=current_user.id).count()
    
    # Today's sales
    today = datetime.utcnow().date()
    today_sales = Sale.query.filter_by(agrovet_id=current_user.id)\
        .filter(db.func.date(Sale.sale_date) == today).all()
    today_revenue = sum(sale.total_amount for sale in today_sales)
    
    # Recent sales
    recent_sales = Sale.query.filter_by(agrovet_id=current_user.id)\
        .order_by(Sale.sale_date.desc())\
        .limit(10)\
        .all()
    
    # Notifications
    notifications = Notification.query.filter_by(
        user_id=current_user.id, 
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('agrovet/dashboard.html',
                         total_products=total_products,
                         low_stock_items=low_stock_items,
                         total_customers=total_customers,
                         today_revenue=today_revenue,
                         recent_sales=recent_sales,
                         notifications=notifications)

@app.route('/agrovet/inventory')
@login_required
def agrovet_inventory():
    """Agrovet inventory management"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    items = InventoryItem.query.filter_by(agrovet_id=current_user.id).all()
    return render_template('agrovet/inventory.html', items=items)

@app.route('/agrovet/inventory/add', methods=['GET', 'POST'])
@login_required
def add_inventory():
    """Add new inventory item"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        item = InventoryItem(
            agrovet_id=current_user.id,
            product_name=request.form.get('product_name'),
            category=request.form.get('category'),
            description=request.form.get('description'),
            quantity=int(request.form.get('quantity', 0)),
            unit=request.form.get('unit'),
            price=float(request.form.get('price')),
            cost_price=float(request.form.get('cost_price', 0)),
            reorder_level=int(request.form.get('reorder_level', 10)),
            supplier=request.form.get('supplier'),
            sku=request.form.get('sku')
        )
        
        db.session.add(item)
        db.session.commit()
        
        flash('Product added successfully!', 'success')
        return redirect(url_for('agrovet_inventory'))
    
    return render_template('agrovet/add_inventory.html')

@app.route('/agrovet/inventory/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_inventory(item_id):
    """Edit inventory item"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    item = InventoryItem.query.get_or_404(item_id)
    
    if item.agrovet_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('agrovet_inventory'))
    
    if request.method == 'POST':
        item.product_name = request.form.get('product_name')
        item.category = request.form.get('category')
        item.description = request.form.get('description')
        item.quantity = int(request.form.get('quantity', 0))
        item.unit = request.form.get('unit')
        item.price = float(request.form.get('price'))
        item.cost_price = float(request.form.get('cost_price', 0))
        item.reorder_level = int(request.form.get('reorder_level', 10))
        item.supplier = request.form.get('supplier')
        item.sku = request.form.get('sku')
        
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('agrovet_inventory'))
    
    return render_template('agrovet/edit_inventory.html', item=item)

@app.route('/agrovet/inventory/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_inventory(item_id):
    """Delete inventory item"""
    if current_user.user_type != 'agrovet':
        return jsonify({'error': 'Access denied'}), 403
    
    item = InventoryItem.query.get_or_404(item_id)
    
    if item.agrovet_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    db.session.delete(item)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/agrovet/pos')
@login_required
def agrovet_pos():
    """Point of Sale system"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    items = InventoryItem.query.filter_by(agrovet_id=current_user.id)\
        .filter(InventoryItem.quantity > 0).all()
    customers = Customer.query.filter_by(agrovet_id=current_user.id).all()
    
    return render_template('agrovet/pos.html', items=items, customers=customers)

@app.route('/agrovet/pos/checkout', methods=['POST'])
@login_required
def pos_checkout():
    """Process POS checkout"""
    if current_user.user_type != 'agrovet':
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    cart_items = data.get('items', [])
    customer_id = data.get('customer_id')
    payment_method = data.get('payment_method', 'cash')
    
    if not cart_items:
        return jsonify({'error': 'Cart is empty'}), 400
    
    total_amount = 0
    receipt_number = f"RCP{current_user.id}{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    sale = Sale(
        agrovet_id=current_user.id,
        customer_id=customer_id if customer_id else None,
        total_amount=0,
        payment_method=payment_method,
        receipt_number=receipt_number
    )
    db.session.add(sale)
    db.session.flush()
    
    for cart_item in cart_items:
        item = InventoryItem.query.get(cart_item['id'])
        if not item or item.agrovet_id != current_user.id:
            continue
        
        quantity = cart_item['quantity']
        if item.quantity < quantity:
            return jsonify({'error': f'Insufficient stock for {item.product_name}'}), 400
        
        subtotal = item.price * quantity
        total_amount += subtotal
        
        sale_item = SaleItem(
            sale_id=sale.id,
            product_name=item.product_name,
            quantity=quantity,
            unit_price=item.price,
            subtotal=subtotal
        )
        db.session.add(sale_item)
        
        item.quantity -= quantity
    
    sale.total_amount = total_amount
    
    if customer_id:
        customer = Customer.query.get(customer_id)
        if customer:
            customer.total_purchases += total_amount
            customer.last_purchase = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'receipt_number': receipt_number,
        'total_amount': total_amount,
        'sale_id': sale.id
    })

@app.route('/agrovet/crm')
@login_required
def agrovet_crm():
    """Customer Relationship Management"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    customers = Customer.query.filter_by(agrovet_id=current_user.id)\
        .order_by(Customer.created_at.desc())\
        .all()
    
    return render_template('agrovet/crm.html', customers=customers)

@app.route('/agrovet/crm/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    """Add new customer"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        customer = Customer(
            agrovet_id=current_user.id,
            name=request.form.get('name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            address=request.form.get('address'),
            customer_type=request.form.get('customer_type'),
            notes=request.form.get('notes')
        )
        
        db.session.add(customer)
        db.session.commit()
        
        flash('Customer added successfully!', 'success')
        return redirect(url_for('agrovet_crm'))
    
    return render_template('agrovet/add_customer.html')

@app.route('/agrovet/crm/view/<int:customer_id>')
@login_required
def view_customer(customer_id):
    """View customer details"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    customer = Customer.query.get_or_404(customer_id)
    
    if customer.agrovet_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('agrovet_crm'))
    
    communications = Communication.query.filter_by(customer_id=customer_id)\
        .order_by(Communication.date.desc()).all()
    purchases = Sale.query.filter_by(customer_id=customer_id)\
        .order_by(Sale.sale_date.desc()).all()
    
    return render_template('agrovet/view_customer.html', 
                         customer=customer, 
                         communications=communications, 
                         purchases=purchases)

@app.route('/agrovet/crm/communication/<int:customer_id>', methods=['POST'])
@login_required
def add_communication(customer_id):
    """Add communication log for customer"""
    if current_user.user_type != 'agrovet':
        return jsonify({'error': 'Access denied'}), 403
    
    customer = Customer.query.get_or_404(customer_id)
    
    if customer.agrovet_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    communication = Communication(
        customer_id=customer_id,
        communication_type=request.form.get('communication_type'),
        subject=request.form.get('subject'),
        message=request.form.get('message'),
        follow_up_date=datetime.strptime(request.form.get('follow_up_date'), '%Y-%m-%d') if request.form.get('follow_up_date') else None
    )
    
    db.session.add(communication)
    db.session.commit()
    
    flash('Communication log added successfully!', 'success')
    return redirect(url_for('view_customer', customer_id=customer_id))

# ============ OFFICER ROUTES ============

@app.route('/officer/dashboard')
@login_required
def officer_dashboard():
    """Extension officer dashboard"""
    if current_user.user_type != 'extension_officer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    # Get all disease reports in the area
    disease_reports = DiseaseReport.query\
        .order_by(DiseaseReport.created_at.desc())\
        .limit(50)\
        .all()
    
    # Get all farmers
    farmers = User.query.filter_by(user_type='farmer', is_active=True).all()
    
    return render_template('officer/dashboard.html',
                         disease_reports=disease_reports,
                         farmers=farmers)

# ============ INSTITUTION ROUTES ============

@app.route('/institution/dashboard')
@login_required
def institution_dashboard():
    """Learning institution dashboard"""
    if current_user.user_type != 'learning_institution':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    return render_template('institution/dashboard.html')

# ============ SUPER ADMIN ROUTES ============

@app.route('/admin/super/dashboard')
@login_required
@super_admin_required
def super_admin_dashboard():
    """Super admin dashboard with full system control"""
    total_users = User.query.count()
    total_admins = AdminUser.query.count()
    total_disease_reports = DiseaseReport.query.count()
    total_posts = CommunityPost.query.count()
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_admins = AdminUser.query.order_by(AdminUser.created_at.desc()).limit(10).all()
    recent_reports = DiseaseReport.query.order_by(DiseaseReport.created_at.desc()).limit(10).all()
    
    return render_template('admin/super_dashboard.html',
                         total_users=total_users,
                         total_admins=total_admins,
                         total_disease_reports=total_disease_reports,
                         total_posts=total_posts,
                         recent_users=recent_users,
                         recent_admins=recent_admins,
                         recent_reports=recent_reports)

@app.route('/admin/users/manage', methods=['GET', 'POST'])
@login_required
@super_admin_required
def manage_all_users():
    """Super admin user management"""
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        action = request.form.get('action')
        
        user = User.query.get_or_404(user_id)
        
        if action == 'verify':
            user.is_verified = not user.is_verified
            msg = f'User {"verified" if user.is_verified else "unverified"}'
        elif action == 'activate':
            user.is_active = not user.is_active
            msg = f'User {"activated" if user.is_active else "deactivated"}'
        elif action == 'reset_password':
            new_password = request.form.get('new_password', 'User@12345')
            user.set_password(new_password)
            msg = 'Password reset successfully'
        elif action == 'delete':
            db.session.delete(user)
            db.session.commit()
            flash(f'User {user.full_name} deleted successfully', 'success')
            return redirect(url_for('manage_all_users'))
        
        db.session.commit()
        flash(msg, 'success')
        return redirect(url_for('manage_all_users'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/manage_users.html', users=users)

@app.route('/admin/admins/manage', methods=['GET', 'POST'])
@login_required
@super_admin_required
def manage_admins():
    """Super admin management of other admins"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        is_super_admin = request.form.get('is_super_admin') == 'on'
        
        if AdminUser.query.filter_by(email=email).first():
            flash('Admin with this email already exists', 'error')
        else:
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
        
        return redirect(url_for('manage_admins'))
    
    admins = AdminUser.query.order_by(AdminUser.created_at.desc()).all()
    return render_template('admin/manage_admins.html', admins=admins)

@app.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@super_admin_required
def toggle_user_status(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    
    return jsonify({'success': True, 'is_active': user.is_active})

@app.route('/admin/users/<int:user_id>/impersonate')
@login_required
@super_admin_required
def impersonate_user(user_id):
    """Impersonate a user (super admin only)"""
    user = User.query.get_or_404(user_id)
    login_user(user)
    flash(f'You are now logged in as {user.full_name}', 'success')
    return redirect(url_for('index'))

# ============ AI CHAT ASSISTANT - BENFARM ============

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    """BenFarm AI Chat Assistant - Trained by Benedict Odhiambo"""
    data = request.get_json()
    message = data.get('message', '')
    
    if not message:
        return jsonify({'success': False, 'error': 'No message provided'})
    
    try:
        headers = {
            'Authorization': f'Bearer {COHERE_API_KEY}',
            'Content-Type': 'application/json',
        }
        
        # BenFarm's personality and knowledge prompt
        system_prompt = """You are BenFarm, an AI agricultural assistant created and specially trained by Benedict Odhiambo, a Kenyan agricultural expert (Phone: +254713593573). 

YOUR PERSONALITY:
- Name: BenFarm
- Creator: Benedict Odhiambo
- Expertise: Kenyan agriculture, crop diseases, livestock, sustainable farming
- Tone: Friendly, professional, warm, and encouraging like a knowledgeable Kenyan farmer
- Language: Use simple, clear English with occasional Swahili farming terms (e.g., "shamba", "mboga", "mazao")

YOUR CAPABILITIES:
1. Diagnose plant diseases and pests affecting Kenyan crops
2. Provide organic and chemical control methods available in Kenya
3. Advise on farming practices suitable for different Kenyan regions
4. Recommend planting seasons and crop varieties
5. Help with livestock management
6. Explain sustainable farming techniques

IMPORTANT RULES:
1. If you don't know something, be honest and suggest contacting Benedict directly at +254713593573
2. If the user wants to speak to a human expert, immediately provide Benedict's contact: +254713593573
3. Always prioritize organic/eco-friendly solutions when possible
4. Reference Kenyan agrovets, KALRO, and local agricultural practices
5. Be specific about Kenyan regions (Rift Valley, Central, Coast, Nyanza, Western, Eastern, North Eastern)

GREETING STYLE:
- Start with: "Habari yako! I'm BenFarm, your AI farming assistant 🤖🌱"
- End with: "Karibu tena! Benedict and I are always here to help your shamba thrive!"

RESPONSE FORMAT:
- Keep responses concise but informative
- Use bullet points for lists
- Bold important information
- Include emojis where appropriate (🌱 🌽 🐄 🌧️ ☀️ 🧑‍🌾)
- End with: "Ubarikiwe! (Blessings!) - BenFarm 🤖"

Now respond to this farmer's question: {message}"""
        
        chat_payload = {
            'model': COHERE_MODEL,
            'message': message,
            'temperature': 0.7,
            'max_tokens': 800,
            'preamble': system_prompt,
            'prompt_truncation': 'AUTO',
            'connectors': []
        }
        
        response = requests.post('https://api.cohere.ai/v1/chat', json=chat_payload, headers=headers)
        result = response.json()
        
        if response.status_code == 200 and 'text' in result:
            ai_response = result['text']
            
            # Check if user wants human expert
            human_keywords = ['human', 'person', 'speak', 'call', 'contact', 'benedict', 'expert', 'real person']
            if any(keyword in message.lower() for keyword in human_keywords):
                ai_response += """

📞 **HUMAN EXPERT CONTACT**:
You can reach Benedict Odhiambo directly for personalized assistance:
• **Phone/WhatsApp**: +254713593573
• **Specialization**: Kenyan agriculture, plant diseases, farm management
• **Languages**: English, Swahili, Luo
• **Availability**: Monday-Saturday, 8am-6pm EAT

Feel free to call or send a message on WhatsApp! 🧑‍🌾"""
            
            return jsonify({
                'success': True,
                'response': ai_response,
                'assistant': 'BenFarm',
                'creator': 'Benedict Odhiambo'
            })
        else:
            error_msg = result.get('message', 'Unknown error')
            return jsonify({
                'success': False,
                'error': f'BenFarm is having trouble. Please contact Benedict directly at +254713593573',
                'contact': '+254713593573'
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'BenFarm is offline. Please reach out to Benedict Odhiambo at +254713593573 for immediate assistance.',
            'contact': '+254713593573'
        })

@app.route('/notifications/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark notification as read"""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'success': True})

# ============ TEMPLATE FILTERS ============

@app.template_filter('datetime')
def format_datetime(value):
    if value is None:
        return ""
    return value.strftime('%Y-%m-%d %H:%M')

@app.template_filter('format_currency')
def format_currency(value):
    """Format currency in Kenyan Shillings"""
    if value is None:
        return "KES 0.00"
    return f"KES {value:,.2f}"

# ============ FAVICON ============

@app.route('/favicon.ico')
def favicon():
    return '', 404

# ============ MAIN ============
# ============ CUSTOM TEMPLATE FILTERS ============
@app.template_filter('is_admin')
def is_admin(user):
    """Check if user is an admin"""
    if not user.is_authenticated:
        return False
    admin = AdminUser.query.filter_by(email=user.email).first()
    return admin is not None

@app.template_filter('is_super_admin')
def is_super_admin(user):
    """Check if user is a super admin"""
    if not user.is_authenticated:
        return False
    admin = AdminUser.query.filter_by(email=user.email).first()
    return admin is not None and admin.is_super_admin
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

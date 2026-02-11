# fix_all.py
import os
import shutil
from PIL import Image, ImageDraw

print("🔧 Fixing all remaining issues...\n")

# 1. Create all necessary directories
directories = [
    'static/uploads',
    'uploads',
    'instance',
    'templates/admin',
    'templates/auth',
    'templates/farmer',
    'templates/agrovet',
    'templates/officer',
    'templates/institution',
    'templates/community',
    'templates/components'
]

for directory in directories:
    os.makedirs(directory, exist_ok=True)
    print(f"✅ Created directory: {directory}")

# 2. Create default avatar
avatar_paths = [
    'static/uploads/default_avatar.png',
    'uploads/default_avatar.png'
]

for avatar_path in avatar_paths:
    img = Image.new('RGB', (200, 200), color=(40, 167, 69))
    draw = ImageDraw.Draw(img)
    # Draw circle background
    draw.ellipse((25, 25, 175, 175), fill=(255, 255, 255))
    # Draw user icon
    draw.ellipse((75, 60, 125, 110), fill=(40, 167, 69))  # head
    draw.rectangle((70, 115, 130, 160), fill=(40, 167, 69))  # body
    img.save(avatar_path)
    print(f"✅ Created default avatar: {avatar_path}")

# 3. Create .env file if it doesn't exist
if not os.path.exists('.env'):
    with open('.env', 'w') as f:
        f.write("""# Flask Configuration
SECRET_KEY=your-secret-key-here-change-in-production
FLASK_DEBUG=False

# Admin Credentials
ADMIN_EMAIL=admin@benfarming.com
ADMIN_PASSWORD=admin123

# API Keys (Add your keys here)
COHERE_API_KEY=your-cohere-api-key-here
OPENWEATHER_API_KEY=your-openweather-api-key-here

# Database
DATABASE_URL=sqlite:///app.db
""")
    print("✅ Created .env file")
else:
    print("⏩ .env file already exists")

# 4. Create a test user for debugging (optional)
print("\n📝 Next steps:")
print("1. Add your Cohere API key to the .env file")
print("2. Add your OpenWeather API key to the .env file")
print("3. Run: python app.py")
print("\n✨ All fixes applied successfully!")
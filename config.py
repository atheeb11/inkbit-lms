import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'inkbit-dev-secret-key-9283109312'
    
    # Database Configuration (Defaults to local MySQL, reads from environment variables)
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'root'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or 'your-mysql-password'
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
    MYSQL_PORT = os.environ.get('MYSQL_PORT') or '3306'
    MYSQL_DB = os.environ.get('MYSQL_DB') or 'inkbit'

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "isolation_level": "READ COMMITTED"
    }
    
    # File Uploads
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max file size
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'pptx', 'txt', 'zip', 'png', 'jpg', 'jpeg', 'mp4'}
    
    # Telegram Bot Support Integration
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'your-telegram-bot-token'
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID') or None

    # Email Configuration (SMTP or Resend API)
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY') or 'your-resend-api-key'
    BREVO_API_KEY = os.environ.get('BREVO_API_KEY') or 'your-brevo-api-key'
    
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 465)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') or 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'your-email@example.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'your-mail-password'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'your-email@example.com'

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID') or 'your-google-client-id'
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET') or 'your-google-client-secret'
    
    # Microsoft OAuth Configuration
    MICROSOFT_CLIENT_ID = os.environ.get('MICROSOFT_CLIENT_ID') or 'your-microsoft-client-id'
    MICROSOFT_CLIENT_SECRET = os.environ.get('MICROSOFT_CLIENT_SECRET') or 'your-microsoft-client-secret'

    # Gemini API Configuration
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') or None




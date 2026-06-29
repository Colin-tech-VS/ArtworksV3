import os
basedir = os.path.abspath(os.path.dirname(__file__))

_env_path = os.path.join(basedir, '.env')
try:
    from dotenv import load_dotenv
    load_dotenv(_env_path, override=False)
except ImportError:
    if os.path.isfile(_env_path):
        with open(_env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _env_first(*keys, default=''):
    for k in keys:
        v = os.environ.get(k, '')
        if v:
            return v.strip().strip('"').strip("'")
    return default


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-this'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB

    MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY', '')
    MISTRAL_MODEL = os.environ.get('MISTRAL_MODEL', 'mistral-small-latest')
    MISTRAL_MODEL_HEAVY = os.environ.get('MISTRAL_MODEL_HEAVY', 'mistral-large-latest')
    AI_PRIMARY = os.environ.get('AI_PRIMARY', 'mistral')

    GOOGLE_PLACES_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY') or os.environ.get('GOOGLE_PLACES_KEY', '')

    GOOGLE_OAUTH_CLIENT_ID = _env_first('GOOGLE_OAUTH_CLIENT_ID', 'GOOGLE_CLIENT_ID')
    GOOGLE_OAUTH_CLIENT_SECRET = _env_first('GOOGLE_OAUTH_CLIENT_SECRET', 'GOOGLE_CLIENT_SECRET')

    SITE_URL = os.environ.get('SITE_URL', 'http://127.0.0.1:8080').rstrip('/')

    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    STRIPE_ENABLED = bool(STRIPE_SECRET_KEY)
    STRIPE_DEMO_MODE = os.environ.get('STRIPE_DEMO_MODE', '').lower() in ('1', 'true', 'yes')

    # Email SMTP — noms Scalingo V2 (SMTP_*) + alias MAIL_*
    ADMIN_EMAILS = [
        e.strip().lower()
        for e in os.environ.get('ADMIN_EMAILS', '').split(',')
        if e.strip()
    ]
    SMTP_HOST = _env_first('SMTP_HOST', 'MAIL_SERVER')
    SMTP_PORT = int(_env_first('SMTP_PORT', 'MAIL_PORT') or '587')
    SMTP_USER = _env_first('SMTP_USER', 'EMAIL_ADDRESS', 'MAIL_USERNAME')
    SMTP_PASSWORD = _env_first('SMTP_PASSWORD', 'EMAIL_PASSWORD', 'MAIL_PASSWORD', 'BREVO_SMTP_KEY')
    SMTP_FROM = _env_first('SMTP_FROM') or SMTP_USER or 'contact@artworksdigital.fr'
    SMTP_FROM_NAME = _env_first('SMTP_FROM_NAME') or 'Artworks'

    MAIL_SERVER = SMTP_HOST or 'smtp-relay.brevo.com'
    MAIL_PORT = SMTP_PORT
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', '1').lower() in ('1', 'true', 'yes')
    MAIL_USERNAME = SMTP_USER
    MAIL_PASSWORD = SMTP_PASSWORD
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or f'{SMTP_FROM_NAME} <{SMTP_FROM}>'
    MAIL_ENABLED = bool(MAIL_USERNAME and MAIL_PASSWORD and MAIL_SERVER)
    COMMISSION_RATE = float(os.environ.get('COMMISSION_RATE', '0.18'))

    # Réseaux sociaux (alias V2 Scalingo artworksdigital)
    FACEBOOK_PAGE_ACCESS_TOKEN = _env_first('FACEBOOK_PAGE_ACCESS_TOKEN', 'FB_PAGE_TOKEN', 'FACEBOOK_PAGE_TOKEN')
    FACEBOOK_PAGE_ID = _env_first('FACEBOOK_PAGE_ID', 'FB_PAGE_ID')
    INSTAGRAM_ACCESS_TOKEN = _env_first('INSTAGRAM_ACCESS_TOKEN')
    INSTAGRAM_USER_ID = _env_first('INSTAGRAM_USER_ID', 'IG_BUSINESS_ACCOUNT_ID', 'IG_ACCOUNT_ID')
    PINTEREST_CLIENT_ID = _env_first('PINTEREST_CLIENT_ID')
    PINTEREST_CLIENT_SECRET = _env_first('PINTEREST_CLIENT_SECRET')
    PINTEREST_DEFAULT_BOARD_ID = _env_first('PINTEREST_DEFAULT_BOARD_ID')
    PINTEREST_REDIRECT_URI = _env_first('PINTEREST_REDIRECT_URI')
    DEVIANTART_CLIENT_ID = _env_first('DEVIANTART_CLIENT_ID')
    DEVIANTART_CLIENT_SECRET = _env_first('DEVIANTART_CLIENT_SECRET')
    DEVIANTART_REDIRECT_URI = _env_first('DEVIANTART_REDIRECT_URI')
    SOCIAL_ENABLED = bool(
        FACEBOOK_PAGE_ACCESS_TOKEN or INSTAGRAM_USER_ID
        or DEVIANTART_CLIENT_ID or PINTEREST_CLIENT_ID
    )

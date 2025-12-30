'''
rename this file to config.py and update with your credentials
'''
GODEL_URL = "https://app.godelterminal.com/"
GODEL_USERNAME = "your_email@example.com"
GODEL_PASSWORD = "your_password" 
SCWAB_APP_KEY = "your_app_key"
SCWAB_APP_SECRET = "your_app_secret"

# Security hash for dashboard updates
DASHBOARD_SECURITY_HASH = ""

# Database configuration
# For local development
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '',  # Set your MySQL password here
    'database': 'trading_db',
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci',
    'autocommit': False
}

# For Railway production (set via environment variables)
# Railway provides these as: MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
import os
if os.getenv('MYSQL_HOST'):  # Railway environment
    DB_CONFIG = {
        'host': os.getenv('MYSQL_HOST'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER'),
        'password': os.getenv('MYSQL_PASSWORD'),
        'database': os.getenv('MYSQL_DATABASE'),
        'charset': 'utf8mb4',
        'collation': 'utf8mb4_unicode_ci',
        'autocommit': False
    }
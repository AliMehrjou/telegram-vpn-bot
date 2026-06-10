# vpn_bot_project/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram Bot Credentials
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Database Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "vpn_bot")
DB_PORT = os.getenv("DB_PORT", "3306")

PROXY_URL = os.getenv("PROXY_URL","")

CARD_NUMBER = os.getenv("CARD_NUMBER","")
ADMIN_NAME = os.getenv("ADMIN_NAME")

SUB_LINK_TUTORIAL_URL = os.getenv("SUB_LINK_TUTORIAL_URL","")
# Admin and Channel Data
SPONSOR_CHANNEL_ID = os.getenv("SPONSOR_CHANNEL_ID", "")
SPONSOR_CHANNEL_LINK = os.getenv("SPONSOR_CHANNEL_LINK", "")
admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in admin_ids_raw.split(",") if x.strip().isdigit()]
SUPPORT_ADMIN_USERNAME = os.getenv("SUPPORT_ADMIN_USERNAME", "@IAydaNouriI")
# Construct the SQLAlchemy async database URL (using aiomysql)
DATABASE_URL = f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
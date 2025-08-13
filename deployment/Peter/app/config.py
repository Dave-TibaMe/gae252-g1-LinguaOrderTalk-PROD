import os
from dotenv import load_dotenv

# 找到專案根目錄並載入 .env
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))

class Config:
    """應用程式的基礎設定"""
    # LINE Bot 設定
    CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
    CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
    LIFF_ID = os.environ.get('LIFF_ID')

    # Google Maps API Key
    MAPS_API_KEY = os.environ.get('MAPS_API_KEY')

    DATABASE_URL = os.environ.get("DATABASE_URL")
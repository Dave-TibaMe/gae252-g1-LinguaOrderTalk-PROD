# =============================================================================
# 檔案名稱：app/config/settings.py
# 功能描述：統一管理應用程式中的所有設定
# 主要職責：
# - 集中管理所有環境變數
# - 提供預設值和驗證
# - 支援不同環境的配置
# =============================================================================

import os
from typing import Optional

class AppConfig:
    """應用程式配置管理類別"""
    
    # =============================================================================
    # 資料庫配置
    # =============================================================================
    
    # 資料庫連線設定
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_HOST = os.getenv('DB_HOST')
    DB_DATABASE = os.getenv('DB_DATABASE')
    DB_PORT = os.getenv('DB_PORT', '3306')
    
    # 資料庫 SSL 設定
    DB_SSL_CA = os.getenv('DB_SSL_CA')
    DB_SSL_CERT = os.getenv('DB_SSL_CERT')
    DB_SSL_KEY = os.getenv('DB_SSL_KEY')
    
    # 資料庫連線池設定
    DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '10'))
    DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '20'))
    DB_POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '30'))
    DB_POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', '3600'))
    
    # 資料庫超時設定
    DB_CONNECT_TIMEOUT = int(os.getenv('DB_CONNECT_TIMEOUT', '10'))
    DB_READ_TIMEOUT = int(os.getenv('DB_READ_TIMEOUT', '30'))
    DB_WRITE_TIMEOUT = int(os.getenv('DB_WRITE_TIMEOUT', '30'))
    
    # =============================================================================
    # LINE Bot 配置
    # =============================================================================
    
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
    
    # =============================================================================
    # AI 服務配置
    # =============================================================================
    
    # Google Gemini API
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Azure Speech Service
    AZURE_SPEECH_KEY = os.getenv('AZURE_SPEECH_KEY')
    AZURE_SPEECH_REGION = os.getenv('AZURE_SPEECH_REGION')
    
    # =============================================================================
    # Google Cloud 配置
    # =============================================================================
    
    GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', 'ordering-helper-voice-files')
    
    # =============================================================================
    # 應用程式配置
    # =============================================================================
    
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # =============================================================================
    # 驗證方法
    # =============================================================================
    
    @classmethod
    def validate_required_configs(cls) -> dict:
        """驗證必要的配置是否存在"""
        required_configs = {
            'database': {
                'DB_USER': cls.DB_USER,
                'DB_PASSWORD': cls.DB_PASSWORD,
                'DB_HOST': cls.DB_HOST,
                'DB_DATABASE': cls.DB_DATABASE
            },
            'line_bot': {
                'LINE_CHANNEL_ACCESS_TOKEN': cls.LINE_CHANNEL_ACCESS_TOKEN,
                'LINE_CHANNEL_SECRET': cls.LINE_CHANNEL_SECRET
            },
            'ai_services': {
                'GEMINI_API_KEY': cls.GEMINI_API_KEY,
                'AZURE_SPEECH_KEY': cls.AZURE_SPEECH_KEY,
                'AZURE_SPEECH_REGION': cls.AZURE_SPEECH_REGION
            }
        }
        
        missing_configs = {}
        for category, configs in required_configs.items():
            missing = [key for key, value in configs.items() if not value]
            if missing:
                missing_configs[category] = missing
        
        return missing_configs
    
    @classmethod
    def get_database_url(cls) -> str:
        """取得資料庫連線 URL"""
        if cls.DB_SSL_CA:
            # 使用 SSL 連線
            return f"mysql+pymysql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_DATABASE}?ssl_ca={cls.DB_SSL_CA}&ssl_cert={cls.DB_SSL_CERT}&ssl_key={cls.DB_SSL_KEY}"
        else:
            # 一般連線
            return f"mysql+pymysql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_DATABASE}"
    
    @classmethod
    def is_production(cls) -> bool:
        """檢查是否為生產環境"""
        return cls.FLASK_ENV == 'production'
    
    @classmethod
    def is_development(cls) -> bool:
        """檢查是否為開發環境"""
        return cls.FLASK_ENV == 'development'
    
    @classmethod
    def get_config_summary(cls) -> dict:
        """取得配置摘要（用於除錯）"""
        return {
            'environment': cls.FLASK_ENV,
            'debug': cls.FLASK_DEBUG,
            'database': {
                'host': cls.DB_HOST,
                'database': cls.DB_DATABASE,
                'port': cls.DB_PORT,
                'pool_size': cls.DB_POOL_SIZE
            },
            'services': {
                'line_bot': bool(cls.LINE_CHANNEL_ACCESS_TOKEN),
                'gemini': bool(cls.GEMINI_API_KEY),
                'azure_speech': bool(cls.AZURE_SPEECH_KEY),
                'gcs_bucket': cls.GCS_BUCKET_NAME
            }
        }

# 全域配置實例
config = AppConfig()

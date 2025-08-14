# =============================================================================
# 檔案名稱：app/config/urls.py
# 功能描述：統一管理應用程式中的所有 URL 配置
# 主要職責：
# - 集中管理所有 URL 設定
# - 提供環境變數的預設值
# - 支援不同環境的 URL 配置
# =============================================================================

import os
from typing import Optional

class URLConfig:
    """URL 配置管理類別"""
    
    # 預設的 Cloud Run URL
    DEFAULT_CLOUD_RUN_URL = "https://ordering-helper-backend-1095766716155.asia-east1.run.app"
    
    # 開發環境 URL
    DEFAULT_DEV_URL = "http://localhost:5000"
    
    @classmethod
    def get_base_url(cls) -> str:
        """取得基礎 URL"""
        return os.getenv('BASE_URL', cls.DEFAULT_CLOUD_RUN_URL)
    
    @classmethod
    def get_api_base_url(cls) -> str:
        """取得 API 基礎 URL"""
        base_url = cls.get_base_url()
        return f"{base_url}/api"
    
    @classmethod
    def get_voice_url(cls, filename: str) -> str:
        """取得語音檔 URL"""
        base_url = cls.get_base_url()
        return f"{base_url}/api/voices/{filename}"
    
    @classmethod
    def get_webhook_url(cls) -> str:
        """取得 Webhook URL"""
        base_url = cls.get_base_url()
        return f"{base_url}/webhook/callback"
    
    @classmethod
    def get_health_check_url(cls) -> str:
        """取得健康檢查 URL"""
        base_url = cls.get_base_url()
        return f"{base_url}/api/health"
    
    @classmethod
    def get_stores_url(cls) -> str:
        """取得店家列表 URL"""
        base_url = cls.get_base_url()
        return f"{base_url}/api/stores"
    
    @classmethod
    def get_menu_url(cls, store_id: int) -> str:
        """取得菜單 URL"""
        base_url = cls.get_base_url()
        return f"{base_url}/api/menu/{store_id}"
    
    @classmethod
    def get_order_url(cls, order_id: Optional[int] = None) -> str:
        """取得訂單 URL"""
        base_url = cls.get_base_url()
        if order_id:
            return f"{base_url}/api/orders/{order_id}"
        return f"{base_url}/api/orders"
    
    @classmethod
    def get_upload_url(cls) -> str:
        """取得上傳 URL"""
        base_url = cls.get_base_url()
        return f"{base_url}/api/upload-menu-image"
    
    @classmethod
    def is_production(cls) -> bool:
        """檢查是否為生產環境"""
        return cls.get_base_url() != cls.DEFAULT_DEV_URL
    
    @classmethod
    def is_cloud_run(cls) -> bool:
        """檢查是否部署在 Cloud Run"""
        return "run.app" in cls.get_base_url()

# 為了向後相容，提供全域變數
BASE_URL = URLConfig.get_base_url()
API_BASE_URL = URLConfig.get_api_base_url()

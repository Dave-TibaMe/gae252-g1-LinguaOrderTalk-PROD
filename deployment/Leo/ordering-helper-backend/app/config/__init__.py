# =============================================================================
# 檔案名稱：app/config/__init__.py
# 功能描述：配置模組的初始化檔案
# 主要職責：
# - 匯出所有配置相關的類別和函數
# - 提供統一的配置存取介面
# =============================================================================

from .urls import URLConfig, BASE_URL, API_BASE_URL
from .settings import AppConfig, config

__all__ = [
    'URLConfig',
    'BASE_URL', 
    'API_BASE_URL',
    'AppConfig',
    'config'
]

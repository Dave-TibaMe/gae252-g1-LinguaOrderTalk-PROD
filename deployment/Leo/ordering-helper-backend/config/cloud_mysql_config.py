#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloud MySQL 連線配置

功能：
1. 管理 Cloud MySQL 連線參數
2. 設定 SSL 連線
3. 配置連線池
4. 提供環境變數驗證
"""

import os
from typing import Optional, Dict, Any

class CloudMySQLConfig:
    """Cloud MySQL 連線配置類別"""
    
    def __init__(self):
        """初始化配置"""
        self.db_user = os.getenv('DB_USER')
        self.db_password = os.getenv('DB_PASSWORD')
        self.db_host = os.getenv('DB_HOST')
        self.db_name = os.getenv('DB_DATABASE')
        self.db_port = os.getenv('DB_PORT', '3306')
        
        # SSL 配置
        self.ssl_ca = os.getenv('DB_SSL_CA')
        self.ssl_cert = os.getenv('DB_SSL_CERT')
        self.ssl_key = os.getenv('DB_SSL_KEY')
        
        # 連線池配置
        self.pool_size = int(os.getenv('DB_POOL_SIZE', '10'))
        self.max_overflow = int(os.getenv('DB_MAX_OVERFLOW', '20'))
        self.pool_timeout = int(os.getenv('DB_POOL_TIMEOUT', '30'))
        self.pool_recycle = int(os.getenv('DB_POOL_RECYCLE', '3600'))
        
        # 連線超時配置
        self.connect_timeout = int(os.getenv('DB_CONNECT_TIMEOUT', '10'))
        self.read_timeout = int(os.getenv('DB_READ_TIMEOUT', '30'))
        self.write_timeout = int(os.getenv('DB_WRITE_TIMEOUT', '30'))
    
    def is_configured(self) -> bool:
        """檢查是否已完整配置"""
        required_vars = ['DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_DATABASE']
        return all(os.getenv(var) for var in required_vars)
    
    def get_database_url(self) -> str:
        """取得資料庫連線 URL"""
        if not self.is_configured():
            raise ValueError("Cloud MySQL 配置不完整")
        
        # 基礎連線字串
        base_url = f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        
        # 查詢參數
        params = []
        
        # SSL 配置
        if self.ssl_ca or self.ssl_cert or self.ssl_key:
            ssl_params = []
            if self.ssl_ca:
                ssl_params.append(f"ssl_ca={self.ssl_ca}")
            if self.ssl_cert:
                ssl_params.append(f"ssl_cert={self.ssl_cert}")
            if self.ssl_key:
                ssl_params.append(f"ssl_key={self.ssl_key}")
            
            if ssl_params:
                params.append(f"ssl={{{','.join(ssl_params)}}}")
        else:
            # 預設 SSL 配置（Cloud SQL 推薦）
            params.append("ssl={'ssl': {}}")
            params.append("ssl_verify_cert=false")
        
        # 連線池配置
        params.extend([
            f"pool_size={self.pool_size}",
            f"max_overflow={self.max_overflow}",
            f"pool_timeout={self.pool_timeout}",
            f"pool_recycle={self.pool_recycle}"
        ])
        
        # 超時配置
        params.extend([
            f"connect_timeout={self.connect_timeout}",
            f"read_timeout={self.read_timeout}",
            f"write_timeout={self.write_timeout}"
        ])
        
        # 字符集配置
        params.extend([
            "charset=utf8mb4",
            "collation=utf8mb4_unicode_ci"
        ])
        
        # 組合完整 URL
        if params:
            return f"{base_url}?{'&'.join(params)}"
        else:
            return base_url
    
    def get_sqlalchemy_config(self) -> Dict[str, Any]:
        """取得 SQLAlchemy 配置"""
        return {
            'SQLALCHEMY_DATABASE_URI': self.get_database_url(),
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'SQLALCHEMY_ENGINE_OPTIONS': {
                'pool_size': self.pool_size,
                'max_overflow': self.max_overflow,
                'pool_timeout': self.pool_timeout,
                'pool_recycle': self.pool_recycle,
                'connect_args': {
                    'connect_timeout': self.connect_timeout,
                    'read_timeout': self.read_timeout,
                    'write_timeout': self.write_timeout,
                }
            }
        }
    
    def get_connection_info(self) -> Dict[str, Any]:
        """取得連線資訊（用於除錯，不包含密碼）"""
        return {
            'host': self.db_host,
            'port': self.db_port,
            'database': self.db_name,
            'user': self.db_user,
            'ssl_enabled': bool(self.ssl_ca or self.ssl_cert or self.ssl_key),
            'pool_size': self.pool_size,
            'max_overflow': self.max_overflow
        }
    
    def validate_config(self) -> Dict[str, Any]:
        """驗證配置並回傳結果"""
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'config_info': {}
        }
        
        # 檢查必要環境變數
        if not self.db_user:
            result['errors'].append("DB_USER 未設定")
            result['valid'] = False
        
        if not self.db_password:
            result['errors'].append("DB_PASSWORD 未設定")
            result['valid'] = False
        
        if not self.db_host:
            result['errors'].append("DB_HOST 未設定")
            result['valid'] = False
        
        if not self.db_name:
            result['errors'].append("DB_DATABASE 未設定")
            result['valid'] = False
        
        # 檢查連線池配置
        if self.pool_size < 1:
            result['warnings'].append("DB_POOL_SIZE 應該大於 0")
        
        if self.max_overflow < 0:
            result['warnings'].append("DB_MAX_OVERFLOW 應該大於等於 0")
        
        # 檢查超時配置
        if self.connect_timeout < 1:
            result['warnings'].append("DB_CONNECT_TIMEOUT 應該大於 0")
        
        if self.read_timeout < 1:
            result['warnings'].append("DB_READ_TIMEOUT 應該大於 0")
        
        if self.write_timeout < 1:
            result['warnings'].append("DB_WRITE_TIMEOUT 應該大於 0")
        
        # 如果配置有效，添加連線資訊
        if result['valid']:
            result['config_info'] = self.get_connection_info()
        
        return result

# 全域配置實例
cloud_mysql_config = CloudMySQLConfig()

def get_cloud_mysql_config() -> CloudMySQLConfig:
    """取得 Cloud MySQL 配置實例"""
    return cloud_mysql_config

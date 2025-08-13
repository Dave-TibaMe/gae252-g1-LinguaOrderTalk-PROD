# -*- coding: utf-8 -*-
"""
配置模組

包含 Cloud MySQL 連線配置和其他應用程式配置
"""

from .cloud_mysql_config import get_cloud_mysql_config, CloudMySQLConfig

__all__ = ['get_cloud_mysql_config', 'CloudMySQLConfig']

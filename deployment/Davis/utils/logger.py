import logging
import os
from datetime import datetime

def setup_logger(name='review_analysis', log_file='logs/app.log'):
    """設置日誌記錄器"""
    # 確保日誌目錄存在
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # 創建日誌記錄器
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 避免重複添加處理器
    if not logger.handlers:
        # 文件處理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 控制台處理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 日誌格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加處理器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

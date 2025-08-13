#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
店家 ID 解析服務

功能：
1. 將 Google Place ID 轉換為內部整數 store_id
2. 自動建立不存在的店家記錄
3. 支援整數和字串格式的 store_id 輸入
4. 加強錯誤處理和輸入驗證
"""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from app.models import Store, db
from typing import Union, Optional
import logging

logger = logging.getLogger(__name__)

def resolve_store_id(store_identifier: Union[str, int], store_name: Optional[str] = None) -> int:
    """
    解析店家識別碼，將 Place ID 或整數轉換為內部 store_id
    
    Args:
        store_identifier: 店家識別碼（可能是整數、數字字串或 Google Place ID）
        store_name: 店家名稱（可選，用於建立新店家時）
    
    Returns:
        int: 內部整數 store_id
        
    Raises:
        ValueError: 當無法解析店家識別碼時
        SQLAlchemyError: 當資料庫操作失敗時
    """
    try:
        # 情況 1: 已經是整數
        if isinstance(store_identifier, int):
            if store_identifier <= 0:
                raise ValueError(f"store_id 必須大於 0，收到: {store_identifier}")
            logger.info(f"店家識別碼已經是整數: {store_identifier}")
            return store_identifier
        
        # 情況 2: 數字字串（如 "123"）
        if isinstance(store_identifier, str) and store_identifier.isdigit():
            store_id = int(store_identifier)
            if store_id <= 0:
                raise ValueError(f"store_id 必須大於 0，收到: {store_id}")
            logger.info(f"店家識別碼是數字字串，轉換為整數: {store_id}")
            return store_id
        
        # 情況 3: Google Place ID 字串（如 "ChIJ0boght2rQjQRsH-_buCo3S4"）
        if isinstance(store_identifier, str):
            place_id = store_identifier.strip()
            
            # 驗證 Google Place ID 格式
            if not place_id.startswith('ChIJ'):
                raise ValueError(f"無效的 Google Place ID 格式: {place_id}，應以 'ChIJ' 開頭")
            
            if len(place_id) < 10:
                raise ValueError(f"Google Place ID 長度不足: {place_id}")
            
            logger.info(f"嘗試解析 Google Place ID: {place_id}")
            
            # 先查詢是否已存在
            existing_store = db.session.execute(
                select(Store).where(Store.place_id == place_id)
            ).scalars().first()
            
            if existing_store:
                logger.info(f"找到現有店家，store_id: {existing_store.store_id}")
                return existing_store.store_id
            
            # 如果不存在，建立新店家
            logger.info(f"建立新店家記錄，Place ID: {place_id}")
            new_store = Store(
                place_id=place_id,
                store_name=store_name or f"店家_{place_id[:8]}",  # 使用 Place ID 前8位作為預設名稱
                partner_level=0  # 預設為非合作店家
            )
            
            db.session.add(new_store)
            db.session.flush()  # 取得自動遞增的 store_id
            
            logger.info(f"成功建立新店家，store_id: {new_store.store_id}")
            return new_store.store_id
        
        # 其他情況
        raise ValueError(f"不支援的店家識別碼格式: {type(store_identifier)} - {store_identifier}")
        
    except SQLAlchemyError as e:
        logger.error(f"資料庫操作失敗: {e}")
        db.session.rollback()
        raise
    except Exception as e:
        logger.error(f"解析店家識別碼失敗: {e}")
        raise ValueError(f"無法解析店家識別碼: {e}")

def coerce_store_id_or_400(value: Union[str, int]) -> int:
    """
    強制轉換 store_id 或拋出 400 錯誤（用於 API 驗證）
    
    Args:
        value: 要轉換的值
        
    Returns:
        int: 轉換後的整數 store_id
        
    Raises:
        ValueError: 當無法轉換時
    """
    try:
        return resolve_store_id(value)
    except Exception as e:
        raise ValueError(f"store_id 驗證失敗: {e}")

def validate_store_id_format(value: Union[str, int]) -> bool:
    """
    驗證 store_id 格式是否有效（不進行資料庫查詢）
    
    Args:
        value: 要驗證的值
        
    Returns:
        bool: 格式是否有效
    """
    try:
        # 整數
        if isinstance(value, int):
            return value > 0
        
        # 字串
        if isinstance(value, str):
            # 數字字串
            if value.isdigit():
                return int(value) > 0
            
            # Google Place ID 格式
            if value.startswith('ChIJ') and len(value) >= 10:
                return True
        
        return False
    except Exception:
        return False

def strict_validate_store_id(value: Union[str, int], allow_auto_create: bool = False) -> tuple[bool, str]:
    """
    嚴格驗證 store_id，可選擇是否允許自動建立
    
    Args:
        value: 要驗證的值
        allow_auto_create: 是否允許自動建立新店家
        
    Returns:
        tuple: (是否有效, 錯誤訊息)
    """
    try:
        # 基本格式驗證
        if not validate_store_id_format(value):
            return False, f"無效的 store_id 格式: {value}"
        
        # 如果是 Google Place ID 且不允許自動建立
        if isinstance(value, str) and value.startswith('ChIJ') and not allow_auto_create:
            return False, f"不允許自動建立新店家，請先使用 /api/stores/resolve 端點"
        
        return True, ""
        
    except Exception as e:
        return False, f"驗證失敗: {e}"

def get_store_by_place_id(place_id: str) -> Optional[Store]:
    """
    根據 Google Place ID 查詢店家
    
    Args:
        place_id: Google Place ID
        
    Returns:
        Store 物件或 None
    """
    try:
        if not place_id or not place_id.startswith('ChIJ'):
            logger.warning(f"無效的 Place ID 格式: {place_id}")
            return None
            
        store = db.session.execute(
            select(Store).where(Store.place_id == place_id)
        ).scalars().first()
        return store
    except SQLAlchemyError as e:
        logger.error(f"查詢店家失敗: {e}")
        return None

def create_temp_store(place_id: str, store_name: Optional[str] = None) -> Store:
    """
    建立臨時店家記錄
    
    Args:
        place_id: Google Place ID
        store_name: 店家名稱
        
    Returns:
        新建立的 Store 物件
    """
    try:
        if not place_id or not place_id.startswith('ChIJ'):
            raise ValueError(f"無效的 Place ID 格式: {place_id}")
            
        store_name = store_name or f"臨時店家_{place_id[:8]}"
        
        new_store = Store(
            place_id=place_id,
            store_name=store_name,
            partner_level=0  # 非合作店家
        )
        
        db.session.add(new_store)
        db.session.flush()
        
        logger.info(f"成功建立臨時店家: {new_store.store_id}")
        return new_store
        
    except SQLAlchemyError as e:
        logger.error(f"建立臨時店家失敗: {e}")
        db.session.rollback()
        raise

def validate_store_id(store_id: Union[str, int]) -> bool:
    """
    驗證店家識別碼格式是否有效
    
    Args:
        store_id: 店家識別碼
        
    Returns:
        bool: 是否有效
    """
    try:
        # 整數
        if isinstance(store_id, int):
            return store_id > 0
        
        # 字串
        if isinstance(store_id, str):
            # 數字字串
            if store_id.isdigit():
                return int(store_id) > 0
            
            # Google Place ID 格式（通常以 ChIJ 開頭）
            if store_id.startswith('ChIJ') and len(store_id) > 10:
                return True
        
        return False
        
    except Exception:
        return False

def safe_resolve_store_id(store_identifier: Union[str, int], store_name: Optional[str] = None, default_id: int = 1) -> int:
    """
    安全的 store_id 解析，失敗時返回預設值
    
    Args:
        store_identifier: 店家識別碼
        store_name: 店家名稱
        default_id: 預設的 store_id
        
    Returns:
        int: 解析後的 store_id 或預設值
    """
    try:
        return resolve_store_id(store_identifier, store_name)
    except Exception as e:
        logger.warning(f"store_id 解析失敗，使用預設值 {default_id}: {e}")
        return default_id

def debug_store_id_info(store_identifier: Union[str, int]) -> dict:
    """
    除錯用：分析 store_id 的詳細資訊
    
    Args:
        store_identifier: 店家識別碼
        
    Returns:
        dict: 詳細的分析資訊
    """
    info = {
        "input_value": store_identifier,
        "input_type": type(store_identifier).__name__,
        "is_valid_format": validate_store_id_format(store_identifier),
        "analysis": {}
    }
    
    try:
        if isinstance(store_identifier, int):
            info["analysis"]["type"] = "integer"
            info["analysis"]["value"] = store_identifier
            info["analysis"]["is_positive"] = store_identifier > 0
        elif isinstance(store_identifier, str):
            info["analysis"]["type"] = "string"
            info["analysis"]["length"] = len(store_identifier)
            info["analysis"]["is_digit"] = store_identifier.isdigit()
            info["analysis"]["starts_with_chij"] = store_identifier.startswith('ChIJ')
            info["analysis"]["is_place_id"] = store_identifier.startswith('ChIJ') and len(store_identifier) >= 10
            
            if store_identifier.isdigit():
                try:
                    int_value = int(store_identifier)
                    info["analysis"]["int_value"] = int_value
                    info["analysis"]["is_positive"] = int_value > 0
                except ValueError:
                    info["analysis"]["int_conversion_error"] = True
        else:
            info["analysis"]["type"] = "unknown"
            info["analysis"]["error"] = "不支援的類型"
            
    except Exception as e:
        info["analysis"]["error"] = str(e)
    
    return info

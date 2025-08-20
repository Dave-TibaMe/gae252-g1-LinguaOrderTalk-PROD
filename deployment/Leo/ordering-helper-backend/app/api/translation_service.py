# =============================================================================
# 檔案名稱：app/api/translation_service.py
# 功能描述：翻譯服務模組，提供語言碼正規化和翻譯功能
# 主要職責：
# - 語言碼正規化（BCP-47 到短碼轉換）
# - 文字翻譯功能
# - 翻譯結果快取管理
# =============================================================================

import os
import logging
from typing import List, Optional
from flask import current_app

def normalize_lang(lang: str) -> str:
    """
    語言碼正規化：把 BCP-47 語言碼轉換成支援的短碼
    
    Args:
        lang: 原始語言碼（如 'en-US', 'zh-Hant', 'ja-JP'）
    
    Returns:
        正規化後的語言碼（如 'en', 'zh-tw', 'ja'）
    """
    if not lang:
        return "en"
    
    s = lang.lower()
    
    # 中文處理
    if s.startswith("zh"):
        if "hant" in s or "tw" in s or "hk" in s:
            return "zh-tw"
        elif "hans" in s or "cn" in s or "sg" in s:
            return "zh-cn"
        else:
            return "zh-tw"  # 預設繁體中文
    
    # 其他語言處理
    if s.startswith("en"):
        return "en"
    if s.startswith("ja"):
        return "ja"
    if s.startswith("ko"):
        return "ko"
    if s.startswith("fr"):
        return "fr"
    if s.startswith("de"):
        return "de"
    if s.startswith("es"):
        return "es"
    if s.startswith("it"):
        return "it"
    if s.startswith("pt"):
        return "pt"
    if s.startswith("ru"):
        return "ru"
    if s.startswith("ar"):
        return "ar"
    if s.startswith("hi"):
        return "hi"
    if s.startswith("th"):
        return "th"
    if s.startswith("vi"):
        return "vi"
    
    # 預設回英文
    return "en"

def translate_text(text: str, target_lang: str, source_lang: str = "zh") -> str:
    """
    翻譯單一文字
    
    Args:
        text: 要翻譯的文字
        target_lang: 目標語言碼（已正規化）
        source_lang: 來源語言碼（預設中文）
    
    Returns:
        翻譯後的文字
    """
    if not text or target_lang.startswith("zh"):
        return text
    
    try:
        # 使用現有的批次翻譯功能
        from .helpers import translate_text_batch
        translated_texts = translate_text_batch([text], target_lang, source_lang)
        return translated_texts[0] if translated_texts else text
    except Exception as e:
        current_app.logger.warning(f"翻譯失敗: {e}")
        return text

def translate_texts(texts: List[str], target_lang: str, source_lang: str = "zh") -> List[str]:
    """
    批次翻譯文字
    
    Args:
        texts: 要翻譯的文字列表
        target_lang: 目標語言碼（已正規化）
        source_lang: 來源語言碼（預設中文）
    
    Returns:
        翻譯後的文字列表
    """
    if not texts or target_lang.startswith("zh"):
        return texts
    
    try:
        from .helpers import translate_text_batch
        return translate_text_batch(texts, target_lang, source_lang)
    except Exception as e:
        current_app.logger.warning(f"批次翻譯失敗: {e}")
        return texts

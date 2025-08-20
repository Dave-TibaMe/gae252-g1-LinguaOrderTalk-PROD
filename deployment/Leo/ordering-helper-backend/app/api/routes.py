# =============================================================================
# 檔案名稱：app/api/routes.py
# 功能描述：定義所有 API 端點，處理 LIFF 前端的 HTTP 請求
# 主要職責：
# - 提供店家資料查詢 API（合作店家）
# - 處理菜單圖片 OCR 和翻譯（非合作店家）
# - 處理訂單建立
# - 處理使用者註冊
# 支援功能：
# - 多語言菜單顯示
# - 菜單圖片 OCR 處理
# - 訂單語音生成
# =============================================================================

from flask import Blueprint, jsonify, request, send_file, current_app, send_from_directory
from ..models import db, Store, Menu, MenuItem, MenuTranslation, User, Order, OrderItem, StoreTranslation, OCRMenu, OCRMenuItem, OCRMenuTranslation, VoiceFile, Language
from .helpers import process_menu_with_gemini, generate_voice_order, create_order_summary, save_uploaded_file, VOICE_DIR
import json
import os
from werkzeug.utils import secure_filename
import datetime
import uuid
import time

# =============================================================================
# CORS 處理函數
# 功能：統一處理 OPTIONS 預檢請求
# =============================================================================
def handle_cors_preflight():
    """處理 CORS 預檢請求"""
    response = jsonify({'message': 'OK'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', '*')  # 允許所有 headers
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    response.headers.add('Access-Control-Max-Age', '3600')
    return response, 200

# =============================================================================
# Blueprint 建立區塊
# 功能：建立 API Blueprint，用於組織所有 API 路由
# 作用：將所有 API 端點統一註冊到 /api 路徑下
# =============================================================================
api_bp = Blueprint('api', __name__)

# =============================================================================
# 檔案上傳設定區塊
# 功能：定義檔案上傳的相關設定
# 包含：
# - UPLOAD_FOLDER：上傳檔案的儲存目錄
# - ALLOWED_EXTENSIONS：允許上傳的檔案格式
# - allowed_file()：檢查檔案格式是否合法的函數
# 用途：用於菜單圖片上傳功能
# =============================================================================
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =============================================================================
# 核心 API 端點
# 功能：提供 LIFF 前端所需的核心功能
# =============================================================================

@api_bp.route('/test', methods=['GET'])
def test_api():
    """API 連線測試端點"""
    return jsonify({
        'message': 'API 連線正常',
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'status': 'success'
    })

@api_bp.route('/translate', methods=['POST', 'OPTIONS'])
def translate_text():
    """批次翻譯文字內容（支援任意語言）"""
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        data = request.get_json() or {}
        contents = data.get('contents', [])
        source = data.get('source')  # 可為 None 讓服務自動偵測
        target = data.get('target')  # e.g. "fr-FR" 或 "fr"
        
        if not contents or not target:
            return jsonify({"error": "contents/target required"}), 400
        
        # 使用新的翻譯服務進行語言碼正規化
        from .translation_service import normalize_lang, translate_texts
        normalized_target = normalize_lang(target)
        
        # 批次翻譯
        translated_texts = translate_texts(contents, normalized_target, source)
        
        response = jsonify({"translated": translated_texts})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Cache-Control', 'public, max-age=300')  # 5分鐘快取
        return response
        
    except Exception as e:
        current_app.logger.error(f"翻譯API錯誤: {str(e)}")
        # 即使出錯也要回傳 200，避免前端卡住
        response = jsonify({"translated": contents, "error": "翻譯失敗，回傳原文"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200
        return jsonify({"error": f"翻譯失敗: {str(e)}"}), 500

@api_bp.route('/api/translate', methods=['POST', 'OPTIONS'])
def translate_single_text():
    """翻譯單一文字（前端 fallback 用）"""
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        data = request.get_json(silent=True) or {}
        text = data.get('text', '')
        target = request.args.get('target', 'en')
        
        if not text:
            response = jsonify({"translated": ""})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 200
        
        # 使用新的翻譯服務
        from .translation_service import normalize_lang, translate_text
        normalized_target = normalize_lang(target)
        translated = translate_text(text, normalized_target)
        
        response = jsonify({"translated": translated})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Cache-Control', 'public, max-age=300')  # 5分鐘快取
        return response, 200
        
    except Exception as e:
        current_app.logger.error(f"單一文字翻譯失敗: {str(e)}")
        # 即使出錯也要回傳 200，避免前端卡住
        response = jsonify({"translated": text, "error": "翻譯失敗，回傳原文"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200

@api_bp.route('/stores/resolve-old', methods=['GET'])
def resolve_store_old():
    """解析店家識別碼，將 Place ID 轉換為內部 store_id (舊版本)"""
    try:
        place_id = request.args.get('place_id')
        store_name = request.args.get('name')
        
        if not place_id:
            return jsonify({"error": "place_id 參數是必需的"}), 400
        
        from .store_resolver import resolve_store_id
        store_db_id = resolve_store_id(place_id, store_name)
        
        return jsonify({
            "success": True,
            "place_id": place_id,
            "store_id": store_db_id,
            "message": f"成功解析店家識別碼: {place_id} -> {store_db_id}"
        }), 200
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": "無效的店家識別碼",
            "details": str(e)
        }), 400
    except Exception as e:
        current_app.logger.error(f"解析店家識別碼失敗: {e}")
        return jsonify({
            "success": False,
            "error": "解析失敗",
            "details": str(e)
        }), 500

@api_bp.route('/stores/debug', methods=['GET'])
def debug_store_id():
    """除錯用：分析 store_id 的詳細資訊"""
    try:
        store_id = request.args.get('store_id')
        
        if not store_id:
            return jsonify({"error": "store_id 參數是必需的"}), 400
        
        from .store_resolver import debug_store_id_info
        
        # 分析 store_id
        debug_info = debug_store_id_info(store_id)
        
        return jsonify({
            "success": True,
            "debug_info": debug_info,
            "message": "store_id 分析完成"
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"除錯 store_id 失敗: {e}")
        return jsonify({
            "success": False,
            "error": "除錯失敗",
            "details": str(e)
        }), 500

@api_bp.route('/stores/<int:store_id>', methods=['GET'])
def get_store(store_id):
    """取得店家資訊（支援多語言翻譯）"""
    try:
        # 取得使用者語言偏好
        user_language = request.args.get('lang', 'zh')
        
        store = Store.query.get(store_id)
        if not store:
            return jsonify({"error": "找不到店家"}), 404
        
        # 使用新的翻譯功能（優先使用資料庫翻譯）
        from .helpers import translate_store_info_with_db_fallback
        translated_store = translate_store_info_with_db_fallback(store, user_language)
        
        return jsonify({
            "store_id": store.store_id,
            "user_language": user_language,
            "store_info": translated_store
        })
        
    except Exception as e:
        return jsonify({'error': '無法載入店家資訊'}), 500

@api_bp.route('/menu/<int:store_id>', methods=['GET'])
def get_menu(store_id):
    """取得店家菜單（支援多語言翻譯，優先使用資料庫翻譯）"""
    try:
        # 取得使用者語言偏好（支援任意 BCP47 語言碼）
        user_language = request.args.get('lang', 'zh')
        
        # 加入最小日誌
        current_app.logger.info("get-menu store_id=%s, user_lang=%s -> found=%s, items=%d",
                                store_id, user_language, True, 0)  # 先設為 0，後面會更新
        
        # 支援 Accept-Language header 作為 fallback
        if not user_language or user_language == 'zh':
            accept_language = request.headers.get('Accept-Language', '')
            if accept_language:
                # 簡單解析 Accept-Language，取第一個語言
                first_lang = accept_language.split(',')[0].strip().split(';')[0]
                if first_lang and first_lang != 'zh':
                    user_language = first_lang
        
        # 使用新的翻譯服務進行語言碼正規化
        from .translation_service import normalize_lang, translate_text
        normalized_lang = normalize_lang(user_language)
        
        # 先檢查店家是否存在
        store = Store.query.get(store_id)
        if not store:
            return jsonify({"error": "找不到店家"}), 404
        
        # 嘗試查詢菜單項目，透過菜單關聯查詢，過濾掉價格為 0 的商品
        try:
            # 先查詢店家的菜單
            menus = Menu.query.filter(Menu.store_id == store_id).all()
            if not menus:
                return jsonify({
                    "error": "此店家目前沒有菜單",
                    "store_id": store_id,
                    "store_name": store.store_name,
                    "message": "請使用菜單圖片上傳功能來建立菜單"
                }), 404
            
            # 透過菜單查詢菜單項目
            menu_ids = [menu.menu_id for menu in menus]
            menu_items = MenuItem.query.filter(
                MenuItem.menu_id.in_(menu_ids),
                MenuItem.price_small > 0  # 只返回價格大於 0 的商品
            ).all()
        except Exception as e:
            # 如果表格不存在，返回友好的錯誤訊息
            return jsonify({
                "error": "此店家目前沒有菜單資料",
                "store_id": store_id,
                "store_name": store.store_name,
                "message": "請使用菜單圖片上傳功能來建立菜單"
            }), 404
        
        if not menu_items:
            current_app.logger.info("get-menu store_id=%s, user_lang=%s -> found=%s, items=%d",
                                    store_id, user_language, False, 0)
            return jsonify({
                "error": "此店家目前沒有菜單項目",
                "store_id": store_id,
                "store_name": store.store_name,
                "message": "請使用菜單圖片上傳功能來建立菜單"
            }), 404
        
        # 使用新的 DTO 模型處理雙語菜單項目
        from .dto_models import build_menu_item_dto
        translated_items = []
        current_app.logger.info(f"開始處理雙語菜單項目，目標語言: {normalized_lang}")
        
        for item in menu_items:
            # 使用 alias 查詢，將 item_name 作為 name_source
            # 這樣可以保留原文，同時提供翻譯版本
            menu_item_dto = build_menu_item_dto(item, normalized_lang)
            
            # 如果需要翻譯，使用翻譯服務
            if not normalized_lang.startswith('zh'):
                from .translation_service import translate_text
                translated_name = translate_text(menu_item_dto.name_source, normalized_lang)
                menu_item_dto.name_ui = translated_name
                
                # 記錄翻譯結果
                current_app.logger.info(f"翻譯: '{menu_item_dto.name_source}' -> '{translated_name}' (語言: {normalized_lang})")
            
            # 轉換為字典格式，明確分離 native 和 display 欄位
            translated_item = {
                "id": menu_item_dto.id,
                # Native 欄位（資料庫原文，用於中文摘要和語音）
                "name_native": menu_item_dto.name_source,  # 原始中文名稱
                "original_name": menu_item_dto.name_source,  # 向後兼容
                # Display 欄位（使用者語言，用於 UI 顯示）
                "name": menu_item_dto.name_ui,  # 使用者語言顯示名稱
                "translated_name": menu_item_dto.name_ui,  # 向後兼容
                # 其他欄位
                "price_small": menu_item_dto.price_small,
                "price_large": menu_item_dto.price_big,
                "category": "",
                "original_category": ""
            }
            translated_items.append(translated_item)
        
        current_app.logger.info("get-menu store_id=%s, user_lang=%s -> found=%s, items=%d",
                                store_id, user_language, True, len(translated_items))
        
        return jsonify({
            "store_id": store_id,
            "user_language": user_language,
            "normalized_language": normalized_lang,
            "menu_items": translated_items
        })
        
    except Exception as e:
        current_app.logger.error(f"菜單載入錯誤: {str(e)}")
        return jsonify({'error': '無法載入菜單'}), 500

@api_bp.route('/menu/by-place-id/<place_id>', methods=['GET'])
def get_menu_by_place_id(place_id):
    """根據 place_id 取得店家菜單（支援多語言翻譯）"""
    try:
        # 取得使用者語言偏好（支援任意 BCP47 語言碼）
        user_language = request.args.get('lang', 'zh')
        
        # 支援 Accept-Language header 作為 fallback
        if not user_language or user_language == 'zh':
            accept_language = request.headers.get('Accept-Language', '')
            if accept_language:
                # 簡單解析 Accept-Language，取第一個語言
                first_lang = accept_language.split(',')[0].strip().split(';')[0]
                if first_lang and first_lang != 'zh':
                    user_language = first_lang
        
        # 使用新的翻譯服務進行語言碼正規化
        from .translation_service import normalize_lang, translate_text
        normalized_lang = normalize_lang(user_language)
        
        # 先根據 place_id 找到店家
        store = Store.query.filter_by(place_id=place_id).first()
        if not store:
            return jsonify({"error": "找不到店家"}), 404
        
        # 嘗試查詢菜單項目，透過菜單關聯查詢，過濾掉價格為 0 的商品
        try:
            # 先查詢店家的菜單
            menus = Menu.query.filter(Menu.store_id == store.store_id).all()
            if not menus:
                return jsonify({
                    "error": "此店家目前沒有菜單",
                    "store_id": store.store_id,
                    "place_id": place_id,
                    "store_name": store.store_name,
                    "message": "請使用菜單圖片上傳功能來建立菜單"
                }), 404
            
            # 透過菜單查詢菜單項目
            menu_ids = [menu.menu_id for menu in menus]
            menu_items = MenuItem.query.filter(
                MenuItem.menu_id.in_(menu_ids),
                MenuItem.price_small > 0  # 只返回價格大於 0 的商品
            ).all()
        except Exception as e:
            # 如果表格不存在，返回友好的錯誤訊息
            return jsonify({
                "error": "此店家目前沒有菜單資料",
                "store_id": store.store_id,
                "place_id": place_id,
                "store_name": store.store_name,
                "message": "請使用菜單圖片上傳功能來建立菜單"
            }), 404
        
        if not menu_items:
                    return jsonify({
            "error": "此店家目前沒有菜單項目",
            "store_id": store.store_id,
            "place_id": place_id,
            "store_name": store.store_name,
            "message": "請使用菜單圖片上傳功能來建立菜單"
        }), 404
        
        # 使用新的翻譯服務翻譯菜單項目
        translated_items = []
        current_app.logger.info(f"開始翻譯菜單項目，目標語言: {normalized_lang}")
        
        for item in menu_items:
            original_name = item.item_name
            translated_name = translate_text(original_name, normalized_lang)
            
            # 記錄翻譯結果
            current_app.logger.info(f"翻譯: '{original_name}' -> '{translated_name}' (語言: {normalized_lang})")
            
            translated_item = {
                "id": item.menu_item_id,
                "name": translated_name,
                "translated_name": translated_name,  # 為了前端兼容性
                "original_name": original_name,
                "price_small": item.price_small,
                "price_large": item.price_big,  # 修正：使用 price_big 而不是 price_large
                "category": "",  # 修正：資料庫中沒有 category 欄位
                "original_category": ""
            }
            translated_items.append(translated_item)
        
        return jsonify({
            "store_id": store.store_id,
            "place_id": place_id,
            "user_language": user_language,
            "normalized_language": normalized_lang,
            "menu_items": translated_items
        })
        
    except Exception as e:
        return jsonify({'error': '無法載入菜單'}), 500

@api_bp.route('/stores/check-partner-status', methods=['GET', 'OPTIONS'])
def check_partner_status():
    """檢查店家合作狀態（支援 store_id 或 place_id）"""
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    # 加入最小日誌
    store_id = request.args.get('store_id', type=int)
    user_lang = request.headers.get('X-LIFF-User-Lang', 'en')
    current_app.logger.info("check-partner-status store_id=%s, user_lang=%s", store_id, user_lang)
    place_id = request.args.get('place_id')
    name = request.args.get('name', '')
    lang = request.args.get('lang', 'en')
    
    # 使用新的翻譯服務進行語言碼正規化
    from .translation_service import normalize_lang, translate_text
    normalized_lang = normalize_lang(lang)
    
    try:
        store = None
        
        if store_id:
            # 使用 store_id 查詢
            current_app.logger.info(f"查詢店家 store_id={store_id}")
            store = Store.query.get(store_id)
            if store:
                current_app.logger.info(f"找到店家: {store.store_name}, partner_level={store.partner_level}")
            else:
                current_app.logger.warning(f"找不到店家 store_id={store_id}")
        elif place_id:
            # 使用 place_id 查詢
            current_app.logger.info(f"查詢店家 place_id={place_id}")
            store = Store.query.filter_by(place_id=place_id).first()
            if store:
                current_app.logger.info(f"找到店家: {store.store_name}, partner_level={store.partner_level}")
            else:
                current_app.logger.warning(f"找不到店家 place_id={place_id}")
        
        if store:
            # 找到店家
            original_name = store.store_name
            translated_name = translate_text(original_name, normalized_lang)
            
            # 合作店家判斷：只要 partner_level > 0 就是合作店家
            is_partner = store.partner_level > 0
            
            # 只有合作店家才檢查菜單
            has_menu = False
            translated_menu = []
            
            if is_partner:
                # 合作店家：檢查是否有菜單
                try:
                    menus = Menu.query.filter(Menu.store_id == store.store_id).all()
                    
                    if menus:
                        menu_ids = [menu.menu_id for menu in menus]
                        menu_items = MenuItem.query.filter(
                            MenuItem.menu_id.in_(menu_ids),
                            MenuItem.price_small > 0
                        ).all()
                        has_menu = len(menu_items) > 0
                        
                        # 如果有菜單項目，提供翻譯後的菜單
                        if menu_items:
                            for item in menu_items:
                                translated_item = {
                                    "id": item.menu_item_id,
                                    "name": translate_text(item.item_name, normalized_lang),
                                    "translated_name": translate_text(item.item_name, normalized_lang),  # 為了前端兼容性
                                    "original_name": item.item_name,
                                    "price_small": item.price_small,
                                    "price_large": item.price_big,  # 修正：使用 price_big 而不是 price_large
                                    "category": "",  # 修正：資料庫中沒有 category 欄位
                                    "original_category": ""
                                }
                                translated_menu.append(translated_item)
                except Exception as e:
                    current_app.logger.warning(f"檢查菜單時發生錯誤: {e}")
                    has_menu = False
            else:
                # 非合作店家：強制沒有菜單，必須使用拍照模式
                current_app.logger.info(f"非合作店家 {store.store_name} (partner_level={store.partner_level})，強制進入拍照模式")
                has_menu = False
                translated_menu = []
            
            response_data = {
                "store_id": store.store_id,
                "store_name": store.store_name,
                "display_name": translated_name,  # 前端優先使用的欄位
                "translated_name": translated_name,  # 前端也會檢查的欄位
                "original_name": original_name,
                "place_id": store.place_id,
                "partner_level": store.partner_level,
                "is_partner": is_partner,  # 合作店家判斷
                "has_menu": has_menu,
                "translated_menu": translated_menu,  # 提供翻譯後的菜單
                "supported_languages": ["zh", "en", "ja", "ko"],  # 支援的語言清單
                "auto_translate": True  # 若無語言時會自動翻譯
            }
        else:
            # 找不到店家，回傳非合作狀態
            original_name = name or f"店家_{place_id[:8] if place_id else 'unknown'}"
            translated_name = translate_text(original_name, normalized_lang)
            
            response_data = {
                "store_id": None,
                "store_name": "",
                "display_name": translated_name,  # 前端優先使用的欄位
                "translated_name": translated_name,  # 前端也會檢查的欄位
                "original_name": original_name,
                "place_id": place_id,
                "partner_level": 0,
                "is_partner": False,
                "has_menu": False
            }
        
        response = jsonify(response_data)
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Cache-Control', 'public, max-age=300')  # 5分鐘快取
        return response, 200
        
    except Exception as e:
        current_app.logger.error(f"檢查店家狀態失敗: {str(e)}")
        # 明確 fallback，避免 5xx 讓前端停在 loading
        original_name = name or f"店家_{place_id[:8] if place_id else 'unknown'}"
        translated_name = translate_text(original_name, normalized_lang)
        
        response_data = {
            "store_id": None,
            "store_name": "",
            "display_name": translated_name,  # 前端優先使用的欄位
            "translated_name": translated_name,  # 前端也會檢查的欄位
            "original_name": original_name,
            "place_id": place_id,
            "partner_level": 0,
            "is_partner": False,
            "has_menu": False,
            "error": "檢查店家狀態失敗，使用預設值"
        }
        
        response = jsonify(response_data)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200

@api_bp.route('/menu/process-ocr', methods=['POST', 'OPTIONS'])
def process_menu_ocr():
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    # 檢查是否有檔案
    if 'image' not in request.files:
        response = jsonify({'error': '沒有上傳檔案'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    
    file = request.files['image']
    
    # 檢查檔案名稱
    if file.filename == '':
        response = jsonify({'error': '沒有選擇檔案'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    
    # 檢查檔案格式
    if not allowed_file(file.filename):
        response = jsonify({'error': '不支援的檔案格式'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    
    # 取得參數
    raw_store_id = request.form.get('store_id')  # 可能是整數、數字字串或 Google Place ID
    user_id = request.form.get('user_id')  # 移除 type=int，因為前端傳遞的是字串格式的 LINE 用戶 ID
    target_lang = request.form.get('lang', 'en')
    
    # 新增：簡化模式參數
    simple_mode = request.form.get('simple_mode', 'false').lower() == 'true'
    
    if not raw_store_id:
        response = jsonify({"error": "需要提供店家ID"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    
    # 使用 store resolver 解析店家 ID
    try:
        from .store_resolver import resolve_store_id
        store_db_id = resolve_store_id(raw_store_id)
        print(f"✅ 店家ID解析成功: {raw_store_id} -> {store_db_id}")
    except Exception as e:
        print(f"❌ 店家ID解析失敗: {e}")
        response = jsonify({
            "error": "店家ID格式錯誤",
            "details": str(e),
            "received_store_id": raw_store_id
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    
    try:
        # 儲存上傳的檔案
        filepath = save_uploaded_file(file)
        
        # 先處理圖片獲取店家資訊
        print("開始使用 Gemini API 處理圖片...")
        result = process_menu_with_gemini(filepath, target_lang)
        
        # 檢查處理結果
        if result and result.get('success', False):
            # 處理 user_id - 使用 LINE 用戶 ID 或創建臨時使用者
            if user_id:
                # 檢查是否已存在該 LINE 用戶
                existing_user = User.query.filter_by(line_user_id=user_id).first()
                if existing_user:
                    actual_user_id = existing_user.user_id
                    print(f"✅ 使用現有使用者，ID: {actual_user_id} (LINE ID: {user_id})")
                else:
                    # 創建新使用者
                    new_user = User(
                        line_user_id=user_id,
                        preferred_lang=target_lang or 'zh'
                    )
                    db.session.add(new_user)
                    db.session.flush()  # 獲取 user_id
                    actual_user_id = new_user.user_id
                    print(f"✅ 創建新使用者，ID: {actual_user_id} (LINE ID: {user_id})")
            else:
                # 沒有提供 user_id，創建臨時使用者
                temp_user = User(
                    line_user_id=f"temp_guest_{int(time.time())}",
                    preferred_lang=target_lang or 'zh'
                )
                db.session.add(temp_user)
                db.session.flush()  # 獲取 user_id
                actual_user_id = temp_user.user_id
                print(f"✅ 創建臨時使用者，ID: {actual_user_id}")
            
            # 建立 OCR 菜單記錄（使用解析後的整數 store_id）
            ocr_menu = OCRMenu(
                user_id=actual_user_id,
                store_id=store_db_id,  # 使用解析後的 store_db_id
                store_name=result.get('store_info', {}).get('name', '臨時店家')
            )
            db.session.add(ocr_menu)
            db.session.flush()  # 獲取 ocr_menu_id
            
            # 儲存菜單項目到資料庫
            menu_items = result.get('menu_items', [])
            dynamic_menu = []
            
            for i, item in enumerate(menu_items):
                # 儲存到 ocr_menu_items 表
                ocr_menu_item = OCRMenuItem(
                    ocr_menu_id=ocr_menu.ocr_menu_id,
                    item_name=str(item.get('original_name', '') or ''),
                    price_small=item.get('price', 0),
                    price_big=item.get('price', 0),  # 使用相同價格
                    translated_desc=str(item.get('translated_name', '') or '')
                )
                db.session.add(ocr_menu_item)
                
                # 根據模式生成不同的菜單資料
                if simple_mode:
                    # 簡化模式：只包含必要欄位
                    dynamic_menu.append({
                        'id': f"ocr_{ocr_menu.ocr_menu_id}_{i}",
                        'name': str(item.get('original_name', '') or ''),
                        'translated_name': str(item.get('translated_name', '') or ''),
                        'price': item.get('price', 0),
                        'description': str(item.get('description', '') or ''),
                        'category': str(item.get('category', '') or '其他')
                    })
                else:
                    # 完整模式：包含所有前端相容欄位
                    dynamic_menu.append({
                        'temp_id': f"temp_{ocr_menu.ocr_menu_id}_{i}",
                        'id': f"temp_{ocr_menu.ocr_menu_id}_{i}",
                        'original_name': str(item.get('original_name', '') or ''),
                        'translated_name': str(item.get('translated_name', '') or ''),
                        'en_name': str(item.get('translated_name', '') or ''),
                        'price': item.get('price', 0),
                        'price_small': item.get('price', 0),
                        'price_large': item.get('price', 0),
                        'description': str(item.get('description', '') or ''),
                        'category': str(item.get('category', '') or '其他'),
                        'image_url': '/static/images/default-dish.png',
                        'imageUrl': '/static/images/default-dish.png',
                        'show_image': False,  # 控制是否顯示圖片框框
                        'inventory': 999,
                        'available': True,
                        'processing_id': ocr_menu.ocr_menu_id
                    })
            
            # 提交資料庫變更
            db.session.commit()
            
            # 根據模式準備回應資料
            if simple_mode:
                # 簡化模式回應
                response_data = {
                    "success": True,
                    "menu_items": dynamic_menu,
                    "store_name": result.get('store_info', {}).get('name', '臨時店家'),
                    "target_language": target_lang,
                    "processing_notes": result.get('processing_notes', ''),
                    "ocr_menu_id": ocr_menu.ocr_menu_id,
                    "saved_to_database": True
                }
            else:
                # 完整模式回應
                response_data = {
                    "message": "菜單處理成功",
                    "processing_id": ocr_menu.ocr_menu_id,
                    "store_info": result.get('store_info', {}),
                    "menu_items": dynamic_menu,
                    "total_items": len(dynamic_menu),
                    "target_language": target_lang,
                    "processing_notes": result.get('processing_notes', ''),
                    "ocr_menu_id": ocr_menu.ocr_menu_id,
                    "saved_to_database": True
                }
            
            response = jsonify(response_data)
            response.headers.add('Access-Control-Allow-Origin', '*')
            
            # 加入 API 回應的除錯 log
            mode_text = "簡化模式" if simple_mode else "完整模式"
            print(f"🎉 API 成功回應 201 Created ({mode_text})")
            print(f"📊 回應統計:")
            print(f"  - OCR菜單ID: {ocr_menu.ocr_menu_id}")
            print(f"  - 菜單項目數: {len(dynamic_menu)}")
            print(f"  - 目標語言: {target_lang}")
            print(f"  - 回應模式: {mode_text}")
            print(f"  - 店家資訊: {result.get('store_info', {})}")
            print(f"  - 處理備註: {result.get('processing_notes', '')}")
            print(f"  - 已儲存到資料庫: True")
            
            return response, 201
        else:
            # 檢查是否是 JSON 解析錯誤或其他可恢復的錯誤
            error_message = result.get('error', '菜單處理失敗，請重新拍攝清晰的菜單照片')
            processing_notes = result.get('processing_notes', '')
            
            # 如果是 JSON 解析錯誤或其他可恢復的錯誤，返回 422
            if 'JSON 解析失敗' in error_message or 'extra_forbidden' in error_message:
                print(f"❌ API 返回 422 錯誤")
                print(f"🔍 錯誤詳情:")
                print(f"  - 錯誤訊息: {error_message}")
                print(f"  - 處理備註: {processing_notes}")
                print(f"  - 處理ID: 無")
                
                response = jsonify({
                    "error": error_message,
                    "processing_notes": processing_notes
                })
                response.headers.add('Access-Control-Allow-Origin', '*')
                return response, 422
            else:
                # 其他錯誤返回 500
                print(f"❌ API 返回 500 錯誤")
                print(f"🔍 錯誤詳情:")
                print(f"  - 錯誤訊息: {error_message}")
                print(f"  - 處理備註: {processing_notes}")
                print(f"  - 處理ID: 無")
                
                response = jsonify({
                    "error": error_message,
                    "processing_notes": processing_notes
                })
                response.headers.add('Access-Control-Allow-Origin', '*')
                return response, 500
                
    except Exception as e:
        print(f"❌ 處理過程中發生錯誤: {e}")
        response = jsonify({
            "error": "處理過程中發生錯誤",
            "details": str(e) if current_app.debug else '請稍後再試'
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@api_bp.route('/orders', methods=['POST', 'OPTIONS'])
def create_order():
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "請求資料為空"}), 400
    
    # 檢查必要欄位
    required_fields = ['items']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({
            "error": "訂單資料不完整",
            "missing_fields": missing_fields,
            "received_data": list(data.keys())
        }), 400
    
    try:
        # 處理 line_user_id（可選）
        line_user_id = data.get('line_user_id')
        if not line_user_id:
            # 為非 LINE 入口生成臨時 ID
            line_user_id = f"guest_{uuid.uuid4().hex[:8]}"
            guest_mode = True
        else:
            guest_mode = False

        # 查找或創建使用者
        user = User.query.filter_by(line_user_id=line_user_id).first()
        if not user:
            try:
                # 檢查語言是否存在，如果不存在就使用預設語言
                preferred_lang = data.get('language', 'zh')
                language = Language.query.get(preferred_lang)
                if not language:
                    # 如果指定的語言不存在，使用中文作為預設
                    preferred_lang = 'zh'
                    language = Language.query.get(preferred_lang)
                    if not language:
                        # 如果連中文都不存在，創建基本語言資料
                        from tools.manage_translations import init_languages
                        init_languages()
                
                # 為訪客創建臨時使用者
                user = User(
                    line_user_id=line_user_id,
                    preferred_lang=preferred_lang
                )
                db.session.add(user)
                db.session.flush()  # 先產生 user_id，但不提交
            except Exception as e:
                db.session.rollback()
                return jsonify({
                    "error": "建立使用者失敗",
                    "details": str(e)
                }), 500

        # 先解析 store_id，確保後續所有操作都使用正確的整數 ID
        raw_store_id = data.get('store_id', 1)
        
        # 先進行格式驗證
        from .store_resolver import validate_store_id_format, safe_resolve_store_id
        
        if not validate_store_id_format(raw_store_id):
            return jsonify({
                "error": "訂單資料驗證失敗",
                "validation_errors": [f"無效的 store_id 格式: {raw_store_id}"],
                "received_data": {"store_id": raw_store_id}
            }), 400
        
        # 保存前端傳遞的店家名稱
        frontend_store_name = data.get('store_name')
        print(f"📋 前端傳遞的店家名稱: {frontend_store_name}")
        print(f"📋 前端傳遞的原始store_id: {raw_store_id}")
        print(f"📋 前端傳遞的完整資料: {data}")
        
        try:
            store_db_id = safe_resolve_store_id(raw_store_id, frontend_store_name, default_id=1)
            print(f"✅ 訂單店家ID解析成功: {raw_store_id} -> {store_db_id}")
            
            # 查詢店家資料庫記錄
            store_record = Store.query.get(store_db_id)
            if store_record:
                print(f"📋 資料庫店家記錄: store_id={store_record.store_id}, store_name='{store_record.store_name}', partner_level={store_record.partner_level}")
            else:
                print(f"❌ 找不到店家記錄: store_id={store_db_id}")
                
        except Exception as e:
            print(f"❌ 訂單店家ID解析失敗: {e}")
            # 如果解析失敗，使用預設值
            store_db_id = 1
            print(f"⚠️ 使用預設店家ID: {store_db_id}")
        
        total_amount = 0
        order_items_to_create = []
        order_details = []
        validation_errors = []
        ocr_menu_id = None
        
        for i, item_data in enumerate(data['items']):
            # 支援多種欄位名稱格式
            menu_item_id = item_data.get('menu_item_id') or item_data.get('id')
            quantity = item_data.get('quantity') or item_data.get('qty') or item_data.get('quantity_small')
            
            # 將 menu_item_id 轉換為字串以便檢查前綴
            menu_item_id_str = str(menu_item_id) if menu_item_id is not None else None
            
            # 檢查是否為OCR菜單項目（以 ocr_ 開頭）
            if menu_item_id_str and menu_item_id_str.startswith('ocr_'):
                # 處理OCR菜單項目
                price = item_data.get('price') or item_data.get('price_small') or item_data.get('price_unit') or 0
                
                # 處理新的雙語格式 {name: {original: "中文", translated: "English"}}
                if item_data.get('name') and isinstance(item_data['name'], dict):
                    item_name = item_data['name'].get('original') or f"項目 {i+1}"
                    translated_name = item_data['name'].get('translated') or item_name
                else:
                    item_name = item_data.get('item_name') or item_data.get('name') or item_data.get('original_name') or f"項目 {i+1}"
                    translated_name = item_data.get('translated_name') or item_data.get('en_name') or item_name
                
                # 提取OCR菜單ID
                if not ocr_menu_id:
                    parts = menu_item_id_str.split('_')
                    if len(parts) >= 3:
                        ocr_menu_id = int(parts[1])
                
                # 驗證數量
                if not quantity:
                    validation_errors.append(f"項目 {i+1}: 缺少 quantity 或 qty 欄位")
                    continue
                
                try:
                    quantity = int(quantity)
                    if quantity <= 0:
                        validation_errors.append(f"項目 {i+1}: 數量必須大於 0")
                        continue
                except (ValueError, TypeError):
                    validation_errors.append(f"項目 {i+1}: 數量格式錯誤，必須是整數")
                    continue
                
                # 計算小計
                subtotal = int(price) * quantity
                total_amount += subtotal
                
                # 為OCR項目創建一個臨時的 MenuItem 記錄
                try:
                    # 檢查是否已經有對應的臨時菜單項目
                    temp_menu_item = MenuItem.query.filter_by(item_name=item_name).first()
                    
                    if not temp_menu_item:
                        # 創建新的臨時菜單項目
                        from app.models import Menu
                        
                        # 找到或創建一個臨時菜單
                        # 修正：使用解析後的 store_db_id 而不是原始的 store_id
                        temp_menu = Menu.query.filter_by(store_id=store_db_id).first()
                        if not temp_menu:
                            temp_menu = Menu(
                                store_id=store_db_id, 
                                version=1,
                                effective_date=datetime.datetime.now()  # 明確設置 effective_date
                            )
                            db.session.add(temp_menu)
                            db.session.flush()
                        
                        temp_menu_item = MenuItem(
                            menu_id=temp_menu.menu_id,
                            item_name=item_name,
                            price_small=int(price),
                            price_big=int(price)  # 使用相同價格
                        )
                        db.session.add(temp_menu_item)
                        db.session.flush()  # 獲取 menu_item_id
                    
                    # 使用臨時菜單項目的 ID
                    order_items_to_create.append(OrderItem(
                        menu_item_id=temp_menu_item.menu_item_id,
                        quantity_small=quantity,
                        subtotal=subtotal,
                        original_name=item_name,
                        translated_name=translated_name
                    ))
                    
                    # 建立訂單明細供確認
                    order_details.append({
                        'menu_item_id': temp_menu_item.menu_item_id,
                        'item_name': item_name,
                        'translated_name': translated_name,
                        'quantity': quantity,
                        'price': int(price),
                        'subtotal': subtotal,
                        'is_ocr': True
                    })
                    
                except Exception as e:
                    validation_errors.append(f"項目 {i+1}: 創建OCR菜單項目失敗 - {str(e)}")
                    continue
            # 檢查是否為臨時菜單項目（以 temp_ 開頭）
            elif menu_item_id_str and menu_item_id_str.startswith('temp_'):
                # 處理臨時菜單項目
                price = item_data.get('price') or item_data.get('price_small') or item_data.get('price_unit') or 0
                item_name = item_data.get('item_name') or item_data.get('name') or item_data.get('original_name') or f"項目 {i+1}"
                
                # 驗證數量
                if not quantity:
                    validation_errors.append(f"項目 {i+1}: 缺少 quantity 或 qty 欄位")
                    continue
                
                try:
                    quantity = int(quantity)
                    if quantity <= 0:
                        validation_errors.append(f"項目 {i+1}: 數量必須大於 0")
                        continue
                except (ValueError, TypeError):
                    validation_errors.append(f"項目 {i+1}: 數量格式錯誤，必須是整數")
                    continue
                
                # 計算小計
                subtotal = int(price) * quantity
                total_amount += subtotal
                
                # 為臨時項目創建一個臨時的 MenuItem 記錄
                try:
                    # 檢查是否已經有對應的臨時菜單項目
                    temp_menu_item = MenuItem.query.filter_by(item_name=item_name).first()
                    
                    if not temp_menu_item:
                        # 創建新的臨時菜單項目
                        from app.models import Menu
                        
                        # 找到或創建一個臨時菜單
                        # 修正：使用解析後的 store_db_id 而不是原始的 store_id
                        temp_menu = Menu.query.filter_by(store_id=store_db_id).first()
                        if not temp_menu:
                            temp_menu = Menu(
                                store_id=store_db_id, 
                                version=1,
                                effective_date=datetime.datetime.now()  # 明確設置 effective_date
                            )
                            db.session.add(temp_menu)
                            db.session.flush()
                        
                        temp_menu_item = MenuItem(
                            menu_id=temp_menu.menu_id,
                            item_name=item_name,
                            price_small=int(price),
                            price_big=int(price)  # 使用相同價格
                        )
                        db.session.add(temp_menu_item)
                        db.session.flush()  # 獲取 menu_item_id
                    
                    # 使用臨時菜單項目的 ID
                    order_items_to_create.append(OrderItem(
                        menu_item_id=temp_menu_item.menu_item_id,
                        quantity_small=quantity,
                        subtotal=subtotal,
                        original_name=item_name,        # 設定中文原始名稱
                        translated_name=item_name       # 設定翻譯名稱（預設相同）
                    ))
                    
                    # 建立訂單明細供確認
                    order_details.append({
                        'menu_item_id': temp_menu_item.menu_item_id,
                        'item_name': item_name,
                        'quantity': quantity,
                        'price': int(price),
                        'subtotal': subtotal,
                        'is_temp': True
                    })
                    
                except Exception as e:
                    validation_errors.append(f"項目 {i+1}: 創建臨時菜單項目失敗 - {str(e)}")
                    continue
            else:
                # 處理正式菜單項目（合作店家）
                if not menu_item_id:
                    validation_errors.append(f"項目 {i+1}: 缺少 menu_item_id 或 id 欄位")
                    continue
                    
                if not quantity:
                    validation_errors.append(f"項目 {i+1}: 缺少 quantity 或 qty 欄位")
                    continue
                
                try:
                    quantity = int(quantity)
                    if quantity <= 0:
                        validation_errors.append(f"項目 {i+1}: 數量必須大於 0")
                        continue
                except (ValueError, TypeError):
                    validation_errors.append(f"項目 {i+1}: 數量格式錯誤，必須是整數")
                    continue
                
                menu_item = MenuItem.query.get(menu_item_id)
                if not menu_item:
                    # 提供更詳細的錯誤訊息，包括可能的正確 ID
                    print(f"❌ 找不到菜單項目 ID {menu_item_id}")
                    
                    # 嘗試找到相似的菜單項目
                    similar_items = MenuItem.query.filter(
                        MenuItem.item_name.like(f"%{item_data.get('item_name', '')}%")
                    ).limit(5).all()
                    
                    error_msg = f"項目 {i+1}: 找不到菜單項目 ID {menu_item_id}"
                    if similar_items:
                        similar_ids = [str(item.menu_item_id) for item in similar_items]
                        error_msg += f" (可能的正確 ID: {', '.join(similar_ids)})"
                    
                    validation_errors.append(error_msg)
                    continue
                
                subtotal = menu_item.price_small * quantity
                total_amount += subtotal
                
                order_items_to_create.append(OrderItem(
                    menu_item_id=menu_item.menu_item_id,
                    quantity_small=quantity,
                    subtotal=subtotal,
                    original_name=menu_item.item_name,  # 設定中文原始名稱
                    translated_name=menu_item.item_name  # 設定翻譯名稱（預設相同）
                ))
                
                # 建立訂單明細供確認
                order_details.append({
                    'menu_item_id': menu_item.menu_item_id,
                    'item_name': menu_item.item_name,
                    'quantity': quantity,
                    'price': menu_item.price_small,
                    'subtotal': subtotal,
                    'is_temp': False
                })

        if validation_errors:
            print(f"❌ 訂單資料驗證失敗: {validation_errors}")
            return jsonify({
                "error": "訂單資料驗證失敗",
                "validation_errors": validation_errors,
                "received_data": {
                    "store_id": raw_store_id,
                    "store_name": frontend_store_name,
                    "items_count": len(data.get('items', [])),
                    "items": data.get('items', [])
                },
                "debug_info": {
                    "resolved_store_id": store_db_id,
                    "user_id": user.user_id if user else None
                }
            }), 400

        if not order_items_to_create:
            return jsonify({
                "error": "沒有選擇任何商品",
                "received_items": data['items']
            }), 400

        try:
            # store_id 已經在前面解析過了，這裡直接使用 store_db_id
            
            # 記錄訂單創建SQL
            import logging
            from sqlalchemy import text
            logging.basicConfig(level=logging.INFO)
            
            print(f"📝 準備創建訂單記錄...")
            print(f"📋 訂單參數:")
            print(f"   user_id: {user.user_id} (型態: {type(user.user_id)})")
            print(f"   store_id: {store_db_id} (型態: {type(store_db_id)})")
            print(f"   total_amount: {total_amount} (型態: {type(total_amount)})")
            print(f"   frontend_store_name: {frontend_store_name} (型態: {type(frontend_store_name)})")
            
            # 查詢使用者資料
            user_record = User.query.get(user.user_id)
            if user_record:
                print(f"📋 使用者資料: user_id={user_record.user_id}, line_user_id='{user_record.line_user_id}', preferred_lang='{user_record.preferred_lang}'")
            else:
                print(f"❌ 找不到使用者記錄: user_id={user.user_id}")
            
            # 使用原生SQL創建訂單
            order_sql = """
            INSERT INTO orders (user_id, store_id, total_amount, order_time, status)
            VALUES (:user_id, :store_id, :total_amount, :order_time, :status)
            """
            
            order_params = {
                "user_id": user.user_id,
                "store_id": store_db_id,
                "total_amount": total_amount,
                "order_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "pending"
            }
            
            print(f"📋 SQL參數詳細資訊:")
            for key, value in order_params.items():
                print(f"   {key}: {value} (型態: {type(value)})")
            
            logging.info(f"Executing Order SQL: {order_sql}")
            logging.info(f"With parameters: {order_params}")
            
            try:
                result = db.session.execute(text(order_sql), order_params)
                db.session.commit()
                print(f"✅ SQL執行成功，影響行數: {result.rowcount}")
            except Exception as sql_error:
                print(f"❌ SQL執行失敗: {sql_error}")
                print(f"錯誤類型: {type(sql_error).__name__}")
                import traceback
                traceback.print_exc()
                raise sql_error
            
            # 獲取訂單ID
            order_id_result = db.session.execute(text("SELECT LAST_INSERT_ID() as id"))
            order_id = order_id_result.fetchone()[0]
            
            print(f"✅ 訂單已創建，ID: {order_id}")
            
            # 創建訂單項目
            print(f"📝 準備創建 {len(order_items_to_create)} 個訂單項目...")
            for i, order_item in enumerate(order_items_to_create):
                print(f"📋 處理訂單項目 {i+1}:")
                print(f"   menu_item_id: {order_item.menu_item_id}")
                print(f"   quantity_small: {order_item.quantity_small}")
                print(f"   subtotal: {order_item.subtotal}")
                print(f"   original_name: {order_item.original_name}")
                print(f"   translated_name: {order_item.translated_name}")
                
                order_item_sql = """
                INSERT INTO order_items (order_id, menu_item_id, quantity_small, subtotal, original_name, translated_name, created_at)
                VALUES (:order_id, :menu_item_id, :quantity_small, :subtotal, :original_name, :translated_name, :created_at)
                """
                
                order_item_params = {
                    "order_id": order_id,
                    "menu_item_id": order_item.menu_item_id,
                    "quantity_small": order_item.quantity_small,
                    "subtotal": order_item.subtotal,
                    "original_name": order_item.original_name or '',
                    "translated_name": order_item.translated_name or '',
                    "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                logging.info(f"Executing Order Item {i+1} SQL: {order_item_sql}")
                logging.info(f"With parameters: {order_item_params}")
                
                db.session.execute(text(order_item_sql), order_item_params)
            
            db.session.commit()
            print(f"✅ 已創建 {len(order_items_to_create)} 個訂單項目")
            
            # 創建Order物件用於後續處理
            new_order = Order()
            new_order.order_id = order_id
            new_order.user_id = user.user_id
            new_order.store_id = store_db_id
            new_order.total_amount = total_amount
            
            print(f"📋 訂單物件資訊:")
            print(f"   order_id: {new_order.order_id}")
            print(f"   user_id: {new_order.user_id}")
            print(f"   store_id: {new_order.store_id}")
            print(f"   total_amount: {new_order.total_amount}")
            print(f"   frontend_store_name: {frontend_store_name}")
            
            # 建立完整訂單確認內容
            from .helpers import create_complete_order_confirmation, send_complete_order_notification, generate_voice_order
            
            print(f"🔧 準備生成訂單確認...")
            print(f"📋 訂單ID: {new_order.order_id}")
            print(f"📋 用戶偏好語言: {user.preferred_lang}")
            
            try:
                order_confirmation = create_complete_order_confirmation(new_order.order_id, user.preferred_lang, frontend_store_name)
                print(f"✅ 訂單確認生成成功")
                print(f"📋 確認內容: {order_confirmation}")
            except Exception as e:
                print(f"❌ 訂單確認生成失敗: {e}")
                print(f"錯誤類型: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                raise e
            
            # 生成中文語音檔
            print(f"🔧 準備生成語音檔...")
            voice_path = None
            try:
                voice_path = generate_voice_order(new_order.order_id)
                print(f"✅ 語音檔生成成功: {voice_path}")
            except Exception as e:
                print(f"❌ 語音檔生成失敗: {e}")
                print(f"錯誤類型: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                # 不拋出異常，繼續執行
                voice_path = None
            
            # 如果是OCR菜單訂單，建立訂單摘要並儲存到資料庫
            if ocr_menu_id:
                try:
                    from .helpers import save_ocr_menu_and_summary_to_database
                    
                    # 準備OCR項目資料
                    ocr_items = []
                    for item in order_details:
                        if item.get('is_ocr'):
                            ocr_items.append({
                                'name': {
                                    'original': item.get('item_name', ''),
                                    'translated': item.get('translated_name', item.get('item_name', ''))
                                },
                                'price': item.get('price', 0),
                                'item_name': item.get('item_name', ''),
                                'translated_name': item.get('translated_name', item.get('item_name', ''))
                            })
                    
                    if ocr_items:
                        # 儲存到資料庫
                        save_result = save_ocr_menu_and_summary_to_database(
                            order_id=new_order.order_id,
                            ocr_items=ocr_items,
                            chinese_summary=order_confirmation.get('chinese', 'OCR訂單摘要'),
                            user_language_summary=order_confirmation.get('translated', 'OCR訂單摘要'),
                            user_language=data.get('language', 'zh'),
                            total_amount=total_amount,
                            user_id=user.user_id if user else None,
                            store_id=store_db_id,  # 新增 store_id
                            store_name=data.get('store_name', 'OCR店家'),
                            existing_ocr_menu_id=ocr_menu_id
                        )
                        
                        if save_result['success']:
                            print(f"✅ OCR訂單摘要已成功儲存到資料庫")
                            print(f"   OCR菜單ID: {save_result['ocr_menu_id']}")
                            print(f"   訂單摘要ID: {save_result['summary_id']}")
                        else:
                            print(f"⚠️ OCR訂單摘要儲存失敗: {save_result['message']}")
                except Exception as e:
                    print(f"⚠️ 儲存OCR訂單摘要時發生錯誤: {e}")
                    # 不影響主要流程，繼續執行
                
                # 只在非訪客模式下發送 LINE 通知
                if not guest_mode:
                    send_complete_order_notification(new_order.order_id, frontend_store_name)
                
                return jsonify({
                    "message": "訂單建立成功", 
                    "order_id": new_order.order_id,
                    "order_details": order_details,
                    "total_amount": total_amount,
                    "confirmation": order_confirmation,
                    "voice_generated": voice_path is not None,
                    "ocr_menu_id": ocr_menu_id
                }), 201
            
            # 如果不是OCR菜單訂單，也需要返回成功響應
            else:
                # 只在非訪客模式下發送 LINE 通知
                if not guest_mode:
                    send_complete_order_notification(new_order.order_id, frontend_store_name)
                
                return jsonify({
                    "message": "訂單建立成功", 
                    "order_id": new_order.order_id,
                    "order_details": order_details,
                    "total_amount": total_amount,
                    "confirmation": order_confirmation,
                    "voice_generated": voice_path is not None
                }), 201
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_traceback = traceback.format_exc()
            print(f"❌ 訂單建立失敗: {str(e)}")
            print(f"❌ 錯誤追蹤: {error_traceback}")
            return jsonify({
                "error": "訂單建立失敗",
                "details": str(e),
                "traceback": error_traceback,
                "debug_info": {
                    "store_id": store_db_id,
                    "user_id": user.user_id if user else None,
                    "items_count": len(order_items_to_create),
                    "total_amount": total_amount
                }
            }), 500
        
    except Exception as e:
        db.session.rollback()
        import traceback
        error_traceback = traceback.format_exc()
        print(f"❌ 訂單建立失敗（外層異常）: {str(e)}")
        print(f"❌ 錯誤追蹤: {error_traceback}")
        return jsonify({
            "error": "訂單建立失敗",
            "details": str(e),
            "traceback": error_traceback
        }), 500

@api_bp.route('/orders/temp', methods=['POST', 'OPTIONS'])
def create_temp_order():
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    """建立臨時訂單（非合作店家）"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "請求資料為空"}), 400
    
    # 檢查必要欄位
    required_fields = ['items']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({
            "error": "訂單資料不完整",
            "missing_fields": missing_fields,
            "received_data": list(data.keys())
        }), 400
    
    try:
        # 處理 line_user_id（可選）
        line_user_id = data.get('line_user_id')
        if not line_user_id:
            # 為非 LINE 入口生成臨時 ID
            line_user_id = f"guest_{uuid.uuid4().hex[:8]}"
            guest_mode = True
        else:
            guest_mode = False

        # 查找或創建使用者
        user = User.query.filter_by(line_user_id=line_user_id).first()
        if not user:
            try:
                # 檢查語言是否存在，如果不存在就使用預設語言
                preferred_lang = data.get('language', 'zh')
                language = Language.query.get(preferred_lang)
                if not language:
                    # 如果指定的語言不存在，使用中文作為預設
                    preferred_lang = 'zh'
                    language = Language.query.get(preferred_lang)
                    if not language:
                        # 如果連中文都不存在，創建基本語言資料
                        from tools.manage_translations import init_languages
                        init_languages()
                
                # 為訪客創建臨時使用者
                user = User(
                    line_user_id=line_user_id,
                    preferred_lang=preferred_lang
                )
                db.session.add(user)
                db.session.flush()  # 先產生 user_id，但不提交
            except Exception as e:
                db.session.rollback()
                return jsonify({
                    "error": "建立使用者失敗",
                    "details": str(e)
                }), 500

        # 驗證訂單項目
        order_items = []
        total_amount = 0
        validation_errors = []
        
        for i, item_data in enumerate(data['items']):
            # 支援多種欄位名稱格式
            item_name = item_data.get('item_name') or item_data.get('name') or item_data.get('original_name') or f"項目 {i+1}"
            quantity = item_data.get('quantity') or item_data.get('qty') or item_data.get('quantity_small') or 1
            price = item_data.get('price') or item_data.get('price_small') or item_data.get('price_unit') or 0
            
            try:
                quantity = int(quantity)
                price = float(price)
                if quantity <= 0:
                    validation_errors.append(f"項目 {i+1}: 數量必須大於 0")
                    continue
                if price < 0:
                    validation_errors.append(f"項目 {i+1}: 價格不能為負數")
                    continue
            except (ValueError, TypeError):
                validation_errors.append(f"項目 {i+1}: 數量或價格格式錯誤")
                continue
            
            subtotal = int(price * quantity)
            total_amount += subtotal
            
            order_items.append({
                'item_name': item_name,
                'quantity': quantity,
                'price': price,
                'subtotal': subtotal
            })

        if validation_errors:
            return jsonify({
                "error": "訂單資料驗證失敗",
                "validation_errors": validation_errors,
                "received_items": data['items']
            }), 400

        if not order_items:
            return jsonify({
                "error": "沒有選擇任何商品",
                "received_items": data['items']
            }), 400

        # 創建臨時訂單記錄（不依賴複雜的資料庫結構）
        temp_order_id = f"temp_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{user.user_id}"
        
        # 建立完整訂單確認內容
        from .helpers import create_complete_order_confirmation, send_complete_order_notification, generate_voice_order
        
        # 創建訂單摘要
        order_summary = {
            'order_id': temp_order_id,
            'user_id': user.user_id,
            'items': order_items,
            'total_amount': total_amount,
            'order_time': datetime.datetime.utcnow().isoformat(),
            'status': 'pending'
        }
        
        # 生成語音檔（可選）
        voice_path = None
        try:
            # 這裡可以生成語音檔，但不需要依賴資料庫
            voice_path = f"/temp_voice/{temp_order_id}.mp3"
        except Exception as e:
            print(f"語音生成失敗: {e}")
        
        # 只在非訪客模式下發送 LINE 通知
        if not guest_mode:
            try:
                from .helpers import send_complete_order_notification_optimized
                send_complete_order_notification_optimized(temp_order_id)
            except Exception as e:
                print(f"LINE 通知發送失敗: {e}")
        
        # 儲存 OCR 菜單和訂單摘要到資料庫（新增功能）
        try:
            from .helpers import save_ocr_menu_and_summary_to_database
            
            # 檢查是否為 OCR 菜單訂單
            if order_items and any(item.get('item_name') for item in order_items):
                print("🔄 檢測到臨時 OCR 菜單訂單，開始儲存到資料庫...")
                
                # 準備 OCR 項目資料
                ocr_items = []
                for item in order_items:
                    if item.get('item_name'):  # 只處理有菜名的項目
                        ocr_items.append({
                            'name': {
                                'original': item.get('item_name', ''),
                                'translated': item.get('item_name', '')
                            },
                            'price': item.get('price', 0),
                            'item_name': item.get('item_name', ''),
                            'translated_name': item.get('item_name', '')
                        })
                
                if ocr_items:
                    # 儲存到資料庫
                    save_result = save_ocr_menu_and_summary_to_database(
                        order_id=temp_order_id,
                        ocr_items=ocr_items,
                        chinese_summary=order_summary.get('summary', '臨時訂單摘要'),
                        user_language_summary=order_summary.get('summary', '臨時訂單摘要'),
                        user_language=data.get('language', 'zh'),
                        total_amount=total_amount,
                        user_id=user.user_id if user else None,
                        store_id=None,  # 臨時訂單沒有 store_id
                        store_name=data.get('store_id', '非合作店家')
                    )
                    
                    if save_result['success']:
                        print(f"✅ 臨時 OCR 菜單和訂單摘要已成功儲存到資料庫")
                        print(f"   OCR 菜單 ID: {save_result['ocr_menu_id']}")
                        print(f"   訂單摘要 ID: {save_result['summary_id']}")
                    else:
                        print(f"⚠️ 臨時 OCR 菜單和訂單摘要儲存失敗: {save_result['message']}")
                else:
                    print("ℹ️ 沒有 OCR 項目需要儲存")
            else:
                print("ℹ️ 此臨時訂單不是 OCR 菜單訂單，跳過資料庫儲存")
        except Exception as e:
            print(f"⚠️ 儲存臨時 OCR 菜單和訂單摘要時發生錯誤: {e}")
            # 不影響主要流程，繼續執行
        
        return jsonify({
            "message": "臨時訂單建立成功", 
            "order_id": temp_order_id,
            "order_details": order_items,
            "total_amount": total_amount,
            "voice_generated": voice_path is not None,
            "order_summary": order_summary
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "臨時訂單建立失敗",
            "details": str(e)
        }), 500

@api_bp.route('/orders/<int:order_id>/confirm', methods=['GET'])
def get_order_confirmation(order_id):
    """取得訂單確認資訊"""
    try:
        from ..models import Order, OrderItem, MenuItem, Store, User
        
        order = Order.query.get(order_id)
        if not order:
            return jsonify({"error": "找不到訂單"}), 404
        
        store = Store.query.get(order.store_id)
        user = User.query.get(order.user_id)
        
        # 建立訂單明細
        order_details = []
        for item in order.items:
            menu_item = MenuItem.query.get(item.menu_item_id)
            if menu_item:
                order_details.append({
                    'item_name': menu_item.item_name,
                    'quantity': item.quantity_small,
                    'price': menu_item.price_small,
                    'subtotal': item.subtotal
                })
        
        # 建立完整訂單確認內容
        from .helpers import create_complete_order_confirmation
        confirmation = create_complete_order_confirmation(order_id, user.preferred_lang)
        
        return jsonify({
            "order_id": order.order_id,
            "store_name": store.store_name,
            "order_details": order_details,
            "total_amount": order.total_amount,
            "order_time": order.order_time.isoformat(),
            "confirmation": confirmation
        })
        
    except Exception as e:
        return jsonify({"error": "取得訂單確認資訊失敗"}), 500

@api_bp.route('/orders/<int:order_id>/voice', methods=['GET'])
def get_order_voice(order_id):
    """取得訂單語音檔"""
    try:
        from .helpers import generate_voice_order
        
        # 檢查訂單是否存在
        order = Order.query.get(order_id)
        if not order:
            return jsonify({"error": "找不到訂單"}), 404
        
        # 取得語速參數
        speech_rate = request.args.get('rate', 1.0, type=float)
        speech_rate = max(0.5, min(2.0, speech_rate))  # 限制語速範圍 0.5-2.0
        
        # 生成語音檔
        voice_path = generate_voice_order(order_id, speech_rate)
        
        if voice_path and os.path.exists(voice_path):
            # 構建語音檔 URL
            fname = os.path.basename(voice_path)
            from ..config import URLConfig
            audio_url = URLConfig.get_voice_url(fname)
            
            return jsonify({
                "success": True,
                "voice_url": audio_url,
                "filename": fname,
                "message": "語音檔生成成功"
            })
        else:
            return jsonify({"error": "語音檔生成失敗"}), 500
            
    except Exception as e:
        return jsonify({"error": "取得語音檔失敗"}), 500

@api_bp.route('/orders/history', methods=['GET'])
def get_order_history():
    """取得使用者訂單記錄"""
    try:
        line_user_id = request.args.get('line_user_id')
        if not line_user_id:
            return jsonify({"error": "需要提供使用者ID"}), 400
        
        # 查詢使用者
        user = User.query.filter_by(line_user_id=line_user_id).first()
        if not user:
            return jsonify({"error": "找不到使用者"}), 404
        
        # 查詢訂單記錄（最近20筆）
        orders = Order.query.filter_by(user_id=user.user_id).order_by(Order.order_time.desc()).limit(20).all()
        
        order_history = []
        for order in orders:
            store = Store.query.get(order.store_id)
            
            # 取得訂單項目
            order_items = []
            for item in order.items:
                menu_item = MenuItem.query.get(item.menu_item_id)
                if menu_item:
                    order_items.append({
                        'item_name': menu_item.item_name,
                        'quantity': item.quantity_small,
                        'price': menu_item.price_small,
                        'subtotal': item.subtotal
                    })
            
            order_data = {
                'order_id': order.order_id,
                'store_name': store.store_name if store else "Unknown Store",
                'store_id': order.store_id,
                'order_time': order.order_time.isoformat(),
                'total_amount': order.total_amount,
                'status': order.status,
                'items': order_items,
                'item_count': len(order_items)
            }
            order_history.append(order_data)
        
        return jsonify({
            'user_id': user.user_id,
            'line_user_id': user.line_user_id,
            'preferred_language': user.preferred_lang,
            'total_orders': len(order_history),
            'orders': order_history
        })
        
    except Exception as e:
        return jsonify({"error": "查詢訂單記錄失敗"}), 500

@api_bp.route('/orders/<int:order_id>/details', methods=['GET'])
def get_order_details(order_id):
    """取得訂單詳細資訊"""
    try:
        order = Order.query.get(order_id)
        if not order:
            return jsonify({"error": "找不到訂單"}), 404
        
        store = Store.query.get(order.store_id)
        user = User.query.get(order.user_id)
        
        # 取得訂單項目
        order_items = []
        for item in order.items:
            menu_item = MenuItem.query.get(item.menu_item_id)
            if menu_item:
                order_items.append({
                    'item_name': menu_item.item_name,
                    'quantity': item.quantity_small,
                    'price': menu_item.price_small,
                    'subtotal': item.subtotal
                })
        
        # 建立完整訂單確認內容
        from .helpers import create_complete_order_confirmation
        confirmation = create_complete_order_confirmation(order_id, user.preferred_lang)
        
        order_details = {
            'order_id': order.order_id,
            'store_name': store.store_name if store else "Unknown Store",
            'store_id': order.store_id,
            'order_time': order.order_time.isoformat(),
            'total_amount': order.total_amount,
            'status': order.status,
            'items': order_items,
            'item_count': len(order_items),
            'user_language': user.preferred_lang,
            'confirmation': confirmation
        }
        
        return jsonify(order_details)
        
    except Exception as e:
        return jsonify({"error": "取得訂單詳細資訊失敗"}), 500

@api_bp.route('/voice/generate', methods=['POST'])
def generate_custom_voice():
    """生成自定義語音檔"""
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({"error": "缺少文字內容"}), 400
        
        text = data['text']
        speech_rate = data.get('rate', 1.0, type=float)
        voice_name = data.get('voice', 'zh-TW-HsiaoChenNeural')
        
        # 限制語速範圍
        speech_rate = max(0.5, min(2.0, speech_rate))
        
        from .helpers import generate_voice_with_custom_rate
        voice_path = generate_voice_with_custom_rate(text, speech_rate, voice_name)
        
        if voice_path and os.path.exists(voice_path):
            # 構建語音檔 URL
            fname = os.path.basename(voice_path)
            from ..config import URLConfig
            audio_url = URLConfig.get_voice_url(fname)
            
            return jsonify({
                "success": True,
                "voice_url": audio_url,
                "filename": fname,
                "message": "自定義語音檔生成成功"
            })
        else:
            return jsonify({"error": "語音檔生成失敗"}), 500
            
    except Exception as e:
        return jsonify({"error": "生成語音檔失敗"}), 500

@api_bp.route('/voice/generate-enhanced', methods=['POST'])
def generate_enhanced_voice():
    """生成增強版語音檔（支援 SSML 和情感風格）"""
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({"error": "缺少文字內容"}), 400
        
        text = data['text']
        speech_rate = data.get('rate', 1.0, type=float)
        emotion_style = data.get('emotion', 'cheerful')  # 情感風格
        use_hd_voice = data.get('hd_voice', True, type=bool)  # 是否使用 HD 聲音
        
        # 限制語速範圍
        speech_rate = max(0.5, min(2.0, speech_rate))
        
        # 驗證情感風格
        valid_emotions = ['cheerful', 'friendly', 'excited', 'calm', 'sad']
        if emotion_style not in valid_emotions:
            emotion_style = 'cheerful'
        
        from .helpers import generate_voice_with_custom_rate_enhanced
        voice_path = generate_voice_with_custom_rate_enhanced(text, speech_rate, emotion_style, use_hd_voice)
        
        if voice_path and os.path.exists(voice_path):
            # 構建語音檔 URL
            fname = os.path.basename(voice_path)
            from ..config import URLConfig
            audio_url = URLConfig.get_voice_url(fname)
            
            return jsonify({
                "success": True,
                "voice_url": audio_url,
                "filename": fname,
                "emotion_style": emotion_style,
                "hd_voice": use_hd_voice,
                "message": "增強版語音檔生成成功"
            })
        else:
            return jsonify({"error": "增強版語音檔生成失敗"}), 500
            
    except Exception as e:
        return jsonify({"error": f"生成增強版語音檔失敗: {str(e)}"}), 500

@api_bp.route('/users/register', methods=['POST'])
def register_user():
    """使用者註冊"""
    data = request.get_json()
    
    if not data or 'line_user_id' not in data or 'preferred_lang' not in data:
        return jsonify({"error": "註冊資料不完整"}), 400
    
    # 檢查使用者是否已存在
    existing_user = User.query.filter_by(line_user_id=data['line_user_id']).first()
    if existing_user:
        # 更新語言偏好
        existing_user.preferred_lang = data['preferred_lang']
        db.session.commit()
        return jsonify({"message": "使用者語言偏好已更新", "user_id": existing_user.user_id})
    
    # 建立新使用者
    new_user = User(
        line_user_id=data['line_user_id'],
        preferred_lang=data['preferred_lang']
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({"message": "使用者註冊成功", "user_id": new_user.user_id}), 201

@api_bp.route('/test', methods=['GET', 'POST', 'OPTIONS'])
def test():
    """API 連線測試"""
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    if request.method == 'POST':
        # 測試 POST 請求
        data = request.get_json() or {}
        response = jsonify({
            'message': 'POST 請求測試成功',
            'received_data': data,
            'content_type': request.content_type,
            'method': request.method
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    
    # GET 請求
    response = jsonify({
        'message': 'API is working!',
        'method': request.method,
        'endpoints': {
            'upload_menu': '/api/upload-menu-image (POST)',
            'test': '/api/test (GET/POST)',
            'health': '/api/health (GET)'
        }
    })
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@api_bp.route('/test-upload', methods=['GET', 'POST', 'OPTIONS'])
def test_upload():
    """檔案上傳測試端點"""
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    if request.method == 'GET':
        response = jsonify({
            'message': '檔案上傳測試端點',
            'usage': '請使用 POST 方法上傳檔案',
            'supported_fields': ['file', 'image'],
            'example': {
                'file': '檔案對象',
                'store_id': '店家ID (數字)',
                'lang': '目標語言 (可選，預設: en)'
            }
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    
    # POST 請求
    try:
        print(f"收到測試上傳請求，Content-Type: {request.content_type}")
        print(f"請求表單資料: {list(request.form.keys())}")
        print(f"請求檔案: {list(request.files.keys())}")
        
        # 檢查檔案
        file = None
        if 'file' in request.files:
            file = request.files['file']
            print("使用 'file' 參數")
        elif 'image' in request.files:
            file = request.files['image']
            print("使用 'image' 參數")
        else:
            response = jsonify({
                'error': '沒有找到檔案',
                'available_fields': list(request.files.keys()),
                'message': '請使用 "file" 或 "image" 參數'
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        # 檢查檔案信息
        file_info = {
            'filename': file.filename,
            'content_type': file.content_type,
            'size': len(file.read())
        }
        file.seek(0)  # 重置檔案指標
        
        # 檢查參數
        store_id = request.form.get('store_id', type=int)
        lang = request.form.get('lang', 'en')
        
        response = jsonify({
            'message': '檔案上傳測試成功',
            'file_info': file_info,
            'parameters': {
                'store_id': store_id,
                'lang': lang
            },
            'method': request.method,
            'content_type': request.content_type
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
        
    except Exception as e:
        response = jsonify({
            'error': '檔案上傳測試失敗',
            'message': str(e)
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

# =============================================================================
# 新增缺失的 API 端點
# 功能：為 LIFF 前端提供必要的 API 端點
# =============================================================================

@api_bp.route('/health', methods=['GET', 'OPTIONS'])
def health_check():
    """健康檢查端點"""
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        # 檢查資料庫連線
        from ..models import db
        db.session.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    response = jsonify({
        'status': 'healthy',
        'message': 'API is running',
        'timestamp': datetime.datetime.now().isoformat(),
        'database': db_status,
        'environment': {
            'db_user': bool(os.getenv('DB_USER')),
            'db_host': bool(os.getenv('DB_HOST')),
            'line_token': bool(os.getenv('LINE_CHANNEL_ACCESS_TOKEN')),
            'gemini_key': bool(os.getenv('GEMINI_API_KEY')),
            'azure_speech': bool(os.getenv('AZURE_SPEECH_KEY'))
        }
    })
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@api_bp.route('/fix-database', methods=['POST', 'OPTIONS'])
def fix_database():
    """修復數據庫表結構"""
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        print("🔧 開始修復數據庫...")
        
        # 檢查現有表
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        # 檢查並創建必要的表
        required_tables = ['ocr_menus', 'ocr_menu_items', 'ocr_menu_translations', 'order_summaries']
        
        for table_name in required_tables:
            if table_name not in existing_tables:
                print(f"🔧 創建 {table_name} 表...")
                
                if table_name == 'ocr_menus':
                    # 創建 ocr_menus 表
                    create_table_sql = """
                    CREATE TABLE ocr_menus (
                        ocr_menu_id BIGINT NOT NULL AUTO_INCREMENT,
                        user_id BIGINT NOT NULL,
                        store_id INT DEFAULT NULL,
                        store_name VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
                        upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (ocr_menu_id),
                        FOREIGN KEY (user_id) REFERENCES users (user_id),
                        FOREIGN KEY (store_id) REFERENCES stores (store_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='非合作店家用戶OCR菜單主檔'
                    """
                    
                    db.session.execute(text(create_table_sql))
                    db.session.commit()
                    print(f"✅ {table_name} 表創建成功")
                    
                elif table_name == 'ocr_menu_translations':
                    # 創建 ocr_menu_translations 表
                    create_table_sql = """
                    CREATE TABLE ocr_menu_translations (
                        ocr_menu_translation_id BIGINT NOT NULL AUTO_INCREMENT,
                        ocr_menu_item_id BIGINT NOT NULL,
                        lang_code VARCHAR(10) NOT NULL,
                        translated_name VARCHAR(100) COLLATE utf8mb4_bin NOT NULL,
                        translated_description TEXT COLLATE utf8mb4_bin,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (ocr_menu_translation_id),
                        FOREIGN KEY (ocr_menu_item_id) REFERENCES ocr_menu_items (ocr_menu_item_id),
                        FOREIGN KEY (lang_code) REFERENCES languages (line_lang_code)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='OCR菜單翻譯表'
                    """
                    
                    db.session.execute(text(create_table_sql))
                    db.session.commit()
                    print(f"✅ {table_name} 表創建成功")
                    
                elif table_name == 'ocr_menu_items':
                    # 創建 ocr_menu_items 表
                    create_table_sql = """
                    CREATE TABLE ocr_menu_items (
                        ocr_menu_item_id BIGINT NOT NULL AUTO_INCREMENT,
                        ocr_menu_id BIGINT NOT NULL,
                        item_name VARCHAR(100) COLLATE utf8mb4_bin NOT NULL,
                        price_big INT DEFAULT NULL,
                        price_small INT NOT NULL,
                        translated_desc TEXT COLLATE utf8mb4_bin,
                        PRIMARY KEY (ocr_menu_item_id),
                        FOREIGN KEY (ocr_menu_id) REFERENCES ocr_menus (ocr_menu_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='OCR菜單品項明細'
                    """
                    
                    db.session.execute(text(create_table_sql))
                    db.session.commit()
                    print(f"✅ {table_name} 表創建成功")
                    
                elif table_name == 'order_summaries':
                    # 創建 order_summaries 表
                    create_table_sql = """
                    CREATE TABLE order_summaries (
                        summary_id BIGINT NOT NULL AUTO_INCREMENT,
                        order_id BIGINT NOT NULL,
                        ocr_menu_id BIGINT NULL,
                        chinese_summary TEXT NOT NULL,
                        user_language_summary TEXT NOT NULL,
                        user_language VARCHAR(10) NOT NULL,
                        total_amount INT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (summary_id),
                        FOREIGN KEY (order_id) REFERENCES orders (order_id),
                        FOREIGN KEY (ocr_menu_id) REFERENCES ocr_menus (ocr_menu_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='訂單摘要'
                    """
                    
                    db.session.execute(text(create_table_sql))
                    db.session.commit()
                    print(f"✅ {table_name} 表創建成功")
                    
                else:
                    print(f"❌ 不支援創建 {table_name} 表")
                    return jsonify({
                        'status': 'error',
                        'message': f'不支援創建 {table_name} 表'
                    }), 500
            else:
                print(f"✅ {table_name} 表已存在")
                
                # 檢查表結構
                columns = inspector.get_columns(table_name)
                column_names = [col['name'] for col in columns]
                
                if table_name == 'ocr_menus':
                    expected_columns = ['ocr_menu_id', 'user_id', 'store_name', 'upload_time']
                    
                    missing_columns = [col for col in expected_columns if col not in column_names]
                    
                    if missing_columns:
                        print(f"⚠️  {table_name} 表缺少欄位: {missing_columns}")
                        return jsonify({
                            'status': 'error',
                            'message': f'{table_name} 表結構不完整，缺少欄位: {missing_columns}'
                        }), 500
                    else:
                        print(f"✅ {table_name} 表結構正確")
                        
                elif table_name == 'ocr_menu_items':
                    expected_columns = ['ocr_menu_item_id', 'ocr_menu_id', 'item_name', 'price_big', 'price_small', 'translated_desc']
                    
                    missing_columns = [col for col in expected_columns if col not in column_names]
                    
                    if missing_columns:
                        print(f"⚠️  {table_name} 表缺少欄位: {missing_columns}")
                        return jsonify({
                            'status': 'error',
                            'message': f'{table_name} 表結構不完整，缺少欄位: {missing_columns}'
                        }), 500
                    else:
                        print(f"✅ {table_name} 表結構正確")
                        
                elif table_name == 'order_summaries':
                    expected_columns = ['summary_id', 'order_id', 'ocr_menu_id', 'chinese_summary', 'user_language_summary', 'user_language', 'total_amount', 'created_at']
                    
                    missing_columns = [col for col in expected_columns if col not in column_names]
                    
                    if missing_columns:
                        print(f"⚠️  {table_name} 表缺少欄位: {missing_columns}")
                        return jsonify({
                            'status': 'error',
                            'message': f'{table_name} 表結構不完整，缺少欄位: {missing_columns}'
                        }), 500
                    else:
                        print(f"✅ {table_name} 表結構正確")
        
        print("🎉 數據庫修復完成")
        response = jsonify({
            'status': 'success',
            'message': '數據庫修復完成'
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
        
    except Exception as e:
        print(f"❌ 修復數據庫時發生錯誤: {e}")
        response = jsonify({
            'status': 'error',
            'message': f'修復失敗: {str(e)}'
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@api_bp.route('/stores', methods=['GET', 'OPTIONS'])
def get_all_stores():
    """取得所有店家列表"""
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        stores = Store.query.all()
        store_list = []
        
        for store in stores:
            store_list.append({
                'store_id': store.store_id,
                'store_name': store.store_name,
                'partner_level': store.partner_level,
                'gps_lat': store.gps_lat,
                'gps_lng': store.gps_lng,
                'place_id': store.place_id,
                'review_summary': store.review_summary,
                'main_photo_url': store.main_photo_url,
                'created_at': store.created_at.isoformat() if store.created_at else None
            })
        
        response = jsonify({
            'stores': store_list,
            'total_count': len(store_list)
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
        
    except Exception as e:
        print(f"取得店家列表失敗: {e}")
        response = jsonify({'error': '無法載入店家列表'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@api_bp.route('/upload-menu-image', methods=['GET', 'POST', 'OPTIONS'])
def upload_menu_image():
    """上傳菜單圖片並進行 OCR 處理"""
    t0 = time.time()
    
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    # 處理 GET 請求（提供錯誤訊息）
    if request.method == 'GET':
        response = jsonify({
            'error': '此端點只接受 POST 請求',
            'message': '請使用 POST 方法上傳菜單圖片',
            'supported_methods': ['POST', 'OPTIONS']
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 405
    
    try:
        print(f"收到上傳請求，Content-Type: {request.content_type}")
        print(f"請求表單資料: {list(request.form.keys())}")
        print(f"請求檔案: {list(request.files.keys())}")
        
        # 檢查是否有檔案（支援 'file' 和 'image' 參數）
        file = None
        if 'file' in request.files:
            file = request.files['file']
            print("使用 'file' 參數")
        elif 'image' in request.files:
            file = request.files['image']
            print("使用 'image' 參數")
        else:
            print("錯誤：沒有找到 'file' 或 'image' 欄位")
            print(f"可用的檔案欄位: {list(request.files.keys())}")
            response = jsonify({
                'error': '沒有上傳檔案',
                'message': '請使用 "file" 或 "image" 參數上傳檔案',
                'available_fields': list(request.files.keys())
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        print(f"檔案名稱: {file.filename}")
        print(f"檔案大小: {len(file.read())} bytes")
        file.seek(0)  # 重置檔案指標
        
        # 檢查檔案名稱
        if file.filename == '':
            print("錯誤：檔案名稱為空")
            response = jsonify({'error': '沒有選擇檔案'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        # 檢查檔案格式
        if not allowed_file(file.filename):
            print(f"錯誤：不支援的檔案格式 {file.filename}")
            response = jsonify({'error': '不支援的檔案格式'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        # 取得參數
        raw_store_id = request.form.get('store_id')  # 可能是整數、數字字串或 Google Place ID
        user_id = request.form.get('user_id', type=int)
        target_lang = request.form.get('lang', 'en')
        
        print(f"原始店家ID: {raw_store_id}")
        print(f"使用者ID: {user_id}")
        print(f"目標語言: {target_lang}")
        
        if not raw_store_id:
            print("錯誤：沒有提供店家ID")
            response = jsonify({"error": "需要提供店家ID"})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        # 使用 store resolver 解析店家 ID
        try:
            from .store_resolver import resolve_store_id
            store_db_id = resolve_store_id(raw_store_id)
            print(f"✅ 店家ID解析成功: {raw_store_id} -> {store_db_id}")
        except Exception as e:
            print(f"❌ 店家ID解析失敗: {e}")
            response = jsonify({
                "error": "店家ID格式錯誤",
                "details": str(e),
                "received_store_id": raw_store_id
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        # 儲存上傳的檔案
        print("開始儲存檔案...")
        filepath = save_uploaded_file(file)
        print(f"檔案已儲存到: {filepath}")
        
        # 生成唯一的處理 ID（不使用資料庫）
        processing_id = int(time.time() * 1000)  # 使用時間戳作為 ID
        print(f"處理記錄已建立，ID: {processing_id}")
        
        # 使用 Gemini API 處理圖片
        print("開始使用 Gemini API 處理圖片...")
        result = process_menu_with_gemini(filepath, target_lang)
        
        # 加入詳細日誌，幫助診斷 OCR 問題
        print(f"🔍 OCR 原始結果: {result}")
        if result and 'menu_items' in result:
            print(f"📋 菜單項目數量: {len(result['menu_items'])}")
            if result['menu_items']:
                print(f"📋 第一個項目結構: {result['menu_items'][0]}")
                print(f"📋 第一個項目 keys: {list(result['menu_items'][0].keys())}")
        
        # 檢查處理結果
        if result and result.get('success', False):
            
            # 生成動態菜單資料
            menu_items = result.get('menu_items', [])
            dynamic_menu = []
            
            # 建立 OCR 菜單記錄到資料庫（使用解析後的整數 store_id）
            ocr_menu_id = None
            try:
                # 處理 user_id - 如果沒有提供，創建一個臨時使用者
                actual_user_id = user_id
                if not actual_user_id:
                    # 創建一個臨時使用者
                    temp_user = User(
                        line_user_id=f"temp_guest_{int(time.time())}",
                        preferred_lang=target_lang or 'zh'
                    )
                    db.session.add(temp_user)
                    db.session.flush()  # 獲取 user_id
                    actual_user_id = temp_user.user_id
                    print(f"✅ 創建臨時使用者，ID: {actual_user_id}")
                
                # 建立 OCR 菜單記錄到資料庫
                ocr_menu = OCRMenu(
                    user_id=actual_user_id,
                    store_id=store_db_id,  # 使用解析後的 store_db_id
                    store_name=result.get('store_info', {}).get('name', '臨時店家')
                )
                db.session.add(ocr_menu)
                db.session.flush()  # 獲取 ocr_menu_id
                ocr_menu_id = ocr_menu.ocr_menu_id
                
                # 儲存菜單項目到資料庫
                for item in menu_items:
                    ocr_menu_item = OCRMenuItem(
                        ocr_menu_id=ocr_menu.ocr_menu_id,
                        item_name=item.get('original_name', ''),
                        price_small=item.get('price', 0),
                        price_big=item.get('price', 0),  # 暫時使用相同價格
                        translated_desc=item.get('description', '') or item.get('translated_name', '')
                    )
                    db.session.add(ocr_menu_item)
                
                # 提交到資料庫
                db.session.commit()
                print(f"✅ OCR菜單已儲存到資料庫，OCR 菜單 ID: {ocr_menu_id}")
                
            except Exception as e:
                print(f"❌ 儲存到資料庫失敗: {e}")
                db.session.rollback()
                ocr_menu_id = None
            
            for i, item in enumerate(menu_items):
                # 確保所有字串欄位都不是 null/undefined，避免前端 charAt() 錯誤
                # 並提供前端需要的所有必要欄位
                # 安全處理價格資料
                def safe_price(value):
                    if value is None:
                        return 0
                    try:
                        return int(float(value))
                    except (ValueError, TypeError):
                        return 0
                
                price = safe_price(item.get('price', 0))
                
                # 過濾掉價格為 0 的商品，避免前端出現價格驗證錯誤
                if price <= 0:
                    continue
                
                # 正規化菜單項目格式，確保前端能正確解析
                original_name = str(item.get('original_name', '') or item.get('name', {}).get('original', '') or '')
                translated_name = str(item.get('translated_name', '') or item.get('name', {}).get('translated', '') or '')
                
                # 如果沒有原始名稱，嘗試其他可能的欄位
                if not original_name:
                    original_name = str(item.get('name', '') or item.get('title', '') or item.get('item_name', '') or '')
                
                # 如果沒有翻譯名稱，使用原始名稱
                if not translated_name:
                    translated_name = original_name
                
                dynamic_menu.append({
                    'temp_id': f"temp_{processing_id}_{i}",
                    'id': f"temp_{processing_id}_{i}",  # 前端可能需要 id 欄位
                    'original_name': original_name,
                    'translated_name': translated_name,
                    'en_name': translated_name,  # 英語名稱
                    'name': {  # 新增前端支援的新格式
                        'original': original_name,
                        'translated': translated_name
                    },
                    'price': price,
                    'price_small': price,  # 小份價格
                    'price_large': price,  # 大份價格
                    'description': str(item.get('description', '') or ''),
                    'category': str(item.get('category', '') or '其他'),
                    'image_url': '/static/images/default-dish.png',  # 預設圖片
                    'imageUrl': '/static/images/default-dish.png',  # 前端可能用這個欄位名
                    'show_image': False,  # 控制是否顯示圖片框框
                    'inventory': 999,  # 庫存數量
                    'available': True,  # 是否可購買
                    'processing_id': processing_id
                })
            
            # 僅回傳必要字段，避免過大與難序列化物件
            response_data = {
                "ok": True,
                "processing_id": processing_id,
                "menu_items": dynamic_menu,
                "count": len(dynamic_menu),
                "elapsed_sec": round(time.time() - t0, 1),
                "store_id": store_db_id,
                "target_language": target_lang
            }
            
            response = jsonify(response_data)
            response.headers.add('Access-Control-Allow-Origin', '*')
            
            print(f"🎉 API 成功回應 200 OK")
            print(f"📊 回應統計: 處理ID={processing_id}, 項目數={len(dynamic_menu)}, 耗時={round(time.time() - t0, 1)}s")
            
            return response, 200
        else:
            # 處理失敗情況
            error_message = result.get('error', '菜單處理失敗，請重新拍攝清晰的菜單照片')
            
            print(f"❌ API 返回 500 錯誤: {error_message}")
            
            response = jsonify({
                "ok": False,
                "error": error_message,
                "elapsed_sec": round(time.time() - t0, 1)
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 500
            
    except Exception as e:
        print(f"OCR處理失敗：{e}")
        response = jsonify({
            'ok': False,
            'error': '檔案處理失敗',
            'details': str(e) if current_app.debug else '請稍後再試',
            'elapsed_sec': round(time.time() - t0, 1)
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@api_bp.route('/debug/order-data', methods=['POST', 'OPTIONS'])
def debug_order_data():
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    """除錯訂單資料格式"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "請求資料為空"}), 400
    
    analysis = {
        "data_type": type(data).__name__,
        "received_data": data,
        "top_level_keys": list(data.keys()) if isinstance(data, dict) else [],
        "validation_results": {
            "required_fields": {
                "present": [],
                "missing": []
            },
            "store": {"found": False, "store_name": None},
            "user": {"found": False, "user_id": None}
        }
    }
    
    # 檢查必要欄位
    required_fields = ['store_id', 'items']
    if isinstance(data, dict):
        for field in required_fields:
            if field in data:
                analysis["validation_results"]["required_fields"]["present"].append(field)
            else:
                analysis["validation_results"]["required_fields"]["missing"].append(field)
    
    # 檢查店家
    if isinstance(data, dict) and 'store_id' in data:
        try:
            store = Store.query.get(data['store_id'])
            if store:
                analysis["validation_results"]["store"]["found"] = True
                analysis["validation_results"]["store"]["store_name"] = store.store_name
        except Exception as e:
            analysis["validation_results"]["store"]["error"] = str(e)
    
    # 檢查使用者
    if isinstance(data, dict) and 'line_user_id' in data:
        try:
            user = User.query.filter_by(line_user_id=data['line_user_id']).first()
            if user:
                analysis["validation_results"]["user"]["found"] = True
                analysis["validation_results"]["user"]["user_id"] = user.user_id
        except Exception as e:
            analysis["validation_results"]["user"]["error"] = str(e)
    
    # 分析 items 陣列
    if isinstance(data, dict) and 'items' in data and isinstance(data['items'], list):
        analysis["validation_results"]["items"] = []
        for i, item in enumerate(data['items']):
            item_analysis = {
                "index": i,
                "item_type": type(item).__name__,
                "keys": list(item.keys()) if isinstance(item, dict) else [],
                "values": item if isinstance(item, dict) else item,
                "field_check": {}
            }
            
            if isinstance(item, dict):
                for field in ['menu_item_id', 'id', 'quantity', 'qty', 'price', 'price_small']:
                    if field in item:
                        item_analysis["field_check"][field] = {
                            "type": type(item[field]).__name__,
                            "value": item[field]
                        }
            
            analysis["validation_results"]["items"].append(item_analysis)
    
    suggestions = []
    if analysis["validation_results"]["required_fields"]["missing"]:
        suggestions.append("如果缺少必要欄位，請檢查前端發送的資料格式")
    if not analysis["validation_results"]["items"]:
        suggestions.append("如果 items 陣列格式不正確，請確保每個項目都有 menu_item_id 和 quantity")
    if not analysis["validation_results"]["store"]["found"]:
        suggestions.append("如果找不到使用者或店家，請檢查 ID 是否正確")
    
    return jsonify({
        "message": "訂單資料分析完成",
        "analysis": analysis,
        "suggestions": suggestions
    }), 200

@api_bp.route('/admin/migrate-database', methods=['POST', 'OPTIONS'])
def migrate_database():
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    """執行資料庫遷移（僅限管理員）"""
    try:
        # 檢查是否為管理員（這裡可以添加更嚴格的驗證）
        # 暫時允許所有請求，但建議添加適當的認證
        
        from tools.migrate_order_items import migrate_order_items, verify_migration
        
        print("🔄 開始執行資料庫遷移...")
        
        # 執行遷移
        success = migrate_order_items()
        
        if success:
            # 驗證遷移
            verify_success = verify_migration()
            
            if verify_success:
                return jsonify({
                    "message": "資料庫遷移成功",
                    "status": "success",
                    "details": "OrderItem 表結構已更新，支援臨時項目"
                }), 200
            else:
                return jsonify({
                    "message": "遷移完成但驗證失敗",
                    "status": "warning",
                    "details": "請檢查資料庫結構"
                }), 200
        else:
            return jsonify({
                "message": "資料庫遷移失敗",
                "status": "error",
                "details": "請檢查錯誤日誌"
            }), 500
            
    except Exception as e:
        return jsonify({
            "message": "遷移過程中發生錯誤",
            "status": "error",
            "details": str(e)
        }), 500

@api_bp.route('/menu/simple-ocr', methods=['POST', 'OPTIONS'])
def simple_menu_ocr():
    """
    @deprecated 此端點已棄用，請使用 /api/menu/process-ocr?simple_mode=true
    將在未來版本中移除
    """
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        # 將請求資料轉發到主要端點，並設定簡化模式
        from flask import request as flask_request
        
        # 複製請求資料
        form_data = dict(flask_request.form)
        form_data['simple_mode'] = 'true'  # 強制啟用簡化模式
        
        # 複製檔案
        files_data = dict(flask_request.files)
        
        # 建立新的請求到主要端點
        from flask import current_app
        with current_app.test_client() as client:
            response = client.post('/api/menu/process-ocr', 
                                data=form_data, 
                                files=files_data)
            
            # 返回相同的回應
            return response.data, response.status_code, response.headers
            
    except Exception as e:
        print(f"簡化 OCR 處理失敗：{e}")
        response = jsonify({
            "success": False,
            "error": "處理過程中發生錯誤，請直接使用 /api/menu/process-ocr?simple_mode=true"
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@api_bp.route('/menu/ocr/<int:ocr_menu_id>', methods=['GET'])
def get_ocr_menu(ocr_menu_id):
    """根據OCR菜單ID取得已儲存的菜單資料"""
    try:
        # 查詢OCR菜單
        ocr_menu = OCRMenu.query.get(ocr_menu_id)
        if not ocr_menu:
            return jsonify({"error": "找不到OCR菜單"}), 404
        
        # 查詢OCR菜單項目
        ocr_menu_items = OCRMenuItem.query.filter_by(ocr_menu_id=ocr_menu_id).all()
        
        # 取得使用者語言偏好
        user_language = request.args.get('lang', 'zh')
        
        # 使用新的翻譯機制
        from .helpers import translate_ocr_menu_items_with_db_fallback
        translated_items = translate_ocr_menu_items_with_db_fallback(ocr_menu_items, user_language)
        
        # 轉換為前端相容格式
        menu_items = []
        for item in translated_items:
            menu_items.append({
                'id': f"ocr_{ocr_menu_id}_{item['ocr_menu_item_id']}",
                'original_name': item['original_name'],
                'translated_name': item['translated_name'],
                'price': item['price_small'],
                'price_small': item['price_small'],
                'price_big': item['price_big'],
                'description': item['translated_name'],  # 使用翻譯後的名稱作為描述
                'category': '其他',
                'image_url': '/static/images/default-dish.png',
                'imageUrl': '/static/images/default-dish.png',
                'show_image': False,
                'inventory': 999,
                'available': True,
                'ocr_menu_item_id': item['ocr_menu_item_id'],
                'translation_source': item['translation_source']
            })
        
        return jsonify({
            "success": True,
            "ocr_menu_id": ocr_menu_id,
            "store_name": ocr_menu.store_name,
            "user_language": user_language,
            "menu_items": menu_items,
            "total_items": len(menu_items),
            "upload_time": ocr_menu.upload_time.isoformat() if ocr_menu.upload_time else None
        })
        
    except Exception as e:
        current_app.logger.error(f"取得OCR菜單錯誤: {str(e)}")
        return jsonify({'error': '無法載入OCR菜單'}), 500

@api_bp.route('/menu/ocr', methods=['GET', 'OPTIONS'])
def list_ocr_menus():
    """列出使用者的 OCR 菜單"""
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        # 取得使用者 ID
        user_id = request.args.get('user_id', type=int)
        if not user_id:
            response = jsonify({
                "success": False,
                "error": "需要提供使用者 ID"
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        # 查詢使用者的 OCR 菜單
        ocr_menus = OCRMenu.query.filter_by(user_id=user_id).order_by(OCRMenu.upload_time.desc()).all()
        
        # 準備回應資料
        menus_data = []
        for menu in ocr_menus:
            # 查詢菜單項目數量
            item_count = OCRMenuItem.query.filter_by(ocr_menu_id=menu.ocr_menu_id).count()
            
            menus_data.append({
                'ocr_menu_id': menu.ocr_menu_id,
                'store_name': menu.store_name,
                'upload_time': menu.upload_time.isoformat() if menu.upload_time else None,
                'item_count': item_count
            })
        
        response = jsonify({
            "success": True,
            "ocr_menus": menus_data,
            "total_menus": len(menus_data)
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200
        
    except Exception as e:
        print(f"查詢使用者 OCR 菜單失敗：{e}")
        response = jsonify({
            "success": False,
            "error": "查詢過程中發生錯誤"
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@api_bp.route('/orders/simple', methods=['POST', 'OPTIONS'])
def simple_order():
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        # 解析請求資料
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "請求資料為空"
            }), 400
        
        # 檢查是否為舊格式訂單，如果是則轉換為新格式
        if 'store_id' in data and 'items' in data:
            # 舊格式訂單，需要轉換
            print("檢測到舊格式訂單，進行格式轉換")
            
            # 重構資料格式以符合新格式的要求
            simple_data = {
                'items': [],
                'lang': data.get('language', 'zh-TW'),
                'line_user_id': data.get('line_user_id')
            }
            
            for item in data.get('items', []):
                # 防呆轉換器：使用新的安全本地化菜名建立函數
                from .helpers import safe_build_localised_name
                
                # 檢查是否已經是新的雙語格式（name 是巢狀物件）
                if 'name' in item and isinstance(item['name'], dict) and 'original' in item['name'] and 'translated' in item['name']:
                    # 已經是新格式，直接使用
                    simple_item = {
                        'name': item['name'],
                        'quantity': item.get('quantity') or item.get('qty') or 1,
                        'price': item.get('price') or item.get('price_small') or 0
                    }
                else:
                    # 舊格式，使用安全本地化菜名建立函數
                    item_name = item.get('item_name') or item.get('name') or item.get('original_name') or '未知項目'
                    
                    # 優先使用 OCR 取得的中文菜名
                    ocr_name = item.get('ocr_name') or item.get('original_name')
                    raw_name = item.get('translated_name') or item.get('name') or item_name
                    
                    localised_name = safe_build_localised_name(raw_name, ocr_name)
                    
                    simple_item = {
                        'name': localised_name,
                        'quantity': item.get('quantity') or item.get('qty') or 1,
                        'price': item.get('price') or item.get('price_small') or 0
                    }
                
                simple_data['items'].append(simple_item)
            
            # 使用轉換後的資料
            data = simple_data
        
        # 使用 Pydantic 模型驗證請求資料
        try:
            from .helpers import OrderRequest, process_order_with_dual_language, synthesize_azure_tts
            order_request = OrderRequest(**data)
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"請求資料格式錯誤: {str(e)}"
            }), 400
        
        # 處理雙語訂單（使用修復版本）
        from .helpers import process_order_with_enhanced_tts, send_order_to_line_bot_fixed
        order_result = process_order_with_enhanced_tts(order_request)
        if not order_result:
            return jsonify({
                "success": False,
                "error": "訂單處理失敗"
            }), 500
        
        # 保存訂單到資料庫
        try:
            from ..models import User, Store, Order, OrderItem, Menu, MenuItem
            import datetime
            
            # 查找或創建使用者
            line_user_id = order_request.line_user_id
            if not line_user_id:
                line_user_id = f"guest_{uuid.uuid4().hex[:8]}"
            
            user = User.query.filter_by(line_user_id=line_user_id).first()
            if not user:
                # 創建新使用者
                user = User(
                    line_user_id=line_user_id,
                    preferred_lang=order_request.lang
                )
                db.session.add(user)
                db.session.flush()
            
            # 查找或創建預設店家
            store = Store.query.filter_by(store_name='預設店家').first()
            if not store:
                store = Store(
                    store_name='預設店家',
                    partner_level=0  # 非合作店家
                )
                db.session.add(store)
                db.session.flush()
            
            # 創建訂單
            order = Order(
                user_id=user.user_id,
                store_id=store.store_id,
                order_time=datetime.datetime.now(),
                total_amount=order_result['total_amount'],
                status='pending'
            )
            db.session.add(order)
            db.session.flush()
            
            # 創建訂單項目 - 修改以確保 menu_item_id 不為 NULL
            for item in order_result['zh_items']:
                # 檢查是否有有效的 menu_item_id
                menu_item_id = item.get('menu_item_id')
                
                # 如果沒有有效的 menu_item_id，為非合作店家創建臨時 MenuItem
                if not menu_item_id:
                    try:
                        # 查找或創建菜單
                        menu = Menu.query.filter_by(store_id=store.store_id).first()
                        if not menu:
                            menu = Menu(
                                store_id=store.store_id,
                                version=1,
                                effective_date=datetime.datetime.now()  # 明確設置 effective_date
                            )
                            db.session.add(menu)
                            db.session.flush()
                        
                        # 創建臨時菜單項目
                        temp_menu_item = MenuItem(
                            menu_id=menu.menu_id,
                            item_name=item.get('name', '臨時項目'),
                            price_small=int(item.get('price', 0)),
                            price_big=int(item.get('price', 0))
                        )
                        db.session.add(temp_menu_item)
                        db.session.flush()  # 獲取 menu_item_id
                        
                        # 使用新創建的 menu_item_id
                        menu_item_id = temp_menu_item.menu_item_id
                        
                        print(f"✅ 為非合作店家創建臨時菜單項目: {temp_menu_item.menu_item_id}")
                        
                    except Exception as e:
                        print(f"❌ 創建臨時菜單項目失敗: {e}")
                        # 如果創建失敗，跳過這個項目
                        continue
                
                # 創建訂單項目（確保 menu_item_id 不為 NULL）
                order_item = OrderItem(
                    order_id=order.order_id,
                    menu_item_id=menu_item_id,  # 現在確保不為 NULL
                    quantity_small=item['quantity'],
                    subtotal=item['subtotal'],
                    original_name=item.get('name', ''),  # 保存原始中文菜名
                    translated_name=item.get('name', '')  # 暫時使用相同名稱
                )
                db.session.add(order_item)
            
            db.session.commit()
            
            # 生成語音檔案
            try:
                voice_file_path = generate_voice_order(order.order_id)
                if voice_file_path:
                    print(f"✅ 成功生成語音檔案: {voice_file_path}")
            except Exception as e:
                print(f"⚠️ 語音生成失敗: {e}")
            
            # 發送到 LINE Bot（使用修復版本）
            try:
                send_order_to_line_bot_fixed(line_user_id, {
                    'order_id': order.order_id,
                    'chinese_summary': order_result['zh_summary'],
                    'user_summary': order_result['user_summary'],
                    'voice_url': order_result.get('audio_url'),
                    'total_amount': order_result['total_amount']
                })
                print(f"✅ 成功發送訂單到 LINE Bot，使用者: {line_user_id}")
            except Exception as e:
                print(f"⚠️ LINE Bot 發送失敗: {e}")
            
            # 儲存 OCR 菜單和訂單摘要到資料庫（新增功能）
            try:
                from .helpers import save_ocr_menu_and_summary_to_database
                
                # 檢查是否為 OCR 菜單訂單
                if order_result.get('zh_items') and any(item.get('name', {}).get('original') for item in order_result['zh_items']):
                    print("🔄 檢測到 OCR 菜單訂單，開始儲存到資料庫...")
                    
                    # 準備 OCR 項目資料
                    ocr_items = []
                    for item in order_result['zh_items']:
                        if item.get('name', {}).get('original'):  # 只處理有原始中文名稱的項目
                            ocr_items.append({
                                'name': item['name'],
                                'price': item.get('price', 0),
                                'item_name': item.get('name', {}).get('original', ''),
                                'translated_name': item.get('name', {}).get('translated', '')
                            })
                    
                    if ocr_items:
                        # 儲存到資料庫
                        save_result = save_ocr_menu_and_summary_to_database(
                            order_id=order.order_id,
                            ocr_items=ocr_items,
                            chinese_summary=order_result['zh_summary'],
                            user_language_summary=order_result['user_summary'],
                            user_language=order_request.lang,
                            total_amount=order_result['total_amount'],
                            user_id=user.user_id,
                            store_id=store.store_id if store else None,  # 新增 store_id
                            store_name=store.store_name if store else '非合作店家'
                        )
                        
                        if save_result['success']:
                            print(f"✅ OCR 菜單和訂單摘要已成功儲存到資料庫")
                            print(f"   OCR 菜單 ID: {save_result['ocr_menu_id']}")
                            print(f"   訂單摘要 ID: {save_result['summary_id']}")
                        else:
                            print(f"⚠️ OCR 菜單和訂單摘要儲存失敗: {save_result['message']}")
                    else:
                        print("ℹ️ 沒有 OCR 項目需要儲存")
                else:
                    print("ℹ️ 此訂單不是 OCR 菜單訂單，跳過資料庫儲存")
            except Exception as e:
                print(f"⚠️ 儲存 OCR 菜單和訂單摘要時發生錯誤: {e}")
                # 不影響主要流程，繼續執行
            
            return jsonify({
                "success": True,
                "order_id": order.order_id,
                "message": "訂單建立成功",
                "total_amount": order_result['total_amount'],
                "items_count": len(order_result['zh_items'])
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "success": False,
                "error": f"資料庫操作失敗: {str(e)}"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"處理請求時發生錯誤: {str(e)}"
        }), 500

@api_bp.route('/voice/control', methods=['POST', 'OPTIONS'])
def voice_control():
    """語音控制 API - 處理 LINE Bot 的語音控制按鈕"""
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "請求資料為空"
            }), 400
        
        # 檢查必要欄位
        required_fields = ['user_id', 'action', 'order_id']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({
                "success": False,
                "error": "缺少必要欄位",
                "missing_fields": missing_fields
            }), 400
        
        user_id = data['user_id']
        action = data['action']
        order_id = data['order_id']
        
        # 根據動作處理語音控制
        from .helpers import send_voice_with_rate
        
        if action == 'replay':
            # 重新播放（正常語速）
            success = send_voice_with_rate(user_id, order_id, 1.0)
        elif action == 'slow':
            # 慢速播放
            success = send_voice_with_rate(user_id, order_id, 0.7)
        elif action == 'fast':
            # 快速播放
            success = send_voice_with_rate(user_id, order_id, 1.3)
        else:
            return jsonify({
                "success": False,
                "error": "不支援的語音控制動作"
            }), 400
        
        if success:
            return jsonify({
                "success": True,
                "message": f"語音控制成功: {action}",
                "user_id": user_id,
                "order_id": order_id
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": "語音控制失敗"
            }), 500
            
    except Exception as e:
        print(f"語音控制處理失敗：{e}")
        return jsonify({
            "success": False,
            "error": "語音控制處理失敗"
        }), 500

@api_bp.route('/line/webhook', methods=['POST', 'OPTIONS'])
def line_webhook():
    """LINE Bot Webhook 處理"""
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        data = request.get_json()
        
        if not data or 'events' not in data:
            return jsonify({"success": False, "error": "無效的 webhook 資料"}), 400
        
        # 處理每個事件
        for event in data['events']:
            event_type = event.get('type')
            user_id = event.get('source', {}).get('userId')
            
            if not user_id:
                continue
            
            if event_type == 'postback':
                # 處理 postback 事件（語音控制按鈕）
                postback_data = event.get('postback', {}).get('data', '')
                
                if postback_data.startswith('replay_voice:'):
                    order_id = postback_data.split(':')[1]
                    from .helpers import send_voice_with_rate
                    send_voice_with_rate(user_id, order_id, 1.0)
                    
                elif postback_data.startswith('slow_voice:'):
                    order_id = postback_data.split(':')[1]
                    from .helpers import send_voice_with_rate
                    send_voice_with_rate(user_id, order_id, 0.7)
                    
                elif postback_data.startswith('fast_voice:'):
                    order_id = postback_data.split(':')[1]
                    from .helpers import send_voice_with_rate
                    send_voice_with_rate(user_id, order_id, 1.3)
            
            elif event_type == 'message':
                # 處理文字訊息
                message_text = event.get('message', {}).get('text', '')
                
                if message_text.lower() in ['help', '幫助', '說明']:
                    # 發送幫助訊息
                    help_message = """
點餐小幫手使用說明：

1. 拍照辨識菜單
2. 選擇想要的品項
3. 確認訂單
4. 系統會自動生成中文語音檔
5. 在店家播放語音即可點餐

支援語音控制：
- 重新播放：正常語速
- 慢速播放：適合店家聽
- 快速播放：節省時間
                    """.strip()
                    
                    from .helpers import send_order_to_line_bot
                    send_order_to_line_bot(user_id, {
                        "chinese_summary": help_message,
                        "user_summary": help_message,
                        "voice_url": None,
                        "total_amount": 0
                    })
        
        return jsonify({"success": True}), 200
        
    except Exception as e:
        print(f"LINE Webhook 處理失敗：{e}")
        return jsonify({"success": False, "error": "Webhook 處理失敗"}), 500

# =============================================================================
# 根路徑處理
# 功能：處理根路徑的請求
# =============================================================================

def handle_root_path():
    """處理根路徑請求"""
    return jsonify({
        'message': '點餐小幫手後端 API',
        'version': '1.0.0',
        'endpoints': {
            'health': '/api/health',
            'stores': '/api/stores',
            'menu': '/api/menu/{store_id}',
            'upload': '/api/upload-menu-image',
            'orders': '/api/orders',
            'test': '/api/test'
        }
    })

@api_bp.route('/test/line-bot', methods=['GET', 'OPTIONS'])
def test_line_bot():
    """測試 LINE Bot 環境變數設定"""
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        import os
        
        # 檢查環境變數
        line_channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
        line_channel_secret = os.getenv('LINE_CHANNEL_SECRET')
        
        # 檢查其他必要環境變數
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        azure_speech_key = os.getenv('AZURE_SPEECH_KEY')
        azure_speech_region = os.getenv('AZURE_SPEECH_REGION')
        
        # 構建測試結果
        test_results = {
            "line_bot": {
                "channel_access_token": "✅ 已設定" if line_channel_access_token else "❌ 未設定",
                "channel_secret": "✅ 已設定" if line_channel_secret else "❌ 未設定"
            },
            "ai_services": {
                "gemini_api_key": "✅ 已設定" if gemini_api_key else "❌ 未設定",
                "azure_speech_key": "✅ 已設定" if azure_speech_key else "❌ 未設定",
                "azure_speech_region": "✅ 已設定" if azure_speech_region else "❌ 未設定"
            },
            "all_configured": all([
                line_channel_access_token,
                line_channel_secret,
                gemini_api_key,
                azure_speech_key,
                azure_speech_region
            ])
        }
        
        response = jsonify({
            "message": "LINE Bot 環境變數檢查",
            "test_results": test_results,
            "ready_for_production": test_results["all_configured"]
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
        
    except Exception as e:
        response = jsonify({
            "error": "環境變數檢查失敗",
            "details": str(e)
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

# =============================================================================
# 語音檔案服務
# 功能：提供語音檔案的靜態服務
# =============================================================================

@api_bp.route('/voices/<path:filename>')
def serve_voice(filename):
    """供外部（Line Bot）GET 語音檔用"""
    try:
        from .helpers import VOICE_DIR
        import os
        from flask import send_file, make_response
        from werkzeug.utils import secure_filename
        import mimetypes
        
        # 安全性檢查：只允許 .mp3 和 .wav 檔案
        if not (filename.endswith('.mp3') or filename.endswith('.wav')):
            return jsonify({"error": "不支援的檔案格式"}), 400
        
        # 防止路徑遍歷攻擊
        safe_filename = secure_filename(filename)
        if '..' in safe_filename or '/' in safe_filename:
            return jsonify({"error": "無效的檔案名稱"}), 400
        
        # 構建完整檔案路徑
        file_path = os.path.join(VOICE_DIR, safe_filename)
        
        # 檢查檔案是否存在
        if not os.path.exists(file_path):
            return jsonify({"error": "語音檔案不存在"}), 404
        
        # 檢查檔案大小
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return jsonify({"error": "語音檔案為空"}), 404
        
        # 根據檔案類型設定正確的 MIME type
        if filename.endswith('.mp3'):
            mimetype = 'audio/mpeg'
        else:  # .wav
            mimetype = 'audio/wav'
        
        # 使用 send_file 讓 Flask/werkzeug 處理 Range/ETag/Last-Modified
        response = send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=False,
            conditional=True  # 啟用 Range 與快取條件
        )
        
        # 設定必要的標頭
        response.headers["Accept-Ranges"] = "bytes"
        response.headers["Cache-Control"] = "public, max-age=86400"  # 24小時快取
        response.headers["Content-Length"] = str(file_size)
        
        print(f"提供語音檔案: {safe_filename}, 大小: {file_size} bytes, MIME: {mimetype}")
        return response
        
    except Exception as e:
        print(f"提供語音檔案失敗: {e}")
        return jsonify({"error": "語音檔案服務失敗"}), 500

@api_bp.route('/menu/ocr/user/<int:user_id>', methods=['GET'])
def get_user_ocr_menus(user_id):
    """查詢使用者的OCR菜單歷史"""
    try:
        # 查詢使用者的OCR菜單
        ocr_menus = OCRMenu.query.filter_by(user_id=user_id).order_by(OCRMenu.upload_time.desc()).all()
        
        if not ocr_menus:
            return jsonify({
                "success": True,
                "user_id": user_id,
                "ocr_menus": [],
                "total_count": 0
            })
        
        # 轉換為前端相容格式
        menus_data = []
        for ocr_menu in ocr_menus:
            # 查詢菜單項目數量
            item_count = OCRMenuItem.query.filter_by(ocr_menu_id=ocr_menu.ocr_menu_id).count()
            
            menus_data.append({
                'ocr_menu_id': ocr_menu.ocr_menu_id,
                'store_name': ocr_menu.store_name,
                'upload_time': ocr_menu.upload_time.isoformat() if ocr_menu.upload_time else None,
                'item_count': item_count,
                'user_id': ocr_menu.user_id
            })
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "ocr_menus": menus_data,
            "total_count": len(menus_data)
        })
        
    except Exception as e:
        current_app.logger.error(f"查詢使用者OCR菜單歷史錯誤: {str(e)}")
        return jsonify({'error': '無法載入OCR菜單歷史'}), 500

@api_bp.route('/orders/ocr', methods=['POST', 'OPTIONS'])
def create_ocr_order():
    """建立OCR菜單訂單"""
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "請求資料為空"}), 400
    
    # 檢查必要欄位
    required_fields = ['items', 'ocr_menu_id']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({
            "error": "訂單資料不完整",
            "missing_fields": missing_fields,
            "received_data": list(data.keys())
        }), 400
    
    try:
        # 處理 line_user_id（可選）
        line_user_id = data.get('line_user_id')
        if not line_user_id:
            # 為非 LINE 入口生成臨時 ID
            line_user_id = f"guest_{uuid.uuid4().hex[:8]}"
            guest_mode = True
        else:
            guest_mode = False

        # 查找或創建使用者
        user = User.query.filter_by(line_user_id=line_user_id).first()
        if not user:
            try:
                # 檢查語言是否存在，如果不存在就使用預設語言
                preferred_lang = data.get('language', 'zh')
                language = Language.query.get(preferred_lang)
                if not language:
                    # 如果指定的語言不存在，使用中文作為預設
                    preferred_lang = 'zh'
                    language = Language.query.get(preferred_lang)
                    if not language:
                        # 如果連中文都不存在，創建基本語言資料
                        from tools.manage_translations import init_languages
                        init_languages()
                
                # 為訪客創建臨時使用者
                user = User(
                    line_user_id=line_user_id,
                    preferred_lang=preferred_lang
                )
                db.session.add(user)
                db.session.flush()  # 先產生 user_id，但不提交
            except Exception as e:
                db.session.rollback()
                return jsonify({
                    "error": "建立使用者失敗",
                    "details": str(e)
                }), 500

        # 驗證OCR菜單是否存在
        ocr_menu_id = data.get('ocr_menu_id')
        ocr_menu = OCRMenu.query.get(ocr_menu_id)
        if not ocr_menu:
            return jsonify({
                "error": "找不到指定的OCR菜單",
                "ocr_menu_id": ocr_menu_id
            }), 404

        total_amount = 0
        order_items_to_create = []
        order_details = []
        validation_errors = []
        
        for i, item_data in enumerate(data['items']):
            # 支援多種欄位名稱格式
            menu_item_id = item_data.get('menu_item_id') or item_data.get('id')
            quantity = item_data.get('quantity') or item_data.get('qty') or item_data.get('quantity_small')
            
            # 將 menu_item_id 轉換為字串以便檢查前綴
            menu_item_id_str = str(menu_item_id) if menu_item_id is not None else None
            
            # 檢查是否為OCR菜單項目（以 ocr_ 開頭）
            if menu_item_id_str and menu_item_id_str.startswith('ocr_'):
                # 處理OCR菜單項目
                price = item_data.get('price') or item_data.get('price_small') or item_data.get('price_unit') or 0
                
                # 處理新的雙語格式 {name: {original: "中文", translated: "English"}}
                if item_data.get('name') and isinstance(item_data['name'], dict):
                    item_name = item_data['name'].get('original') or f"項目 {i+1}"
                    translated_name = item_data['name'].get('translated') or item_name
                else:
                    item_name = item_data.get('item_name') or item_data.get('name') or item_data.get('original_name') or f"項目 {i+1}"
                    translated_name = item_data.get('translated_name') or item_data.get('en_name') or item_name
                
                # 驗證數量
                if not quantity:
                    validation_errors.append(f"項目 {i+1}: 缺少 quantity 或 qty 欄位")
                    continue
                
                try:
                    quantity = int(quantity)
                    if quantity <= 0:
                        validation_errors.append(f"項目 {i+1}: 數量必須大於 0")
                        continue
                except (ValueError, TypeError):
                    validation_errors.append(f"項目 {i+1}: 數量格式錯誤，必須是整數")
                    continue
                
                # 計算小計
                subtotal = int(price) * quantity
                total_amount += subtotal
                
                # 為OCR項目創建一個臨時的 MenuItem 記錄
                try:
                    # 檢查是否已經有對應的臨時菜單項目
                    temp_menu_item = MenuItem.query.filter_by(item_name=item_name).first()
                    
                    if not temp_menu_item:
                        # 創建新的臨時菜單項目
                        from app.models import Menu
                        
                        # 找到或創建一個臨時菜單
                        temp_menu = Menu.query.filter_by(store_id=data.get('store_id', 1)).first()
                        if not temp_menu:
                            temp_menu = Menu(
                                store_id=data.get('store_id', 1), 
                                version=1,
                                effective_date=datetime.datetime.now()  # 明確設置 effective_date
                            )
                            db.session.add(temp_menu)
                            db.session.flush()
                        
                        temp_menu_item = MenuItem(
                            menu_id=temp_menu.menu_id,
                            item_name=item_name,
                            price_small=int(price),
                            price_big=int(price)  # 使用相同價格
                        )
                        db.session.add(temp_menu_item)
                        db.session.flush()  # 獲取 menu_item_id
                    
                    # 使用臨時菜單項目的 ID
                    order_items_to_create.append(OrderItem(
                        menu_item_id=temp_menu_item.menu_item_id,
                        quantity_small=quantity,
                        subtotal=subtotal,
                        original_name=item_name,
                        translated_name=translated_name
                    ))
                    
                    # 建立訂單明細供確認
                    order_details.append({
                        'menu_item_id': temp_menu_item.menu_item_id,
                        'item_name': item_name,
                        'translated_name': translated_name,
                        'quantity': quantity,
                        'price': int(price),
                        'subtotal': subtotal,
                        'is_ocr': True
                    })
                    
                except Exception as e:
                    validation_errors.append(f"項目 {i+1}: 創建OCR菜單項目失敗 - {str(e)}")
                    continue
            else:
                validation_errors.append(f"項目 {i+1}: 不是有效的OCR菜單項目")

        if validation_errors:
            return jsonify({
                "error": "訂單資料驗證失敗",
                "validation_errors": validation_errors,
                "received_items": data['items']
            }), 400

        if not order_items_to_create:
            return jsonify({
                "error": "沒有選擇任何商品",
                "received_items": data['items']
            }), 400

        try:
            # 使用 store resolver 解析店家 ID
            raw_store_id = data.get('store_id', 1)
            frontend_store_name = data.get('store_name')
            try:
                from .store_resolver import resolve_store_id
                store_db_id = resolve_store_id(raw_store_id, frontend_store_name)
                print(f"✅ OCR訂單店家ID解析成功: {raw_store_id} -> {store_db_id}")
                print(f"📋 使用前端店名: {frontend_store_name}")
            except Exception as e:
                print(f"❌ OCR訂單店家ID解析失敗: {e}")
                # 如果解析失敗，使用預設值
                store_db_id = 1
                print(f"⚠️ 使用預設店家ID: {store_db_id}")
            
            new_order = Order(
                user_id=user.user_id,
                store_id=store_db_id,
                total_amount=total_amount,
                items=order_items_to_create
            )
            
            db.session.add(new_order)
            db.session.commit()
            
            # 建立完整訂單確認內容
            from .helpers import create_complete_order_confirmation, send_complete_order_notification, generate_voice_order
            
            print(f"🔧 準備生成訂單確認...")
            print(f"📋 訂單ID: {new_order.order_id}")
            print(f"📋 用戶偏好語言: {user.preferred_lang}")
            
            try:
                # 對於 OCR 訂單，使用前端傳遞的店名
                frontend_store_name = data.get('store_name')
                order_confirmation = create_complete_order_confirmation(new_order.order_id, user.preferred_lang, frontend_store_name)
                print(f"✅ 訂單確認生成成功")
                print(f"📋 確認內容: {order_confirmation}")
                print(f"📋 使用前端店名: {frontend_store_name}")
            except Exception as e:
                print(f"❌ 訂單確認生成失敗: {e}")
                print(f"錯誤類型: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                raise e
            
            # 生成中文語音檔
            print(f"🔧 準備生成語音檔...")
            try:
                voice_path = generate_voice_order(new_order.order_id)
                print(f"✅ 語音檔生成成功: {voice_path}")
            except Exception as e:
                print(f"❌ 語音檔生成失敗: {e}")
                print(f"錯誤類型: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                voice_path = None
            
            # 建立訂單摘要並儲存到資料庫
            try:
                from .helpers import save_ocr_menu_and_summary_to_database
                
                # 準備OCR項目資料
                ocr_items = []
                for item in order_details:
                    if item.get('is_ocr'):
                        ocr_items.append({
                            'name': {
                                'original': item.get('item_name', ''),
                                'translated': item.get('translated_name', item.get('item_name', ''))
                            },
                            'price': item.get('price', 0),
                            'item_name': item.get('item_name', ''),
                            'translated_name': item.get('translated_name', item.get('item_name', ''))
                        })
                
                if ocr_items:
                    # 儲存到資料庫
                    save_result = save_ocr_menu_and_summary_to_database(
                        order_id=new_order.order_id,
                        ocr_items=ocr_items,
                        chinese_summary=order_confirmation.get('chinese', 'OCR訂單摘要'),
                        user_language_summary=order_confirmation.get('translated', 'OCR訂單摘要'),
                        user_language=data.get('language', 'zh'),
                        total_amount=total_amount,
                        user_id=user.user_id if user else None,
                        store_id=store_db_id,  # 使用解析後的店家ID
                        store_name=data.get('store_name', 'OCR店家')
                    )
                    
                    if save_result['success']:
                        print(f"✅ OCR訂單摘要已成功儲存到資料庫")
                        print(f"   OCR菜單ID: {save_result['ocr_menu_id']}")
                        print(f"   訂單摘要ID: {save_result['summary_id']}")
                    else:
                        print(f"⚠️ OCR訂單摘要儲存失敗: {save_result['message']}")
            except Exception as e:
                print(f"⚠️ 儲存OCR訂單摘要時發生錯誤: {e}")
                # 不影響主要流程，繼續執行
            
            # 只在非訪客模式下發送 LINE 通知
            if not guest_mode:
                send_complete_order_notification(new_order.order_id, data.get('store_name'))
            
            return jsonify({
                "message": "OCR訂單建立成功", 
                "order_id": new_order.order_id,
                "order_details": order_details,
                "total_amount": total_amount,
                "confirmation": order_confirmation,
                "voice_generated": voice_path is not None,
                "ocr_menu_id": ocr_menu_id,
                "store_name": data.get('store_name', 'OCR店家')
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "error": "OCR訂單建立失敗",
                "details": str(e)
            }), 500
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "OCR訂單建立失敗",
            "details": str(e)
        }), 500

@api_bp.route('/stores/resolve', methods=['GET', 'POST', 'OPTIONS'])
def resolve_store():
    """解析店家識別碼（測試用）"""
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        if request.method == 'GET':
            # GET 請求：從查詢參數取得
            place_id = request.args.get('place_id')
            store_name = request.args.get('store_name')
        else:
            # POST 請求：從 JSON 取得
            data = request.get_json() or {}
            place_id = data.get('place_id')
            store_name = data.get('store_name')
        
        if not place_id:
            response = jsonify({
                "error": "需要提供 place_id 參數",
                "usage": {
                    "GET": "/api/stores/resolve?place_id=ChlJ0boght2rQjQRsH-_buCo3S4&store_name=店家名稱",
                    "POST": '{"place_id": "ChlJ0boght2rQjQRsH-_buCo3S4", "store_name": "店家名稱"}'
                }
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        # 使用 store resolver 解析
        from .store_resolver import resolve_store_id, validate_store_id
        
        # 先驗證格式
        if not validate_store_id(place_id):
            response = jsonify({
                "error": "無效的 place_id 格式",
                "place_id": place_id,
                "valid_formats": [
                    "整數 (如: 123)",
                    "數字字串 (如: '456')", 
                    "Google Place ID (如: 'ChlJ0boght2rQjQRsH-_buCo3S4')"
                ]
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        # 解析店家 ID
        store_db_id = resolve_store_id(place_id, store_name)
        
        response_data = {
            "success": True,
            "original_place_id": place_id,
            "resolved_store_id": store_db_id,
            "store_name": store_name or f"店家_{place_id[:8]}",
            "message": f"成功解析店家識別碼: {place_id} -> {store_db_id}"
        }
        
        response = jsonify(response_data)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200
        
    except Exception as e:
        print(f"❌ Store resolver 測試失敗: {e}")
        response = jsonify({
            "error": "店家識別碼解析失敗",
            "details": str(e),
            "place_id": place_id if 'place_id' in locals() else None
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@api_bp.route('/admin/menu/process-ocr', methods=['POST', 'OPTIONS'])
def admin_process_menu_ocr():
    """
    後台管理系統專用的菜單辨識 API
    功能：接收菜單圖片，進行 OCR 辨識，直接儲存到資料庫
    回應：只返回 OCR 菜單 ID 和基本資訊，不包含完整的菜單資料
    
    注意：此端點僅供後台管理系統使用，LIFF 前端請使用 /api/menu/process-ocr
    """
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    # 後台管理系統驗證（可選）
    admin_token = request.form.get('admin_token')
    if admin_token:
        expected_token = os.getenv('ADMIN_API_TOKEN')
        if expected_token and admin_token != expected_token:
            response = jsonify({'error': '無效的管理員權限'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 403
    
    # 檢查是否有檔案
    if 'image' not in request.files:
        response = jsonify({'error': '沒有上傳檔案'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    
    file = request.files['image']
    
    # 檢查檔案名稱
    if file.filename == '':
        response = jsonify({'error': '沒有選擇檔案'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    
    # 檢查檔案格式
    if not allowed_file(file.filename):
        response = jsonify({'error': '不支援的檔案格式'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    
    # 取得參數
    raw_store_id = request.form.get('store_id')  # 店家 ID
    user_id = request.form.get('user_id', 'admin_system')  # 後台系統使用者 ID
    target_lang = request.form.get('lang', 'zh')  # 預設中文
    store_name = request.form.get('store_name', '')  # 店家名稱（可選）
    
    if not raw_store_id:
        response = jsonify({"error": "需要提供店家ID"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    
    # 使用 store resolver 解析店家 ID
    try:
        from .store_resolver import resolve_store_id
        store_db_id = resolve_store_id(raw_store_id)
        print(f"✅ 店家ID解析成功: {raw_store_id} -> {store_db_id}")
    except Exception as e:
        print(f"❌ 店家ID解析失敗: {e}")
        response = jsonify({
            "error": "店家ID格式錯誤",
            "details": str(e),
            "received_store_id": raw_store_id
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    
    try:
        # 儲存上傳的檔案
        filepath = save_uploaded_file(file)
        
        # 使用 Gemini API 處理圖片
        print("開始使用 Gemini API 處理圖片...")
        result = process_menu_with_gemini(filepath, target_lang)
        
        # 檢查處理結果
        if result and result.get('success', False):
            # 處理 user_id - 使用後台系統使用者
            if user_id:
                # 檢查是否已存在該使用者
                existing_user = User.query.filter_by(line_user_id=user_id).first()
                if existing_user:
                    actual_user_id = existing_user.user_id
                    print(f"✅ 使用現有使用者，ID: {actual_user_id} (後台系統: {user_id})")
                else:
                    # 創建後台系統使用者
                    new_user = User(
                        line_user_id=user_id,
                        preferred_lang=target_lang or 'zh'
                    )
                    db.session.add(new_user)
                    db.session.flush()  # 獲取 user_id
                    actual_user_id = new_user.user_id
                    print(f"✅ 創建後台系統使用者，ID: {actual_user_id} (後台系統: {user_id})")
            else:
                # 沒有提供 user_id，創建預設後台使用者
                temp_user = User(
                    line_user_id=f"admin_system_{int(time.time())}",
                    preferred_lang=target_lang or 'zh'
                )
                db.session.add(temp_user)
                db.session.flush()  # 獲取 user_id
                actual_user_id = temp_user.user_id
                print(f"✅ 創建預設後台使用者，ID: {actual_user_id}")
            
            # 建立 OCR 菜單記錄
            ocr_menu = OCRMenu(
                user_id=actual_user_id,
                store_id=store_db_id,
                store_name=store_name or result.get('store_info', {}).get('name', '後台管理店家')
            )
            db.session.add(ocr_menu)
            db.session.flush()  # 獲取 ocr_menu_id
            
            # 儲存菜單項目到資料庫
            menu_items = result.get('menu_items', [])
            saved_items = []
            
            for item in menu_items:
                # 儲存到 ocr_menu_items 表
                ocr_menu_item = OCRMenuItem(
                    ocr_menu_id=ocr_menu.ocr_menu_id,
                    item_name=str(item.get('original_name', '') or ''),
                    price_small=item.get('price', 0),
                    price_big=item.get('price', 0),  # 使用相同價格
                    translated_desc=str(item.get('translated_name', '') or '')
                )
                db.session.add(ocr_menu_item)
                
                # 收集已儲存的項目資訊
                saved_items.append({
                    'item_name': str(item.get('original_name', '') or ''),
                    'translated_name': str(item.get('translated_name', '') or ''),
                    'price': item.get('price', 0),
                    'description': str(item.get('description', '') or ''),
                    'category': str(item.get('category', '') or '其他')
                })
            
            # 提交資料庫變更
            db.session.commit()
            
            # 準備回應資料（簡化版，適合後台系統）
            response_data = {
                "success": True,
                "ocr_menu_id": ocr_menu.ocr_menu_id,
                "store_id": store_db_id,
                "store_name": ocr_menu.store_name,
                "total_items": len(saved_items),
                "upload_time": ocr_menu.upload_time.isoformat() if ocr_menu.upload_time else None,
                "processing_notes": result.get('processing_notes', ''),
                "message": f"成功辨識並儲存 {len(saved_items)} 個菜單項目"
            }
            
            response = jsonify(response_data)
            response.headers.add('Access-Control-Allow-Origin', '*')
            
            # 記錄成功日誌
            print(f"🎉 後台系統 API 成功回應 201 Created")
            print(f"📊 回應統計:")
            print(f"  - OCR菜單ID: {ocr_menu.ocr_menu_id}")
            print(f"  - 菜單項目數: {len(saved_items)}")
            print(f"  - 店家ID: {store_db_id}")
            print(f"  - 店家名稱: {ocr_menu.store_name}")
            
            return response, 201
        else:
            # 處理失敗
            error_message = result.get('error', '菜單處理失敗，請重新拍攝清晰的菜單照片')
            processing_notes = result.get('processing_notes', '')
            
            print(f"❌ 後台系統 API 返回錯誤")
            print(f"🔍 錯誤詳情:")
            print(f"  - 錯誤訊息: {error_message}")
            print(f"  - 處理備註: {processing_notes}")
            
            response = jsonify({
                "success": False,
                "error": error_message,
                "processing_notes": processing_notes
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 422
                
    except Exception as e:
        print(f"❌ 後台系統處理過程中發生錯誤: {e}")
        response = jsonify({
            "success": False,
            "error": "處理過程中發生錯誤",
            "details": str(e) if current_app.debug else '請稍後再試'
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@api_bp.route('/admin/menu/ocr/<int:ocr_menu_id>', methods=['GET', 'OPTIONS'])
def admin_get_ocr_menu(ocr_menu_id):
    """
    後台管理系統專用的 OCR 菜單查詢 API
    功能：根據 OCR 菜單 ID 查詢詳細的菜單資料
    
    注意：此端點僅供後台管理系統使用，LIFF 前端請使用 /api/menu/ocr/{ocr_menu_id}
    """
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    # 後台管理系統驗證（可選）
    admin_token = request.args.get('admin_token')
    if admin_token:
        expected_token = os.getenv('ADMIN_API_TOKEN')
        if expected_token and admin_token != expected_token:
            response = jsonify({'error': '無效的管理員權限'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 403
    
    try:
        # 查詢 OCR 菜單
        ocr_menu = OCRMenu.query.get(ocr_menu_id)
        if not ocr_menu:
            response = jsonify({
                "success": False,
                "error": "找不到指定的 OCR 菜單",
                "ocr_menu_id": ocr_menu_id
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 404
        
        # 查詢菜單項目
        menu_items = OCRMenuItem.query.filter_by(ocr_menu_id=ocr_menu_id).all()
        
        # 準備回應資料
        items_data = []
        for item in menu_items:
            items_data.append({
                'ocr_menu_item_id': item.ocr_menu_item_id,
                'item_name': item.item_name,
                'translated_desc': item.translated_desc,
                'price_small': item.price_small,
                'price_big': item.price_big
            })
        
        response_data = {
            "success": True,
            "ocr_menu": {
                "ocr_menu_id": ocr_menu.ocr_menu_id,
                "store_id": ocr_menu.store_id,
                "store_name": ocr_menu.store_name,
                "user_id": ocr_menu.user_id,
                "upload_time": ocr_menu.upload_time.isoformat() if ocr_menu.upload_time else None,
                "items": items_data,
                "total_items": len(items_data)
            }
        }
        
        response = jsonify(response_data)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200
        
    except Exception as e:
        print(f"❌ 查詢 OCR 菜單失敗: {e}")
        response = jsonify({
            "success": False,
            "error": "查詢失敗",
            "details": str(e) if current_app.debug else '請稍後再試'
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@api_bp.route('/admin/menu/ocr', methods=['GET', 'OPTIONS'])
def admin_list_ocr_menus():
    """
    後台管理系統專用的 OCR 菜單列表 API
    功能：列出所有 OCR 菜單的基本資訊
    
    注意：此端點僅供後台管理系統使用，LIFF 前端請使用 /api/menu/ocr/user/{user_id}
    """
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    # 後台管理系統驗證（可選）
    admin_token = request.args.get('admin_token')
    if admin_token:
        expected_token = os.getenv('ADMIN_API_TOKEN')
        if expected_token and admin_token != expected_token:
            response = jsonify({'error': '無效的管理員權限'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 403
    
    try:
        # 取得查詢參數
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        store_id = request.args.get('store_id', type=int)
        
        # 建立查詢
        query = OCRMenu.query
        
        # 如果指定了店家 ID，進行過濾
        if store_id:
            query = query.filter_by(store_id=store_id)
        
        # 按上傳時間倒序排列
        query = query.order_by(OCRMenu.upload_time.desc())
        
        # 分頁查詢
        pagination = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        # 準備回應資料
        menus_data = []
        for ocr_menu in pagination.items:
            # 查詢每個菜單的項目數量
            item_count = OCRMenuItem.query.filter_by(ocr_menu_id=ocr_menu.ocr_menu_id).count()
            
            menus_data.append({
                'ocr_menu_id': ocr_menu.ocr_menu_id,
                'store_id': ocr_menu.store_id,
                'store_name': ocr_menu.store_name,
                'user_id': ocr_menu.user_id,
                'upload_time': ocr_menu.upload_time.isoformat() if ocr_menu.upload_time else None,
                'item_count': item_count
            })
        
        response_data = {
            "success": True,
            "ocr_menus": menus_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev
            }
        }
        
        response = jsonify(response_data)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200
        
    except Exception as e:
        print(f"❌ 查詢 OCR 菜單列表失敗: {e}")
        response = jsonify({
            "success": False,
            "error": "查詢失敗",
            "details": str(e) if current_app.debug else '請稍後再試'
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@api_bp.route('/store/resolve', methods=['GET', 'OPTIONS'])
def resolve_store_for_frontend():
    """解析店家識別碼（前端專用，回傳合作狀態和翻譯店名）"""
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        place_id = request.args.get('place_id')
        name = request.args.get('name', '')
        lang = request.args.get('lang', 'en')
        
        if not place_id:
            response = jsonify({
                "error": "需要提供 place_id 參數",
                "usage": "/api/store/resolve?place_id=ChlJ0boght2rQjQRsH-_buCo3S4&name=店家名稱&lang=en"
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        # 使用新的翻譯服務進行語言碼正規化
        from .translation_service import normalize_lang, translate_text
        normalized_lang = normalize_lang(lang)
        
        # 查詢店家
        store = Store.query.filter_by(place_id=place_id).first()
        
        if store:
            # 合作店家
            original_name = store.store_name
            display_name = translate_text(original_name, normalized_lang)
            
            response_data = {
                "is_partner": True,
                "store_id": store.store_id,
                "original_name": original_name,
                "display_name": display_name,
                "place_id": place_id
            }
        else:
            # 非合作店家
            original_name = name or f"店家_{place_id[:8]}"
            display_name = translate_text(original_name, normalized_lang)
            
            response_data = {
                "is_partner": False,
                "original_name": original_name,
                "display_name": display_name,
                "place_id": place_id
            }
        
        response = jsonify(response_data)
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Cache-Control', 'public, max-age=300')  # 5分鐘快取
        return response, 200
        
    except Exception as e:
        current_app.logger.error(f"店家解析失敗: {str(e)}")
        # 即使出錯也要回傳 200，避免前端卡在 Preparing...
        fallback_name = request.args.get('name') or f"店家_{request.args.get('place_id', 'unknown')[:8]}"
        from .translation_service import normalize_lang, translate_text
        normalized_lang = normalize_lang(request.args.get('lang', 'en'))
        display_name = translate_text(fallback_name, normalized_lang)
        
        response_data = {
            "is_partner": False,
            "original_name": fallback_name,
            "display_name": display_name,
            "place_id": request.args.get('place_id', ''),
            "error": "店家解析失敗，使用預設值"
        }
        
        response = jsonify(response_data)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200

@api_bp.route('/partner/menu', methods=['GET', 'OPTIONS'])
def get_partner_menu():
    """取得合作店家菜單（支援多語言翻譯）"""
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        store_id = request.args.get('store_id')
        lang = request.args.get('lang', 'en')
        
        if not store_id:
            response = jsonify({
                "error": "需要提供 store_id 參數",
                "usage": "/api/partner/menu?store_id=123&lang=en"
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        # 使用新的翻譯服務進行語言碼正規化
        from .translation_service import normalize_lang, translate_text
        
        normalized_lang = normalize_lang(lang)
        
        # 檢查店家是否存在
        store = Store.query.get(store_id)
        if not store:
            response = jsonify({"error": "找不到店家"})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 404
        
        # 查詢菜單
        menus = Menu.query.filter(Menu.store_id == store_id).all()
        if not menus:
            response = jsonify({
                "error": "此店家目前沒有菜單",
                "store_id": store_id,
                "store_name": store.store_name
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 404
        
        # 查詢菜單項目
        menu_ids = [menu.menu_id for menu in menus]
        menu_items = MenuItem.query.filter(
            MenuItem.menu_id.in_(menu_ids),
            MenuItem.price_small > 0
        ).all()
        
        if not menu_items:
            response = jsonify({
                "error": "此店家目前沒有菜單項目",
                "store_id": store_id,
                "store_name": store.store_name
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 404
        
        # 翻譯菜單項目
        translated_items = []
        for item in menu_items:
            translated_item = {
                "id": item.menu_item_id,
                "name": translate_text(item.item_name, normalized_lang),
                "translated_name": translate_text(item.item_name, normalized_lang),  # 為了前端兼容性
                "original_name": item.item_name,
                "price_small": item.price_small,
                "price_large": item.price_big,  # 修正：使用 price_big 而不是 price_large
                "category": "",  # 修正：資料庫中沒有 category 欄位
                "original_category": ""
            }
            translated_items.append(translated_item)
        
        response_data = {
            "store_id": store_id,
            "store_name": store.store_name,
            "user_language": lang,
            "normalized_language": normalized_lang,
            "items": translated_items
        }
        
        response = jsonify(response_data)
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Cache-Control', 'public, max-age=300')  # 5分鐘快取
        return response, 200
        
    except Exception as e:
        current_app.logger.error(f"菜單載入錯誤: {str(e)}")
        # 即使出錯也要回傳 200，避免前端卡在 Preparing...
        response_data = {
            "store_id": request.args.get('store_id', ''),
            "store_name": "",
            "user_language": lang,
            "normalized_language": normalize_lang(lang),
            "items": [],
            "error": "菜單載入失敗，使用預設值"
        }
        
        response = jsonify(response_data)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200

# 新增：暫存 OCR 資料的記憶體儲存
_ocr_temp_storage = {}

@api_bp.route('/menu/process-ocr-optimized', methods=['POST', 'OPTIONS'])
def process_menu_ocr_optimized():
    """
    優化的 OCR 處理流程
    - 直接 OCR 辨識
    - 即時翻譯
    - 暫存結果
    - 不立即儲存資料庫
    """
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    try:
        # 檢查是否有檔案上傳
        if 'image' not in request.files:
            return jsonify({"error": "沒有上傳圖片"}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "沒有選擇檔案"}), 400
        
        # 獲取使用者語言偏好
        line_user_id = request.form.get('line_user_id')
        user_language = request.form.get('language', 'en')
        
        # 查找使用者
        user = User.query.filter_by(line_user_id=line_user_id).first()
        if not user:
            return jsonify({"error": "找不到使用者"}), 404
        
        print(f"🔍 開始優化 OCR 處理...")
        print(f"📋 使用者: {user.line_user_id}, 語言: {user_language}")
        
        # 1. OCR 辨識
        from .helpers import process_menu_with_gemini
        import tempfile
        import os
        
        # 將上傳的文件保存到臨時文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            file.save(temp_file.name)
            temp_file_path = temp_file.name
        
        try:
            ocr_result = process_menu_with_gemini(temp_file_path, user_language)
        finally:
            # 清理臨時文件
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
        if not ocr_result or not ocr_result.get('success') or 'menu_items' not in ocr_result:
            error_msg = ocr_result.get('error', 'OCR 辨識失敗') if ocr_result else 'OCR 辨識失敗'
            return jsonify({"error": error_msg}), 500
        
        # 2. 處理 OCR 結果
        from .helpers import translate_text_batch, contains_cjk
        
        # 處理店家名稱
        store_info = ocr_result.get('store_info', {})
        store_name_original = store_info.get('name', '非合作店家')
        if store_name_original and contains_cjk(store_name_original):
            store_name_translated = translate_text_batch([store_name_original], user_language, 'zh')[0]
        else:
            store_name_translated = store_name_original or 'Non-partner Store'
        
        # 處理菜品項目
        menu_items = ocr_result.get('menu_items', [])
        translated_items = []
        
        for item in menu_items:
            item_name_original = item.get('original_name', '')
            item_name_translated = item.get('translated_name', '')
            item_price = item.get('price', 0)
            
            # 確保有原始名稱
            if not item_name_original:
                continue
            
            # 強制確保 original_name 為中文
            if not contains_cjk(item_name_original):
                if contains_cjk(item_name_translated):
                    # 如果 translated_name 是中文，則交換
                    item_name_original, item_name_translated = item_name_translated, item_name_original
                    print(f"🔄 交換菜名：original='{item_name_original}', translated='{item_name_translated}'")
                else:
                    # 如果兩個都是英文，強制翻譯 original_name 為中文
                    try:
                        item_name_original = translate_text_batch([item_name_original], 'zh', user_language)[0]
                        print(f"🔄 強制翻譯為中文：'{item_name_original}'")
                    except Exception as e:
                        print(f"❌ 翻譯失敗：{e}")
                        # 如果翻譯失敗，跳過這個項目
                        continue
            
            # 如果沒有翻譯名稱，使用原始名稱
            if not item_name_translated:
                item_name_translated = item_name_original
            
            # 最終驗證：確保 original_name 包含中日韓字元
            if not contains_cjk(item_name_original):
                print(f"⚠️ 警告：original_name 仍不包含中日韓字元：'{item_name_original}'，跳過此項目")
                continue
            
            translated_items.append({
                'id': f"temp_item_{len(translated_items) + 1}",
                'original_name': item_name_original,  # 中文原始名稱
                'translated_name': item_name_translated,  # 翻譯後名稱
                'price': item_price
            })
        
        # 3. 生成暫存 ID
        temp_ocr_id = f"temp_ocr_{uuid.uuid4().hex[:8]}"
        
        # 4. 暫存結果
        _ocr_temp_storage[temp_ocr_id] = {
            'user_id': user.user_id,
            'user_language': user_language,
            'store_name_original': store_name_original,  # 中文店名
            'store_name_translated': store_name_translated,  # 翻譯店名
            'items': translated_items,
            'created_at': datetime.datetime.now(),
            'expires_at': datetime.datetime.now() + datetime.timedelta(hours=1)  # 1小時後過期
        }
        
        print(f"✅ OCR 處理完成，暫存 ID: {temp_ocr_id}")
        print(f"📋 店家: {store_name_original} → {store_name_translated}")
        print(f"📋 菜品數量: {len(translated_items)}")
        
        # 5. 返回結果
        return jsonify({
            "success": True,
            "ocr_menu_id": temp_ocr_id,
            "store_name": {
                "original": store_name_original,
                "translated": store_name_translated
            },
            "items": translated_items,
            "message": "OCR 處理完成，請選擇菜品"
        })
        
    except Exception as e:
        print(f"❌ OCR 處理錯誤: {e}")
        return jsonify({"error": f"OCR 處理失敗: {str(e)}"}), 500

@api_bp.route('/orders/ocr-optimized', methods=['POST', 'OPTIONS'])
def create_ocr_order_optimized():
    """
    優化的 OCR 訂單建立
    - 使用暫存的 OCR 資料
    - 生成摘要和語音
    - 發送到 LINE Bot
    - 不立即儲存資料庫
    """
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "請求資料為空"}), 400
    
    # 檢查必要欄位
    required_fields = ['items', 'ocr_menu_id']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({
            "error": "訂單資料不完整",
            "missing_fields": missing_fields,
            "received_data": list(data.keys())
        }), 400
    
    try:
        # 獲取暫存的 OCR 資料
        temp_ocr_id = data.get('ocr_menu_id')
        if temp_ocr_id not in _ocr_temp_storage:
            return jsonify({"error": "OCR 資料已過期或不存在"}), 404
        
        ocr_data = _ocr_temp_storage[temp_ocr_id]
        
        # 檢查是否過期
        if datetime.datetime.now() > ocr_data['expires_at']:
            del _ocr_temp_storage[temp_ocr_id]
            return jsonify({"error": "OCR 資料已過期"}), 410
        
        print(f"🔍 開始處理優化 OCR 訂單...")
        print(f"📋 暫存 ID: {temp_ocr_id}")
        print(f"📋 使用者 ID: {ocr_data['user_id']}")
        print(f"📋 語言: {ocr_data['user_language']}")
        
        # 計算總金額
        total_amount = 0
        order_items_data = []
        
        for item_data in data['items']:
            item_id = item_data.get('id')
            quantity = item_data.get('quantity', 1)
            
            # 找到對應的 OCR 項目
            ocr_item = None
            for item in ocr_data['items']:
                if item['id'] == item_id:
                    ocr_item = item
                    break
            
            if not ocr_item:
                continue
            
            price = ocr_item['price']
            subtotal = price * quantity
            total_amount += subtotal
            
            order_items_data.append({
                'original_name': ocr_item['original_name'],  # 中文原始名稱
                'translated_name': ocr_item['translated_name'],  # 翻譯後名稱
                'quantity': quantity,
                'price': price,
                'subtotal': subtotal
            })
        
        print(f"📋 總金額: {total_amount}")
        print(f"📋 項目數量: {len(order_items_data)}")
        
        # 生成雙語摘要
        chinese_summary = f"店家: {ocr_data['store_name_original']}\n"
        user_language_summary = f"Store: {ocr_data['store_name_translated']}\n"
        
        for item in order_items_data:
            chinese_summary += f"{item['original_name']} x{item['quantity']} ${item['subtotal']}\n"
            user_language_summary += f"{item['translated_name']} x{item['quantity']} ${item['subtotal']}\n"
        
        chinese_summary += f"總計: ${total_amount}"
        user_language_summary += f"Total: ${total_amount}"
        
        print(f"📝 中文摘要:\n{chinese_summary}")
        print(f"📝 外文摘要:\n{user_language_summary}")
        
        # 生成語音檔案
        from .helpers import generate_voice_order
        voice_file_path = generate_voice_order(chinese_summary)
        
        # 發送到 LINE Bot
        from .helpers import send_complete_order_notification
        user = User.query.get(ocr_data['user_id'])
        if user:
            send_complete_order_notification(
                user.line_user_id,
                chinese_summary,
                user_language_summary,
                voice_file_path,
                ocr_data['user_language']
            )
        
        # 準備儲存資料（但不立即儲存）
        save_data = {
            'user_id': ocr_data['user_id'],
            'store_name': {
                'original': ocr_data['store_name_original'],
                'translated': ocr_data['store_name_translated']
            },
            'items': order_items_data,
            'total_amount': total_amount,
            'chinese_summary': chinese_summary,
            'user_language_summary': user_language_summary,
            'user_language': ocr_data['user_language'],
            'voice_file_path': voice_file_path
        }
        
        print(f"📋 準備儲存資料結構:")
        print(f"📋 save_data 內容: {save_data}")
        print(f"📋 order_items_data 內容: {order_items_data}")
        
        # 暫存儲存資料
        _ocr_temp_storage[f"{temp_ocr_id}_save_data"] = save_data
        print(f"✅ 儲存資料已暫存到 _ocr_temp_storage[{temp_ocr_id}_save_data]")
        
        print(f"✅ 優化 OCR 訂單處理完成")
        
        return jsonify({
            "success": True,
            "message": "訂單已發送到 LINE Bot",
            "save_data_id": f"{temp_ocr_id}_save_data",
            "chinese_summary": chinese_summary,
            "user_language_summary": user_language_summary
        })
        
    except Exception as e:
        print(f"❌ 優化 OCR 訂單處理錯誤: {e}")
        return jsonify({"error": f"訂單處理失敗: {str(e)}"}), 500

@api_bp.route('/orders/save-ocr-data', methods=['POST', 'OPTIONS'])
def save_ocr_data():
    """
    統一儲存 OCR 資料到資料庫
    - 儲存中文菜單到 ocr_menu_items
    - 儲存外文菜單到 ocr_menu_translations
    - 儲存訂單到 orders 和 order_items
    """
    # 處理 OPTIONS 預檢請求
    if request.method == 'OPTIONS':
        return handle_cors_preflight()
    
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "請求資料為空"}), 400
    
    # 檢查必要欄位
    required_fields = ['save_data_id']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({
            "error": "資料不完整",
            "missing_fields": missing_fields
        }), 400
    
    try:
        save_data_id = data.get('save_data_id')
        if save_data_id not in _ocr_temp_storage:
            return jsonify({"error": "儲存資料不存在或已過期"}), 404
        
        save_data = _ocr_temp_storage[save_data_id]
        
        print(f"🔍 開始儲存 OCR 資料到資料庫...")
        print(f"📋 儲存資料 ID: {save_data_id}")
        print(f"📋 暫存資料內容: {save_data}")
        print(f"📋 項目數量: {len(save_data['items'])}")
        
        # 檢查每個項目的資料結構
        for i, item in enumerate(save_data['items']):
            print(f"📋 項目 {i+1}: original_name='{item.get('original_name')}', translated_name='{item.get('translated_name')}', price={item.get('price')}, quantity={item.get('quantity')}")
        
        # 使用交易確保資料一致性
        with db.session.begin():
            # 1. 建立 OCR 菜單記錄
            ocr_menu = OCRMenu(
                user_id=save_data['user_id'],
                store_id=1,  # 非合作店家使用預設 store_id
                store_name=save_data['store_name']['original']
            )
            db.session.add(ocr_menu)
            db.session.flush()  # 獲取 ocr_menu_id
            
            print(f"✅ 建立 OCR 菜單記錄: {ocr_menu.ocr_menu_id}")
            
            # 2. 儲存 OCR 菜單項目
            for item in save_data['items']:
                ocr_menu_item = OCRMenuItem(
                    ocr_menu_id=ocr_menu.ocr_menu_id,
                    item_name=item['original_name'],  # 中文菜名
                    price_small=item['price'],
                    translated_desc=item['translated_name']  # 外文菜名
                )
                db.session.add(ocr_menu_item)
                db.session.flush()  # 獲取 ocr_menu_item_id
                
                # 3. 儲存翻譯資料
                ocr_menu_translation = OCRMenuTranslation(
                    menu_item_id=ocr_menu_item.ocr_menu_item_id,
                    lang_code=save_data['user_language'],
                    description=item['translated_name']
                )
                db.session.add(ocr_menu_translation)
            
            # 4. 建立訂單記錄
            order = Order(
                user_id=save_data['user_id'],
                store_id=1,  # 非合作店家使用預設 store_id
                total_amount=save_data['total_amount'],
                status='pending'
            )
            db.session.add(order)
            db.session.flush()  # 獲取 order_id
            
            print(f"✅ 建立訂單記錄: {order.order_id}")
            
            # 5. 儲存訂單項目（包含雙語摘要）
            for i, item in enumerate(save_data['items']):
                print(f"📋 建立 OrderItem {i+1}: original_name='{item.get('original_name')}', translated_name='{item.get('translated_name')}'")
                
                order_item = OrderItem(
                    order_id=order.order_id,
                    temp_item_id=f"ocr_{ocr_menu.ocr_menu_id}_{i+1}",
                    temp_item_name=item['original_name'],  # 中文菜名
                    temp_item_price=item['price'],
                    quantity_small=item['quantity'],
                    subtotal=item['subtotal'],
                    original_name=item['original_name'],  # 中文菜名
                    translated_name=item['translated_name'],  # 外文菜名
                    is_temp_item=1
                )
                db.session.add(order_item)
                print(f"✅ OrderItem {i+1} 已加入 session")
        
        # 清理暫存資料
        del _ocr_temp_storage[save_data_id]
        
        print(f"✅ OCR 資料儲存完成")
        print(f"📋 OCR 菜單 ID: {ocr_menu.ocr_menu_id}")
        print(f"📋 訂單 ID: {order.order_id}")
        
        return jsonify({
            "success": True,
            "message": "資料已成功儲存到資料庫",
            "ocr_menu_id": ocr_menu.ocr_menu_id,
            "order_id": order.order_id,
            "chinese_summary": save_data['chinese_summary'],
            "user_language_summary": save_data['user_language_summary']
        })
        
    except Exception as e:
        print(f"❌ 儲存 OCR 資料錯誤: {e}")
        db.session.rollback()
        return jsonify({"error": f"儲存失敗: {str(e)}"}), 500
# =============================================================================
# 檔案名稱：app/models.py
# 功能描述：定義所有資料庫模型，包含整個點餐系統的資料結構
# 主要職責：
# - 定義資料庫表格結構
# - 建立模型之間的關聯關係
# - 提供資料庫操作的 ORM 介面
# 包含模型：
# - 使用者管理：User, Language
# - 店家管理：Store, StoreTranslation
# - 菜單管理：Menu, MenuItem, MenuTranslation
# - 訂單管理：Order, OrderItem
# - 語音檔案：VoiceFile
# - AI 處理：GeminiProcessing
# =============================================================================

from flask_sqlalchemy import SQLAlchemy
import datetime

# =============================================================================
# SQLAlchemy 資料庫物件建立區塊
# 功能：建立 SQLAlchemy 資料庫物件，用於所有資料庫操作
# 作用：提供 ORM（物件關聯對應）功能，讓 Python 程式碼可以直接操作資料庫
# =============================================================================
db = SQLAlchemy()

# =============================================================================
# 語言設定模型區塊
# 功能：定義系統支援的語言設定
# 用途：管理多語言支援，包含中文、英文、日文、韓文等
# 欄位：
# - lang_code：語言代碼（如 'zh', 'en', 'ja', 'ko'）
# - lang_name：語言名稱（如 '中文', 'English', '日本語'）
# =============================================================================
class Language(db.Model):
    __tablename__ = 'languages'
    line_lang_code = db.Column(db.String(10), primary_key=True)
    translation_lang_code = db.Column(db.String(5), nullable=False)
    stt_lang_code = db.Column(db.String(15), nullable=False)
    lang_name = db.Column(db.String(50), nullable=False)

# =============================================================================
# 使用者模型區塊
# 功能：定義 LINE Bot 使用者的資料結構
# 用途：儲存使用者的基本資訊和偏好設定
# 欄位：
# - user_id：使用者唯一識別碼
# - line_user_id：LINE 平台的使用者 ID
# - preferred_lang：使用者偏好的語言（關聯到 Language 模型）
# - created_at：帳號建立時間（資料庫自動設定）
# - state：使用者狀態（normal, blocked 等）
# 關聯：與 Language 模型建立外鍵關聯
# =============================================================================
class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    line_user_id = db.Column(db.String(100), unique=True, nullable=False)
    preferred_lang = db.Column(db.String(10), db.ForeignKey('languages.line_lang_code'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    state = db.Column(db.String(50), default='normal')

# =============================================================================
# 店家模型區塊
# 功能：定義合作店家的資料結構
# 用途：儲存店家的基本資訊、位置、合作等級等
# 欄位：
# - store_id：店家唯一識別碼
# - store_name：店家名稱
# - partner_level：合作等級（0=非合作, 1=合作, 2=VIP）
# - gps_lat/gps_lng：店家 GPS 座標
# - place_id：Google Places ID
# - review_summary：評論摘要
# - top_dish_1-5：熱門菜色
# - main_photo_url：店家招牌照片 URL
# - created_at：店家資料建立時間（資料庫自動設定）
# - latitude/longitude：向後相容的座標欄位
# 關聯：與 Menu 模型建立一對多關聯（一個店家可以有多個菜單）
# =============================================================================
class Store(db.Model):
    __tablename__ = 'stores'
    store_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    store_name = db.Column(db.String(100), nullable=False)
    partner_level = db.Column(db.Integer, nullable=False, default=0)  # 0=非合作, 1=合作, 2=VIP
    gps_lat = db.Column(db.Double)  # 店家緯度
    gps_lng = db.Column(db.Double)  # 店家經度
    place_id = db.Column(db.String(255))  # Google Places ID
    review_summary = db.Column(db.Text)  # 評論摘要
    top_dish_1 = db.Column(db.String(100))  # 熱門菜色1
    top_dish_2 = db.Column(db.String(100))  # 熱門菜色2
    top_dish_3 = db.Column(db.String(100))  # 熱門菜色3
    top_dish_4 = db.Column(db.String(100))  # 熱門菜色4
    top_dish_5 = db.Column(db.String(100))  # 熱門菜色5
    main_photo_url = db.Column(db.String(255))  # 店家招牌照片
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    # 向後相容的欄位（用於向後相容）
    latitude = db.Column(db.Numeric(10,8))  # 店家緯度（向後相容）
    longitude = db.Column(db.Numeric(11,8))  # 店家經度（向後相容）
    menus = db.relationship('Menu', backref='store', lazy=True)

class StoreTranslation(db.Model):
    __tablename__ = 'store_translations'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.store_id'), nullable=False)
    language_code = db.Column(db.String(10), db.ForeignKey('languages.line_lang_code'), nullable=False)
    description = db.Column(db.Text)  # 翻譯後的店家簡介
    translated_summary = db.Column(db.Text)  # 翻譯後的評論摘要

class Menu(db.Model):
    __tablename__ = 'menus'
    menu_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.store_id'), nullable=False)
    template_id = db.Column(db.Integer)  # 暫時移除外鍵引用，因為 menu_templates 表格不存在
    version = db.Column(db.Integer, nullable=False, default=1)
    effective_date = db.Column(db.DateTime, nullable=False, server_default=db.func.current_timestamp())
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    items = db.relationship('MenuItem', backref='menu', lazy=True, cascade="all, delete-orphan")

class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    menu_item_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('menus.menu_id'), nullable=False)
    item_name = db.Column(db.String(100), nullable=False) # 這是中文菜品名
    price_big = db.Column(db.Integer)
    price_small = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    translations = db.relationship('MenuTranslation', backref='menu_item', lazy=True, cascade="all, delete-orphan")

class MenuTranslation(db.Model):
    __tablename__ = 'menu_translations'
    menu_translation_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_items.menu_item_id'), nullable=False)
    lang_code = db.Column(db.String(10), db.ForeignKey('languages.line_lang_code'), nullable=False)
    description = db.Column(db.Text)  # 翻譯後的菜品描述

class Order(db.Model):
    __tablename__ = 'orders'
    order_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.user_id'), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.store_id'), nullable=False)
    order_time = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    total_amount = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")
    voice_files = db.relationship('VoiceFile', backref='order', lazy=True, cascade="all, delete-orphan")

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    order_item_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    order_id = db.Column(db.BigInteger, db.ForeignKey('orders.order_id'), nullable=False)
    menu_item_id = db.Column(db.BigInteger, db.ForeignKey('menu_items.menu_item_id'), nullable=False)
    quantity_small = db.Column(db.Integer, nullable=False, default=0)
    subtotal = db.Column(db.Integer, nullable=False)
    
    # 雙語菜名欄位（已新增到資料庫）
    original_name = db.Column(db.String(100), nullable=True)  # 原始中文菜名（OCR辨識結果）
    translated_name = db.Column(db.String(100), nullable=True)  # 翻譯菜名（使用者語言）
    
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())

class VoiceFile(db.Model):
    __tablename__ = 'voice_files'
    voice_file_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    order_id = db.Column(db.BigInteger, db.ForeignKey('orders.order_id'), nullable=False)
    file_url = db.Column(db.String(500), nullable=False)  # 語音檔案 URL
    file_type = db.Column(db.String(10), default='mp3')  # mp3, wav
    speech_rate = db.Column(db.Float, default=1.0)  # 語速倍率
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())

# =============================================================================
# OCR 處理模型（符合同事的資料庫結構）
# 功能：支援非合作店家的菜單圖片辨識
# =============================================================================

class OCRMenu(db.Model):
    """OCR 菜單主檔（符合同事的資料庫結構）"""
    __tablename__ = 'ocr_menus'
    
    ocr_menu_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.user_id'), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.store_id'), nullable=True)  # 新增 store_id 欄位
    store_name = db.Column(db.String(100))  # 非合作店家名稱
    upload_time = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    
    # 關聯到菜單項目
    items = db.relationship('OCRMenuItem', backref='ocr_menu', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<OCRMenu {self.ocr_menu_id}>'

class OCRMenuItem(db.Model):
    """OCR 菜單品項（符合同事的資料庫結構）"""
    __tablename__ = 'ocr_menu_items'
    
    ocr_menu_item_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    ocr_menu_id = db.Column(db.BigInteger, db.ForeignKey('ocr_menus.ocr_menu_id'), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)  # 品項名稱
    price_big = db.Column(db.Integer)  # 大份量價格
    price_small = db.Column(db.Integer, nullable=False)  # 小份量價格
    translated_desc = db.Column(db.Text)  # 翻譯後介紹
    
    def __repr__(self):
        return f'<OCRMenuItem {self.ocr_menu_item_id}>'

class OCRMenuTranslation(db.Model):
    """OCR 菜單翻譯（儲存翻譯後的 OCR 菜單）"""
    __tablename__ = 'ocr_menu_translations'
    
    ocr_menu_translation_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    ocr_menu_item_id = db.Column(db.BigInteger, db.ForeignKey('ocr_menu_items.ocr_menu_item_id'), nullable=False)
    lang_code = db.Column(db.String(10), db.ForeignKey('languages.line_lang_code'), nullable=False)
    translated_name = db.Column(db.String(100), nullable=False)  # 翻譯後的菜名
    translated_description = db.Column(db.Text)  # 翻譯後的描述
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    
    # 關聯到 OCR 菜單項目
    ocr_menu_item = db.relationship('OCRMenuItem', backref='translations', lazy=True)
    
    def __repr__(self):
        return f'<OCRMenuTranslation {self.ocr_menu_translation_id}>'

# =============================================================================
# 簡化系統模型（非合作店家）
# 功能：支援拍照辨識的簡化訂單系統
# 注意：此系統不再儲存資料庫，改為即時處理
# =============================================================================

# 移除 SimpleOrder 和 SimpleMenuProcessing 模型
# 因為非合作店家改為即時處理，不需要資料庫儲存

class OrderSummary(db.Model):
    """訂單摘要儲存模型"""
    __tablename__ = 'order_summaries'
    
    summary_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    order_id = db.Column(db.BigInteger, db.ForeignKey('orders.order_id', ondelete='CASCADE'), nullable=False)
    ocr_menu_id = db.Column(db.BigInteger, db.ForeignKey('ocr_menus.ocr_menu_id', ondelete='CASCADE'), nullable=True)  # 可為空，因為合作店家可能沒有 OCR 菜單
    chinese_summary = db.Column(db.Text, nullable=False)  # 中文訂單摘要
    user_language_summary = db.Column(db.Text, nullable=False)  # 使用者語言訂單摘要
    user_language = db.Column(db.String(10), nullable=False)  # 使用者語言代碼
    total_amount = db.Column(db.Integer, nullable=False)  # 訂單總金額
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    
    # 關聯到訂單和 OCR 菜單
    order = db.relationship('Order', backref='summaries', lazy=True)
    ocr_menu = db.relationship('OCRMenu', backref='order_summaries', lazy=True)
    
    def __repr__(self):
        return f'<OrderSummary {self.summary_id}>'

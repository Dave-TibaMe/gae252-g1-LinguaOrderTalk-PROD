# 導入 SQLAlchemy 中所有需要的元件
from sqlalchemy import (
    TEXT,             # 對應 SQL 的 TEXT 型別，用於儲存長字串
    BigInteger,       # 對應 SQL 的 BIGINT 型別，用於儲存大整數
    Boolean,          # 對應 SQL 的 BOOLEAN 型別
    Column,           # 用於定義資料表中的一個欄位
    DateTime,         # 對應 SQL 的 DATETIME 或 TIMESTAMP 型別
    Float,            # 對應 SQL 的 FLOAT 型別，用於浮點數
    ForeignKey,       # 用於定義外鍵約束，建立資料表之間的關聯
    Integer,          # 對應 SQL 的 INTEGER 型別
    Numeric,          # 對應 SQL 的 NUMERIC 或 DECIMAL 型別，用於需要精確小數的場景（如經緯度）
    String,           # 對應 SQL 的 VARCHAR 型別，用於儲存可變長度字串
    func,             # 用於呼叫 SQL 函式，例如 `func.now()` 會對應到 `NOW()`
)
# 從 SQLAlchemy 的 MySQL 方言中導入 TINYINT 型別，這是 MySQL 特有的
from sqlalchemy.dialects.mysql import TINYINT
# 導入 SQLAlchemy ORM 的核心元件
# `declarative_base`: 是一個工廠函式，會回傳一個基底類別，我們定義的所有模型都將繼承它
# `relationship`: 用於定義模型之間的關聯
from sqlalchemy.orm import declarative_base, relationship

# 建立一個所有 ORM 模型的基底類別 `Base`。
# SQLAlchemy 的宣告式系統會透過這個基底類別來識別所有與資料庫對應的模型。
Base = declarative_base()


class User(Base):
    # `__tablename__` 指定這個模型對應到資料庫中的資料表名稱
    __tablename__ = "users"

    # 定義欄位
    user_id = Column(BigInteger, primary_key=True) # `primary_key=True` 表示這是主鍵
    line_user_id = Column(String(100), unique=True, nullable=False) # `unique=True` 表示此欄位值唯一；`nullable=False` 表示不可為空
    state = Column(String(50), nullable=True, default="normal") # `default` 設定欄位的預設值
    # `ForeignKey("languages.line_lang_code")` 建立一個外鍵，關聯到 `languages` 資料表的 `line_lang_code` 欄位
    preferred_lang = Column(
        String(10), ForeignKey("languages.line_lang_code"), nullable=False, default="en"
    )
    # `server_default=func.now()` 表示讓資料庫在新增資料時，自動使用其 `NOW()` 函式填入目前時間
    created_at = Column(DateTime, nullable=True, server_default=func.now())

    # 定義關聯
    # `relationship("Language")` 建立一個物件導向的關聯。
    # 這讓我們可以透過 `user_instance.language` 的方式直接存取到關聯的 Language 物件。
    # SQLAlchemy 會根據上面定義的 ForeignKey 自動找到關聯的條件。
    language = relationship("Language")
    # `relationship("Order", back_populates="user")` 定義一對多關聯（一個 User 可以有多個 Order）。
    # `back_populates="user"` 指明了這個關聯與 Order 模型中的 `user` 關聯是雙向的，
    # 當一邊的關聯更新時，另一邊也會自動同步。
    orders = relationship("Order", back_populates="user")


class Language(Base):
    __tablename__ = "languages"

    line_lang_code = Column(String(10), primary_key=True) # LINE 平台使用的語言代碼，作為主鍵
    translation_lang_code = Column(String(5), nullable=False) # 對應到 Google Translate API 的語言代碼
    stt_lang_code = Column(String(15), nullable=False) # 對應到語音轉文字 (STT) 服務的語言代碼
    lang_name = Column(String(50), nullable=False) # 語言的標準名稱（例如 "繁體中文"）


class Store(Base):
    __tablename__ = "stores"

    # `comment` 參數會在建立資料表時，為該欄位加上註解，有助於資料庫文件化
    store_id = Column(Integer, primary_key=True, comment="店家 ID")
    store_name = Column(String(100), nullable=False, comment="店家名稱")
    partner_level = Column(
        TINYINT, nullable=False, default=0, comment="合作等級: 0=非合作, 1=合作, 2=VIP"
    )
    place_id = Column(String(255), nullable=True, unique=True, comment="Google Map Place ID")

    # GPS 座標，使用 Float (DOUBLE)
    gps_lat = Column(Float, nullable=True, comment="店家 GPS 緯度 (DOUBLE)")
    gps_lng = Column(Float, nullable=True, comment="店家 GPS 經度 (DOUBLE)")
    # GPS 座標，使用 Numeric (DECIMAL)，提供更高的精確度
    latitude = Column(Numeric(10, 8), nullable=True, comment="店家緯度 (DECIMAL)")
    longitude = Column(Numeric(11, 8), nullable=True, comment="店家經度 (DECIMAL)")

    review_summary = Column(TEXT, nullable=True, comment="店家評論摘要")
    # 人氣菜色欄位
    top_dish_1 = Column(String(100), nullable=True, comment="人氣菜色1")
    top_dish_2 = Column(String(100), nullable=True, comment="人氣菜色2")
    top_dish_3 = Column(String(100), nullable=True, comment="人氣菜色3")
    top_dish_4 = Column(String(100), nullable=True, comment="人氣菜色4")
    top_dish_5 = Column(String(100), nullable=True, comment="人氣菜色5")

    main_photo_url = Column(TEXT, nullable=True, comment="店家招牌照片 URL")
    created_at = Column(DateTime, nullable=True, server_default=func.now(), comment="建立時間")

    # 定義與 Order 和 StoreTranslation 的一對多關聯
    orders = relationship("Order", back_populates="store")
    translations = relationship("StoreTranslation", back_populates="store")


class StoreTranslation(Base):
    # 這張表用於儲存店家的多國語言翻譯內容，是實現國際化的關鍵
    __tablename__ = "store_translations"

    id = Column(Integer, primary_key=True)
    store_id = Column(Integer, ForeignKey("stores.store_id"), nullable=False) # 外鍵，關聯到店家
    language_code = Column(
        String(10), ForeignKey("languages.line_lang_code"), nullable=False
    ) # 外鍵，關聯到語言
    description = Column(TEXT, nullable=True) # 店家描述的翻譯
    translated_summary = Column(TEXT, nullable=True) # 店家摘要的翻譯

    # 定義與 Store 和 Language 的多對一關聯
    store = relationship("Store", back_populates="translations")
    language = relationship("Language")


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False) # 外鍵，關聯到使用者
    store_id = Column(Integer, ForeignKey("stores.store_id"), nullable=False) # 外鍵，關聯到店家
    order_time = Column(DateTime, nullable=True, server_default=func.now())
    total_amount = Column(Integer, nullable=False, default=0)
    status = Column(String(20), default="pending") # 訂單狀態

    # 定義多對一關聯
    user = relationship("User", back_populates="orders")
    store = relationship("Store", back_populates="orders")
    # 定義一對多關聯 (一張訂單可以有多個訂單品項)
    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    # 這張表代表訂單中的每一個品項
    __tablename__ = "order_items"

    order_item_id = Column(BigInteger, primary_key=True)
    order_id = Column(BigInteger, ForeignKey("orders.order_id"), nullable=False) # 外鍵，關聯到訂單
    # 外鍵，關聯到菜單品項，`nullable=True` 表示這個品項可能是一個臨時性、不在正式菜單上的品項
    menu_item_id = Column(BigInteger, ForeignKey("menu_items.menu_item_id"), nullable=True)
    quantity_small = Column(Integer, nullable=False, default=0) # 數量
    subtotal = Column(Integer, nullable=False) # 小計金額
    original_name = Column(String(100), nullable=True) # 品項的原始名稱
    translated_name = Column(String(100), nullable=True) # 品項的翻譯後名稱

    # 處理不在正式菜單上的臨時品項的相關欄位
    is_temp_item = Column(Boolean, nullable=True, server_default="0")
    temp_item_id = Column(String(100), nullable=True)
    temp_item_name = Column(String(100), nullable=True)
    temp_item_price = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=True, server_default=func.now())

    # 定義與 Order 和 MenuItem 的多對一關聯
    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem", back_populates="order_items")


class MenuItem(Base):
    # 這張表代表店家的正式菜單品項
    __tablename__ = "menu_items"

    menu_item_id = Column(BigInteger, primary_key=True)

    # 定義與 OrderItem 的一對多關聯 (一個菜單品項可以出現在多個訂單品項中)
    order_items = relationship("OrderItem", back_populates="menu_item")
from datetime import datetime
from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Float,
    Numeric,
    TEXT,
    Boolean,
    func
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.mysql import TINYINT

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    user_id = Column(BigInteger, primary_key=True)
    line_user_id = Column(String(100), unique=True, nullable=False)
    state = Column(String(50), nullable=True, default='normal')
    preferred_lang = Column(String(10), ForeignKey('languages.line_lang_code'), nullable=False, default='en')
    created_at = Column(DateTime, nullable=True, server_default=func.now())

    language = relationship('Language')
    orders = relationship('Order', back_populates='user')

class Language(Base):
    __tablename__ = 'languages'
    
    line_lang_code = Column(String(10), primary_key=True)
    translation_lang_code = Column(String(5), nullable=False)
    stt_lang_code = Column(String(15), nullable=False)
    lang_name = Column(String(50), nullable=False)

class Store(Base):
    """ 
    店家模型 (修正後，與資料庫結構完全一致)
    """
    __tablename__ = 'stores'

    store_id = Column(Integer, primary_key=True, comment="店家 ID")
    store_name = Column(String(100), nullable=False, comment="店家名稱")
    partner_level = Column(TINYINT, nullable=False, default=0, comment="合作等級: 0=非合作, 1=合作, 2=VIP")
    gps_lat = Column(Float, nullable=True, comment="店家 GPS 緯度 (DOUBLE)")
    gps_lng = Column(Float, nullable=True, comment="店家 GPS 經度 (DOUBLE)")
    latitude = Column(Numeric(10, 8), nullable=True, comment="店家緯度 (DECIMAL)")
    longitude = Column(Numeric(11, 8), nullable=True, comment="店家經度 (DECIMAL)")
    place_id = Column(String(255), nullable=True, unique=True, comment="Google Map Place ID")
    review_summary = Column(TEXT, nullable=True, comment="店家評論摘要")
    top_dish_1 = Column(String(100), nullable=True, comment="人氣菜色1")
    top_dish_2 = Column(String(100), nullable=True, comment="人氣菜色2")
    top_dish_3 = Column(String(100), nullable=True, comment="人氣菜色3")
    top_dish_4 = Column(String(100), nullable=True, comment="人氣菜色4")
    top_dish_5 = Column(String(100), nullable=True, comment="人氣菜色5")
    main_photo_url = Column(TEXT, nullable=True, comment="店家招牌照片 URL")
    created_at = Column(DateTime, nullable=True, server_default=func.now(), comment="建立時間")

    orders = relationship('Order', back_populates='store')

    def __repr__(self):
        return f'<Store {self.store_name}>'
    
class Order(Base):
    """ 訂單主檔 """
    __tablename__ = 'orders'
    order_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)
    store_id = Column(Integer, ForeignKey('stores.store_id'), nullable=False)
    order_time = Column(DateTime, nullable=True, server_default=func.now())
    total_amount = Column(Integer, nullable=False, default=0)
    status = Column(String(20), default='pending')

    user = relationship('User', back_populates='orders')
    store = relationship('Store', back_populates='orders')
    items = relationship('OrderItem', back_populates='order')

class OrderItem(Base):
    """ 訂單品項 """
    __tablename__ = 'order_items'
    order_item_id = Column(BigInteger, primary_key=True)
    order_id = Column(BigInteger, ForeignKey('orders.order_id'), nullable=False)
    menu_item_id = Column(BigInteger, ForeignKey('menu_items.menu_item_id'), nullable=True)
    quantity_small = Column(Integer, nullable=False, default=0)
    subtotal = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=True, server_default=func.now())
    original_name = Column(String(100), nullable=True)
    translated_name = Column(String(100), nullable=True)
    temp_item_id = Column(String(100), nullable=True)
    temp_item_name = Column(String(100), nullable=True)
    temp_item_price = Column(Integer, nullable=True)
    is_temp_item = Column(Boolean, nullable=True, server_default='0')

    order = relationship('Order', back_populates='items')
    menu_item = relationship('MenuItem', back_populates='order_items')

class MenuItem(Base):
    """ 菜單品項 (最小化定義) """
    __tablename__ = 'menu_items'

    menu_item_id = Column(BigInteger, primary_key=True)

    # 為了讓 back_populates 正常運作，也定義好反向關聯
    order_items = relationship('OrderItem', back_populates='menu_item')
from datetime import datetime
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    DateTime,
    ForeignKey,
    Integer,
    Float
)
from sqlalchemy.orm import relationship

# --- 關鍵改動 ---
# 從我們建立的 database.py 檔案中匯入 Base
# 這讓所有模型都共用同一個資料庫設定
from .database import Base


class User(Base):
    __tablename__ = 'users'

    user_id = Column(BigInteger, primary_key=True)
    line_user_id = Column(String(100), unique=True, nullable=False)
    state = Column(String(50), nullable=True, default='normal')
    preferred_lang = Column(String(10), ForeignKey('languages.lang_code'), nullable=False, default='en')
    created_at = Column(DateTime, default=datetime.now)

    # 建立與 Language 模型的關聯
    language = relationship('Language')


class Language(Base):
    __tablename__ = 'languages'

    lang_code = Column(String(10), primary_key=True)
    lang_name = Column(String(50), nullable=False)


class Store(Base):
    __tablename__ = 'stores'

    store_id = Column(BigInteger, primary_key=True)
    store_name = Column(String(100), nullable=False)
    partner_level = Column(Integer, nullable=False, default=0) # 0:非合作, 1:合作, 2:VIP
    gps_lat = Column(Float, nullable=True)
    gps_lng = Column(Float, nullable=True)
    place_id = Column(String(100), nullable=True, unique=True)
    main_photo_url = Column(String(255), nullable=True)

    def __repr__(self):
        return f'<Store {self.store_name}>'
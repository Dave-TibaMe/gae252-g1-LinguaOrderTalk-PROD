# 從 sqlalchemy.ext.asyncio 模組導入 `async_sessionmaker` 和 `create_async_engine`。
# 這兩者是使用 SQLAlchemy 進行非同步資料庫操作的核心元件。
# `create_async_engine`: 用於建立一個能與資料庫進行非同步溝通的引擎。
# `async_sessionmaker`: 一個工廠函式，用於配置和建立非同步的 Session 物件。
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# 從同層級的 config 模組（`config.py`）中導入 `Config` 類別。
# 這個 `Config` 類別集中管理了應用程式的所有設定值，例如資料庫連線 URL。
from .config import Config

# 使用 `create_async_engine` 函式建立一個全域的非同步資料庫引擎實例。
# 這個引擎是 SQLAlchemy 與資料庫溝通的起點。
engine = create_async_engine(
    Config.DATABASE_URL,  # 參數1: 從設定檔 `Config` 中讀取資料庫連線字串。
    echo=False,           # `echo=False`: 設定為 False 表示不要在主控台印出 SQLAlchemy 產生的所有 SQL 語句，通常在正式環境中會關閉以保持日誌乾淨。
    pool_recycle=3600     # `pool_recycle=3600`: 設定連線池回收連線的秒數。這裡設定為 3600 秒（1小時），可以防止資料庫因閒置過久而自動斷線的問題，增強程式的穩定性。
)

# 建立一個非同步會話（Session）的工廠 `AsyncSessionLocal`。
# 在應用程式中，我們會透過呼叫 `AsyncSessionLocal()` 來取得一個新的 `AsyncSession` 實例，以便與資料庫進行交易（Transaction）。
AsyncSessionLocal = async_sessionmaker(
    bind=engine,              # `bind=engine`: 將這個會話工廠綁定到先前建立的 `engine`。這意味著從這個工廠建立的所有會話都將使用此引擎來與資料庫溝通。
    expire_on_commit=False,   # `expire_on_commit=False`: 設定為 False 可以防止在交易提交（commit）後，Session 中的 ORM 物件實例過期。
                              # 在 FastAPI 的非同步環境中，這是一個很重要的設定，它允許你在資料庫交易結束後，仍然可以存取 ORM 物件的屬性，而不需要重新查詢資料庫。
)
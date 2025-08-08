from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# 從 config 模組匯入設定
from app.config import Config

# 檢查 DATABASE_URL 是否成功載入，若否，則直接中斷程式並給出明確提示
if Config.DATABASE_URL is None:
    raise ValueError("環境變數 'DATABASE_URL' 未設定，請檢查您的 .env 檔案。")

# 1. 建立非同步引擎
engine = create_async_engine(
    Config.DATABASE_URL,
    echo=False, # 在正式環境建議設為 False
)

# 2. 建立非同步 Session 的工廠
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)

# 3. 建立給 ORM 模型繼承用的基礎類別
Base = declarative_base()

# 4. 建立 FastAPI 依賴項 (Dependency)
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
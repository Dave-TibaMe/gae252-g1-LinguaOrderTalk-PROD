from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import Config

# 1. 建立非同步引擎
engine = create_async_engine(
    Config.DATABASE_URL,
    echo=False
)

# 2. 建立非同步 Session 的工廠
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)

# 3. 建立 FastAPI 依賴項 (Dependency)
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
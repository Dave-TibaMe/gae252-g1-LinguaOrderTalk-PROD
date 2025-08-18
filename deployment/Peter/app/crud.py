# 從 `typing` 模組導入型別提示，用於增強程式碼的可讀性和健壯性。
# `List`: 用於表示列表型別。
# `Optional`: 表示一個值可以是某個指定型別，也可以是 `None`。
# `Sequence`: 表示一個通用的序列型別（如 list 或 tuple），常用於函式的返回型別。
from typing import List, Optional, Sequence

# 從 `sqlalchemy` 模組導入 `desc` 和 `select`。
# `desc`: 用於指定查詢結果以降序 (descending) 排序。
# `select`: 在 SQLAlchemy 2.0 風格中，用於建立 SELECT 查詢語句的核心函式。
from sqlalchemy import desc, select
# 從 SQLAlchemy 的 asyncio 擴充套件導入 `AsyncSession`，這是執行非同步資料庫操作的會話物件型別。
from sqlalchemy.ext.asyncio import AsyncSession
# 從 SQLAlchemy 的 ORM 模組導入 `joinedload`。
# `joinedload` 是一種查詢選項，用於「預先載入」(Eager Loading) 關聯的物件。
# 它可以透過一個 JOIN 查詢一次性取得主物件和其關聯物件，從而有效避免 "N+1 查詢問題"，提升效能。
from sqlalchemy.orm import joinedload

# 從同層級的 `models` 模組中導入所有 ORM 模型類別。
from .models import Language, Order, Store, StoreTranslation, User


async def get_user_by_line_id(
    db: AsyncSession, line_user_id: str
) -> Optional[User]:
    """
    根據 LINE User ID 查詢使用者資料。
    """
    # 建立一個查詢語句，選擇 User 物件。
    stmt = (
        select(User)
        # 使用 .options(joinedload(...)) 來預先載入與 User 相關的 Language 物件。
        # 這樣在後續存取 `user.language` 時，就不需要再發起一次新的資料庫查詢。
        .options(joinedload(User.language))
        # 加入 WHERE 條件，篩選出 `line_user_id` 符合指定值的記錄。
        .filter_by(line_user_id=line_user_id)
    )
    # 非同步地執行查詢語句。
    result = await db.execute(stmt)
    # `scalar_one_or_none()`: 處理查詢結果。它預期最多只會有一筆結果。
    # 如果找到一筆，就返回該筆結果的第一個欄位（在這裡就是 User 物件本身）。
    # 如果沒有找到結果，就返回 `None`。
    # 如果找到多筆結果，會拋出錯誤。
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession, line_user_id: str, preferred_lang: str
) -> User:
    """
    建立一位新使用者。
    """
    # 建立一個新的 User ORM 物件實例。
    new_user = User(
        line_user_id=line_user_id, preferred_lang=preferred_lang, state="normal"
    )
    # 將新建立的 User 物件加入到 session 中，此時它處於 "pending" 狀態。
    db.add(new_user)
    # 非同步地提交（commit）當前的交易。這會將 session 中所有變更（如此處的新增使用者）寫入資料庫。
    await db.commit()
    # 提交後，`new_user` 物件的狀態可能不是最新的（例如資料庫自動產生的 `user_id`）。
    # `db.refresh()` 會從資料庫重新載入 `new_user` 物件的資料，使其與資料庫同步。
    await db.refresh(new_user)
    # 返回建立並刷新後的 User 物件。
    return new_user


async def update_user(db: AsyncSession, user: User, **kwargs) -> User:
    """
    更新現有使用者的資料。
    `**kwargs` 允許傳入任意數量的鍵值對來指定要更新的欄位。
    """
    # 遍歷傳入的關鍵字參數（如 `preferred_lang="en"`, `state="menu"`）。
    for key, value in kwargs.items():
        # 使用 `setattr()` 動態地設定 `user` 物件的屬性。
        # 例如，`setattr(user, "preferred_lang", "en")` 等同於 `user.preferred_lang = "en"`。
        setattr(user, key, value)
    # 提交交易，SQLAlchemy 的工作單元 (Unit of Work) 機制會自動偵測到 `user` 物件的變更，並產生對應的 UPDATE 語句。
    await db.commit()
    # 重新整理物件狀態。
    await db.refresh(user)
    # 返回更新後的 User 物件。
    return user


async def get_stores_by_place_ids(
    db: AsyncSession, place_ids: List[str]
) -> Sequence[Store]:
    """
    根據 Google Place ID 列表，查詢對應的店家資料。
    """
    # 建立查詢語句，選擇 Store 物件。
    # `.where(Store.place_id.in_(place_ids))` 加入 WHERE 條件，使用 `IN` 子句來一次性查詢所有 `place_id` 在列表中的店家。
    # 這比迴圈中逐一查詢要高效得多。
    stmt = select(Store).where(Store.place_id.in_(place_ids))
    # 執行查詢。
    result = await db.execute(stmt)
    # `scalars()` 會從結果中提取每一行的第一個元素（即 Store 物件）。
    # `.all()` 將所有結果收集到一個列表中並返回。
    return result.scalars().all()


async def add_stores(db: AsyncSession, new_stores: List[Store]):
    """
    將一批新的店家資料新增到資料庫。
    """
    # `db.add_all()` 是一個優化後的方法，可以一次性將一個列表中的所有 ORM 物件加入到 session 中。
    db.add_all(new_stores)
    # 提交交易，將所有新店家一次性寫入資料庫。
    await db.commit()


async def get_store_translation_summary(
    db: AsyncSession, store_id: int, lang_code: str
) -> Optional[str]:
    """
    根據店家 ID 和語言代碼，查詢店家的翻譯摘要。
    """
    # 建立查詢語句，但這次只選擇 `StoreTranslation.translated_summary` 這一個欄位，而不是整個物件。
    # 當只需要特定欄位時，這樣做更有效率。
    stmt = select(StoreTranslation.translated_summary).where(
        StoreTranslation.store_id == store_id,
        StoreTranslation.language_code == lang_code,
    )
    # 執行查詢。
    result = await db.execute(stmt)
    # 返回查詢到的單一純量值（即摘要字串），如果找不到則返回 `None`。
    return result.scalar_one_or_none()


async def get_order_details(
    db: AsyncSession, order_id: int, user_id: int
) -> Optional[Order]:
    """
    根據訂單 ID 和使用者 ID，查詢單一訂單的詳細資料。
    """
    # 建立查詢語句，選擇 Order 物件。
    stmt = (
        select(Order)
        # WHERE 條件：確保訂單 ID 和使用者 ID 都匹配，防止使用者查詢到不屬於自己的訂單。
        .where(Order.order_id == order_id, Order.user_id == user_id)
        # 預先載入關聯的 `store` 物件 (一對多關係的 "一") 和 `items` 列表 (一對多關係的 "多")。
        .options(joinedload(Order.store), joinedload(Order.items))
    )
    # 執行查詢。
    result = await db.execute(stmt)
    # `.unique()`: 當使用 `joinedload` 載入一對多關聯（如 `items`）時，查詢結果可能會因為 JOIN 而包含重複的主物件（Order）。
    # `.unique()` 會在 Python 端過濾掉這些重複的物件。
    # `.scalar_one_or_none()`: 返回唯一的 Order 物件，或 `None`。
    return result.unique().scalar_one_or_none()


async def get_user_order_history(
    db: AsyncSession, user_id: int, limit: int = 10
) -> Sequence[Order]:
    """
    查詢指定使用者的歷史訂單，並按時間倒序排列。
    `limit` 參數可以限制返回的訂單數量。
    """
    # 建立查詢語句，選擇 Order 物件。
    stmt = (
        select(Order)
        # 預先載入每筆訂單關聯的店家資訊。
        .options(joinedload(Order.store))
        # WHERE 條件：篩選出屬於該使用者的訂單。
        .where(Order.user_id == user_id)
        # 排序條件：根據訂單時間 (`order_time`) 進行倒序 (`desc`) 排列，讓最新的訂單在最前面。
        .order_by(desc(Order.order_time))
        # 限制返回的結果數量，對應 SQL 中的 `LIMIT` 子句。
        .limit(limit)
    )
    # 執行查詢。
    result = await db.execute(stmt)
    # 返回訂單物件列表。
    return result.scalars().all()


async def get_all_languages(db: AsyncSession) -> Sequence[Language]:
    """
    從資料庫中取得所有支援的語言設定。
    """
    # 建立一個簡單的查詢，選擇所有 Language 物件。
    result = await db.execute(select(Language))
    # 返回所有語言物件的列表。
    return result.scalars().all()
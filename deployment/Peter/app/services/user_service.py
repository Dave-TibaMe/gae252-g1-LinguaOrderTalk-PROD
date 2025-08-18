# 導入 logging 模組，用於記錄日誌訊息。
import logging
# 導入 typing 模組中的 List 型別，用於型別提示。
from typing import List

# 從 linebot SDK 導入非同步相關的類別。
from linebot.v3.messaging import (
    AsyncApiClient,     # 非同步 API 客戶端
    Configuration,      # LINE SDK 的設定類別
    Message,            # 所有訊息類別的基底類別
    MessagingApi,       # 非同步訊息 API 客戶端
    PushMessageRequest, # 建立推播訊息請求的類別
)
# 從 sqlalchemy.ext.asyncio 導入 AsyncSession，用於型別提示資料庫會話物件。
from sqlalchemy.ext.asyncio import AsyncSession

# 從上層目錄 (app/) 導入 crud 和 line_messages 模組。
from .. import crud, line_messages
# 導入設定檔 Config。
from ..config import Config
# 導入 User 模型，用於型別提示。
from ..models import User

# 取得一個 logger 實例，名稱與當前模組相同。
logger = logging.getLogger(__name__)

# 使用設定檔中的 Access Token 來初始化 LINE SDK 的設定。
line_config = Configuration(access_token=Config.CHANNEL_ACCESS_TOKEN)


async def handle_new_user_follow(
    db: AsyncSession, line_user_id: str, translate_client, lang_code_map: dict
):
    """
    處理使用者加入好友或解除封鎖的事件。
    這個函式會建立或更新使用者資料，並發送一個歡迎訊息及主選單。
    """
    # 預設使用者的語言為英文。
    user_language = "en"
    try:
        # 使用非同步 API 客戶端來執行非同步請求。
        async with AsyncApiClient(line_config) as api_client:
            # 呼叫 LINE Messaging API 的 get_profile 方法，取得使用者的個人資料。
            profile = await MessagingApi(api_client).get_profile(line_user_id)
            # 如果使用者資料中包含語言資訊，則更新 user_language 變數。
            if profile.language:
                user_language = profile.language
    except Exception as e:
        # 如果取得個人資料失敗，記錄錯誤日誌。
        logger.error(f"Failed to get user profile for {line_user_id}: {e}")

    # 使用 crud 函式查詢資料庫，檢查使用者是否已存在。
    user = await crud.get_user_by_line_id(db, line_user_id)

    # 如果使用者不存在...
    if not user:
        # 呼叫 crud 函式建立一個新的使用者。
        user = await crud.create_user(db, line_user_id, user_language)
    else:
        # 如果使用者已存在，則更新其偏好語言和狀態。
        user = await crud.update_user(db, user, preferred_lang=user_language, state="normal")

    # 使用 line_messages 模組中的函式，建立一則包含歡迎文字和主選單的訊息列表。
    welcome_messages = await line_messages.create_main_menu_messages(
        user, translate_client, lang_code_map
    )

    # 再次使用非同步 API 客戶端。
    async with AsyncApiClient(line_config) as api_client:
        # 呼叫 LINE Messaging API 的 push_message 方法，主動將歡迎訊息推播給使用者。
        # PushMessageRequest 用於指定訊息的接收者 (to) 和內容 (messages)。
        await MessagingApi(api_client).push_message(
            PushMessageRequest(to=line_user_id, messages=welcome_messages)
        )


async def handle_unknown_command(
    user: User, translate_client, lang_code_map: dict
) -> List[Message]:
    """
    當使用者發送的訊息不是一個可識別的指令時，回覆主選單。
    """
    # 呼叫 line_messages 模組中的函式來建立主選單訊息，並將其返回。
    return await line_messages.create_main_menu_messages(
        user, translate_client, lang_code_map
    )
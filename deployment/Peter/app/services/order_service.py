# 從 typing 模組導入 List 型別，用於型別提示函式的回傳值為列表。
from typing import List

# 從 linebot SDK 導入 Message 基底類別，用於型別提示函式的回傳值。
from linebot.v3.messaging import Message
# 從 sqlalchemy.ext.asyncio 導入 AsyncSession，用於型別提示資料庫會話物件。
from sqlalchemy.ext.asyncio import AsyncSession

# 從上層目錄 (app/) 導入 crud 和 line_messages 模組。
# `..` 表示上一層目錄，這是 Python 的相對導入語法。
from .. import crud, line_messages
# 同樣從上層目錄導入 User 模型，用於函式參數的型別提示。
from ..models import User


async def handle_order_now_request(
    user: User, translate_client, lang_code_map: dict
) -> List[Message]:
    """
    處理使用者發出的「立即點餐」請求。
    這個函式會建立一則要求使用者分享位置的訊息，以便為其尋找附近的店家。
    """
    # 呼叫 line_messages 模組中的函式，建立一個帶有「分享我的位置」快速回覆按鈕的文字訊息。
    # 接著將此訊息物件放入一個列表中返回。
    return [
        await line_messages.create_ask_location_message(
            user, translate_client, lang_code_map
        )
    ]


async def handle_order_history_request(
    db: AsyncSession, user: User, translate_client, lang_code_map: dict
) -> List[Message]:
    """
    處理使用者發出的「歷史訂單」請求。
    這個函式會從資料庫查詢使用者的歷史訂單，並回傳一個輪播訊息來顯示這些訂單。
    """
    # 1. 查詢資料庫:
    # 呼叫 crud 模組中的 get_user_order_history 函式，以非同步方式查詢指定使用者的歷史訂單。
    orders = await crud.get_user_order_history(db, user.user_id)
    
    # 2. 處理查詢結果並建立回覆訊息:
    # 如果查詢結果為空（即 orders 列表為空）...
    if not orders:
        # 建立一則「沒有歷史訂單」的簡單文字訊息。
        return [
            await line_messages.create_simple_text_message(
                user,
                "no_order_history", # 訊息範本的鍵值
                translate_client=translate_client,
                lang_code_map=lang_code_map,
            )
        ]
    else:
        # 如果找到訂單...
        # 建立一個輪播（Carousel）模板訊息，用於顯示每一筆訂單。
        return [
            await line_messages.create_order_history_carousel(
                orders, user, translate_client, lang_code_map
            )
        ]


async def handle_show_order_details_request(
    db: AsyncSession, user: User, order_id: int, translate_client, lang_code_map: dict
) -> List[Message]:
    """
    處理使用者發出的「顯示訂單詳情」請求。
    這個函式會從資料庫查詢指定訂單的詳細資訊，並以文字訊息的形式回覆給使用者。
    """
    # 1. 查詢資料庫:
    # 呼叫 crud 模組中的 get_order_details 函式，以非同步方式查詢單一訂單的詳細資料。
    # 查詢條件包含 order_id 和 user_id，以確保使用者只能查詢自己的訂單。
    order = await crud.get_order_details(db, order_id, user.user_id)
    
    # 2. 處理查詢結果並建立回覆訊息:
    # 如果成功找到訂單...
    if order:
        # 建立一則包含訂單所有詳細內容的文字訊息。
        return [
            await line_messages.create_order_details_message(
                order, user, translate_client, lang_code_map
            )
        ]
    else:
        # 如果找不到訂單（例如 order_id 無效或不屬於該使用者）...
        # 返回一個通用的錯誤訊息。
        return [
            await line_messages.create_simple_text_message(
                user,
                "generic_error",
                translate_client=translate_client,
                lang_code_map=lang_code_map,
            )
        ]
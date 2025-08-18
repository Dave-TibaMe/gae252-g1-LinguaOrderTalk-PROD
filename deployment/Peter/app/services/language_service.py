# 導入型別提示
from typing import Dict, List

# 從 linebot SDK 導入 Message 基底類別，用於函式的返回型別提示
from linebot.v3.messaging import Message
# 導入 SQLAlchemy 的非同步會話型別提示
from sqlalchemy.ext.asyncio import AsyncSession

# 從上層目錄 (`app/`) 導入 crud 和 line_messages 模組
# `..` 表示上一層目錄，這是 Python 的相對導入語法
from .. import crud, line_messages
# 同樣從上層目錄導入 User 模型，用於型別提示
from ..models import User


async def handle_change_language_request(
    user: User,
    translate_client,
    lang_code_map: dict,
    native_language_list: list,
    language_display_texts: Dict[str, str],
) -> List[Message]:
    """
    處理使用者發出的「變更語言」請求。
    
    這個服務的職責很簡單：就是呼叫 `line_messages` 模組來建立一個語言選擇的 Flex Message。
    它將從主處理流程中接收到的所有必要資源（如翻譯客戶端、語言列表等）直接傳遞下去。
    """
    # 呼叫 `line_messages` 中的函式來建立語言選擇介面，並將其回傳的 Message 物件放入一個列表中返回。
    # 所有複雜的訊息建立邏輯都封裝在 `line_messages` 中，服務層只負責呼叫。
    return [
        await line_messages.create_language_selection_flex_message(
            user=user,
            translate_client=translate_client,
            lang_code_map=lang_code_map,
            native_language_list=native_language_list,
            display_texts_cache=language_display_texts, # 傳入預先翻譯好的顯示文字快取
        )
    ]


async def handle_set_language_request(
    db: AsyncSession,
    user: User,
    lang_code: str,
    translate_client,
    lang_code_map: dict,
    native_language_list: list,
) -> List[Message]:
    """
    處理使用者選擇了某個特定語言之後的請求。
    """
    # 1. 驗證：檢查傳入的 `lang_code` 是否有效（非空且存在於我們支援的語言映射表中）。
    if lang_code and lang_code in lang_code_map:
        # 2. 更新資料庫：如果語言代碼有效，就呼叫 crud 函式來更新使用者在資料庫中的 `preferred_lang` 欄位。
        # 同時也可能將使用者的狀態（state）重設為 "normal"。
        await crud.update_user(db, user, preferred_lang=lang_code, state="normal")

        # 3. 準備回覆訊息：
        # 從完整的語言列表中，找到與使用者選擇的 `lang_code` 對應的語言物件。
        # `next(...)` 是一個迭代器工具，用於找到滿足條件的第一個元素。
        lang_obj = next(
            (item for item in native_language_list if item["lang_code"] == lang_code),
            None, # 如果找不到，預設返回 None
        )
        # 取得該語言的標準名稱（例如 "繁體中文"）。如果找不到物件，則備用為語言代碼本身。
        canonical_lang_name = lang_obj["lang_name"][0] if lang_obj else lang_code

        # 為了讓確認訊息更貼近使用者，將語言的標準名稱（如 "繁體中文"）
        # 翻譯成使用者剛剛選擇的目標語言（如 "Traditional Chinese"）。
        localized_name = await line_messages.localize_lang_name(
            canonical_lang_name, lang_code, translate_client
        )

        # 呼叫 `line_messages` 中的函式來建立一則成功設定的確認訊息。
        return [
            await line_messages.create_simple_text_message(
                user, # 此時 user 物件的 preferred_lang 已經在記憶體中更新，所以這則訊息會以新語言發送
                "language_set_success", # 訊息範本的 key
                lang_name=localized_name, # 傳入要格式化的變數
                translate_client=translate_client,
                lang_code_map=lang_code_map,
            )
        ]
    else:
        # 4. 處理無效輸入：如果傳入的 `lang_code` 無效，則回傳一則通用的錯誤訊息。
        return [
            await line_messages.create_simple_text_message(
                user,
                "generic_error",
                translate_client=translate_client,
                lang_code_map=lang_code_map,
            )
        ]
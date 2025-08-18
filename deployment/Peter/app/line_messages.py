# 導入 asyncio 模組，用於非同步操作，如此處的 `asyncio.to_thread`。
import asyncio
# 導入 json 模組，用於處理 JSON 格式的資料，例如 PostbackAction 的 data 欄位。
import json
# 導入 logging 模組，用於日誌記錄。
import logging
# 從 typing 模組導入型別提示。
from typing import Any, Dict, List
# 從 urllib.parse 導入 quote，用於對 URL 中的特殊字元進行編碼，確保 URL 的正確性。
from urllib.parse import quote

# 從 line-bot-sdk for python v3 中導入所有會用到的訊息類別和動作類別。
# 這些類別對應到 LINE Messaging API 中各種不同的訊息格式。
from linebot.v3.messaging import (
    ButtonsTemplate,      # 按鈕模板
    CarouselColumn,       # 輪播模板中的單一欄位
    CarouselTemplate,     # 輪播模板
    FlexBox,              # Flex Message 中的基本排版元件
    FlexBubble,           # Flex Message 的泡泡容器
    FlexMessage,          # Flex Message 訊息本體
    FlexText,             # Flex Message 中的文字元件
    LocationAction,       # 觸發使用者傳送位置資訊的動作
    Message,              # 所有訊息類別的基底類別，用於型別提示
    PostbackAction,       # 觸發 postback 事件的動作
    QuickReply,           # 快速回覆按鈕的容器
    QuickReplyItem,       # 快速回覆中的單一按鈕
    TemplateMessage,      # 模板訊息
    TextMessage,          # 文字訊息
    URIAction,            # 開啟網頁連結的動作
)

# 從本地模組中導入設定、常數和資料模型。
from .config import Config
from .constants import ActionType
from .models import Order, Store, User

# 取得 logger 實例。
logger = logging.getLogger(__name__)

# 定義一個全域字典，儲存所有回覆訊息的文字範本。
# 基礎語言為繁體中文。Key 是範本的識別碼，Value 是文字內容。
# 使用 `{key}` 的格式來表示可被動態替換的變數。
REPLY_TEMPLATES = {
    "welcome_text_message": "您可以透過下方的按鈕開始使用我們的服務，或隨時輸入文字與我互動。",
    "button_card_prompt": "請選擇服務項目：",
    "button_label_change_language": "更改語言",
    "button_label_order_now": "立即點餐",
    "button_label_order_history": "歷史訂單",
    "flex_language_prompt": "請選擇您想使用的語言：",
    "setting_language_to": "將語言設定為 {lang_name}",
    "language_set_success": "語言已成功設定為: {lang_name}。",
    "user_not_found": "錯誤：找不到您的使用者資料，請嘗試重新加入好友。",
    "ask_location": "請分享您目前的位置，為您尋找附近的店家。",
    "no_stores_found": "對不起，您附近找不到任何店家。",
    "start_ordering": "開始點餐",
    "order_again": "再次訂購",
    "view_order_details": "查看訂單詳情",
    "no_order_history": "您目前沒有任何歷史訂單。",
    "order_details_title": "訂單詳情",
    "order_details_store": "店家",
    "order_details_time": "時間",
    "order_details_total": "總金額",
    "order_details_items_header": "品項",
    "generic_error": "處理您的請求時發生錯誤，請稍後再試。",
    "querying_order_details": "正在查詢 {store_name} 的訂單詳情...",
    "partner_level_0": "非合作店家",
    "partner_level_1": "合作店家",
    "partner_level_2": "VIP店家",
    "view_store_summary": "店家介紹",
    "store_summary_not_found": "對不起，目前沒有提供此店家的介紹。",
    "querying_store_summary": "正在查詢 {store_name} 的介紹...",
    "alt_text_store_list": "附近的店家列表",
    "alt_text_order_history": "您的歷史訂單",
}


async def translate_texts_batch(
    texts: List[str], user: User, translate_client, lang_code_map: Dict[str, Any]
) -> List[str]:
    """
    非同步地批次翻譯一組文字。一次性送出多個翻譯請求可以提升效率並節省成本。
    """
    # 如果翻譯客戶端未初始化（例如 API 金鑰未設定），則直接返回原文。
    if not translate_client:
        logger.warning("Translate client not available. Skipping translation.")
        return texts

    # 如果使用者不存在，或使用者的偏好語言是預設的繁體中文，則無需翻譯，直接返回原文。
    if not user or not user.preferred_lang or user.preferred_lang == "zh-Hant":
        return texts

    # 從語言映射表中找到 LINE 語言代碼對應的 Google Translate 語言代碼。
    lang_map = lang_code_map.get(user.preferred_lang)
    target_lang = lang_map.get("translation") if lang_map else user.preferred_lang

    # 如果目標語言是 "zh-TW" (Google Translate 的繁中代碼) 或沒有任何文字需要翻譯，則直接返回。
    if target_lang == "zh-TW" or not texts:
        return texts

    # 使用 try...except 處理可能的翻譯 API 錯誤。
    try:
        # `translate_client.translate` 是同步函式庫，使用 `asyncio.to_thread` 將其放入獨立的執行緒中執行，
        # 避免阻塞 asyncio 的事件循環 (event loop)。
        results = await asyncio.to_thread(
            translate_client.translate,
            texts, # 要翻譯的文字列表
            target_language=target_lang, # 目標語言
            source_language="zh-TW", # 來源語言
        )
        # 從翻譯結果中提取翻譯後的文字，並組合成一個新的列表返回。
        return [result["translatedText"] for result in results]
    except Exception as e:
        # 如果翻譯失敗，記錄錯誤並返回原始文字，確保程式不會因此中斷。
        logger.error(
            f"Batch translation to {target_lang} for texts '{texts}' failed: {e}"
        )
        return texts


async def get_translated_text(
    user: User,
    template_key: str,
    *,
    translate_client,
    lang_code_map: Dict[str, Any],
    **kwargs,
) -> str:
    """
    根據使用者的偏好語言，取得單一範本的翻譯文字。
    `**kwargs` 用於格式化文字中的動態變數。
    """
    # 從 `REPLY_TEMPLATES` 字典中安全地取得範本文字。如果 key 不存在，返回一個錯誤提示。
    default_text = REPLY_TEMPLATES.get(template_key, f"Template_Error: {template_key}")

    # 如果翻譯客戶端不可用，直接格式化並返回預設語言的文字。
    if not translate_client:
        logger.warning("Translate client not available. Skipping translation.")
        return default_text.format(**kwargs)

    # 如果使用者是預設語言，也直接格式化並返回。
    if not user or not user.preferred_lang or user.preferred_lang == "zh-Hant":
        return default_text.format(**kwargs)

    # 找出目標翻譯語言代碼。
    lang_map = lang_code_map.get(user.preferred_lang)
    target_lang = lang_map.get("translation") if lang_map else user.preferred_lang

    # 如果目標語言是繁體中文，直接返回。
    if target_lang == "zh-TW":
        return default_text.format(**kwargs)

    # 處理可能的 API 錯誤。
    try:
        # 使用 `asyncio.to_thread` 執行同步的翻譯請求。
        result = await asyncio.to_thread(
            translate_client.translate,
            default_text,
            target_language=target_lang,
            source_language="zh-TW",
        )
        # 返回翻譯後並格式化過的文字。
        return result["translatedText"].format(**kwargs)
    except Exception as e:
        # 如果翻譯失敗，記錄錯誤並返回預設語言的文字。
        logger.error(
            f"Translation to {target_lang} for key '{template_key}' failed: {e}"
        )
        return default_text.format(**kwargs)


async def get_translated_text_for_target_lang(
    template_key: str,
    target_line_lang_code: str,
    translate_client,
    lang_code_map: Dict[str, Any],
    **kwargs,
) -> str:
    """
    將指定的範本文字翻譯成指定的目標語言（而不是目前使用者的語言）。
    這個函式主要用於應用程式啟動時，預先快取各種語言的顯示文字。
    """
    # 取得預設的範本文字。
    default_text = REPLY_TEMPLATES.get(template_key, f"Template_Error: {template_key}")

    # 如果翻譯功能不可用或目標語言是預設語言，直接返回。
    if not translate_client or target_line_lang_code == "zh-Hant":
        return default_text.format(**kwargs)

    # 找出目標翻譯語言代碼。
    lang_map = lang_code_map.get(target_line_lang_code)
    target_translation_lang = (
        lang_map.get("translation") if lang_map else target_line_lang_code
    )

    # 如果目標翻譯語言是繁體中文，直接返回。
    if target_translation_lang == "zh-TW":
        return default_text.format(**kwargs)

    # 處理 API 錯誤。
    try:
        # 執行翻譯。
        result = await asyncio.to_thread(
            translate_client.translate,
            default_text,
            target_language=target_translation_lang,
            source_language="zh-TW",
        )
        # 返回翻譯後並格式化過的文字。
        return result["translatedText"].format(**kwargs)
    except Exception as e:
        logger.error(
            f"Translation to {target_translation_lang} for key '{template_key}' failed: {e}"
        )
        return default_text.format(**kwargs)


async def localize_lang_name(
    canonical_name: str, target_lang: str, translate_client
) -> str:
    """
    將一個標準的語言名稱（如 "繁體中文"）翻譯成目標語言本身（如翻譯成英文變成 "Traditional Chinese"）。
    """
    # 如果目標語言不是預設語言，才進行翻譯。
    if target_lang != "zh-Hant":
        try:
            # 執行翻譯。
            result = await asyncio.to_thread(
                translate_client.translate,
                canonical_name,
                target_language=target_lang,
                source_language="zh-TW",
            )
            return result["translatedText"]
        except Exception as e:
            # 翻譯失敗則記錄錯誤並返回原文。
            logger.error(
                f"Failed to localize lang_name '{canonical_name}' to {target_lang}: {e}"
            )
    # 如果是預設語言或翻譯失敗，返回原文。
    return canonical_name


async def create_language_selection_flex_message(
    user: User,
    translate_client,
    lang_code_map: Dict[str, Any],
    native_language_list: List[Dict[str, Any]],
    display_texts_cache: Dict[str, str],
) -> FlexMessage:
    """
    建立一個讓使用者選擇語言的 Flex Message。
    Flex Message 是一種可以高度自訂排版的訊息格式。
    """
    # 取得翻譯後的提示文字。
    prompt_text = await get_translated_text(
        user,
        "flex_language_prompt",
        translate_client=translate_client,
        lang_code_map=lang_code_map,
    )

    # `body_contents` 用於存放所有語言按鈕的排版元件。
    body_contents = []
    buttons_per_row = 2 # 設定每行顯示兩個語言按鈕。
    # 將語言列表切割成多個子列表，每個子列表代表一行。
    language_chunks = [
        native_language_list[i : i + buttons_per_row]
        for i in range(0, len(native_language_list), buttons_per_row)
    ]

    # 遍歷每一行的語言資料。
    for chunk in language_chunks:
        row_components = [] # 存放單行內的所有按鈕元件。
        # 遍歷單行內的每個語言項目。
        for lang_item in chunk:
            lang_name = lang_item["lang_name"][0] # 語言名稱，例如 "English"
            lang_code = lang_item["lang_code"] # 語言代碼，例如 "en"

            # 從預先快取的字典中取得按下按鈕後會顯示的文字。
            # 這樣可以避免在每次生成此訊息時都重新翻譯。
            display_text = display_texts_cache.get(
                lang_code, f"Set language to {lang_item['lang_name'][0]}"
            )

            # 建立 Flex Message 中的文字元件。
            button_text = FlexText(
                text=lang_name, wrap=True, align="center", size="sm", color="#007BFF"
            )

            # 準備 PostbackAction 的資料，當使用者點擊按鈕時，LINE 平台會將這些資料傳回我們的 webhook。
            postback_data = {"action": ActionType.SET_LANGUAGE, "lang_code": lang_code}
            # 建立一個 FlexBox 作為按鈕的容器。
            custom_button = FlexBox(
                layout="vertical",
                # `action` 決定了這個元件的可點擊行為。
                action=PostbackAction(
                    label=lang_name, # 按鈕標籤（在無法顯示 Flex Message 的裝置上作為替代文字）
                    data=json.dumps(postback_data), # 傳回的資料，必須是字串
                    displayText=display_text, # 使用者點擊後，在聊天室中顯示的文字
                ),
                flex=1, # 佔滿可用空間
                padding_all="md",
                contents=[button_text], # 將文字元件放入按鈕容器中
            )
            row_components.append(custom_button)

        # 如果一行不滿 `buttons_per_row` 個按鈕，用空的 FlexBox 佔位，以維持排版整齊。
        while len(row_components) < buttons_per_row:
            row_components.append(FlexBox(layout="vertical", flex=1, contents=[]))

        # 將單行的所有按鈕元件放入一個水平排列的 FlexBox 中。
        row_box = FlexBox(
            layout="horizontal", contents=row_components, spacing="md", margin="md"
        )
        body_contents.append(row_box)

    # 建立 Flex Message 的主要結構，稱為 "bubble"。
    bubble = FlexBubble(
        size="kilo", # 泡泡的大小
        # 泡泡的頂部區塊 (header)。
        header=FlexBox(
            layout="vertical",
            backgroundColor="#E6F0FF",
            contents=[FlexText(text=prompt_text, weight="regular", size="md", wrap=True)],
        ),
        # 泡泡的主體區塊 (body)，包含所有語言按鈕。
        body=FlexBox(layout="vertical", contents=body_contents, spacing="sm"),
    )

    # 最後，將 bubble 包裝成一個 `FlexMessage` 物件並返回。
    # `alt_text` 是在聊天列表或推播通知中顯示的替代文字。
    return FlexMessage(alt_text=prompt_text, contents=bubble)


def create_liff_url(user: User, store: Store) -> str:
    """
    建立並返回一個 LIFF (LINE Front-end Framework) 應用程式的 URL。
    LIFF URL 允許在 LINE 內部開啟一個網頁視窗。
    """
    # 對店家名稱進行 URL 編碼，以處理名稱中可能包含的特殊字元。
    encoded_store_name = quote(store.store_name)
    # 判斷店家是否為合作夥伴。
    is_partner = "true" if store.partner_level > 0 else "false"
    # 取得使用者的偏好語言。
    user_lang = user.preferred_lang if user else "en"
    # 組合 LIFF URL，並將店家 ID、名稱、合作狀態和語言等資訊作為查詢參數 (query parameters) 傳遞給 LIFF 網頁。
    return f"line://app/{Config.LIFF_ID}?store_id={store.store_id}&store_name={encoded_store_name}&is_partner={is_partner}&lang={user_lang}"


async def create_main_menu_messages(
    user: User, translate_client, lang_code_map: Dict[str, Any]
) -> List[Message]:
    """
    建立歡迎訊息和主選單。這通常由一則文字訊息和一則按鈕模板訊息組成。
    """
    # 定義所有需要翻譯的文字範本 key。
    template_keys = [
        "welcome_text_message",
        "button_card_prompt",
        "button_label_order_now",
        "button_label_order_history",
        "button_label_change_language",
    ]
    # 取得這些 key 對應的預設文字。
    default_texts = [REPLY_TEMPLATES[key] for key in template_keys]

    # 使用批次翻譯函式一次性翻譯所有文字。
    translated_texts = await translate_texts_batch(
        default_texts, user, translate_client, lang_code_map
    )

    # 將翻譯後的文字解包到各個變數中。
    welcome_text, prompt_text, order_now_label, history_label, change_lang_label = (
        translated_texts
    )

    # 建立第一則訊息：純文字的歡迎訊息。
    text_message = TextMessage(text=welcome_text)
    # 建立第二則訊息：帶有按鈕的模板訊息。
    buttons_template = ButtonsTemplate(
        text=prompt_text, # 模板中的提示文字
        actions=[
            # 按鈕1: "立即點餐"。這是一個 `LocationAction`，點擊後會提示使用者分享目前位置。
            LocationAction(label=order_now_label),
            # 按鈕2: "歷史訂單"。這是一個 `PostbackAction`，點擊後會觸發一個 postback 事件。
            PostbackAction(
                label=history_label, data=json.dumps({"action": ActionType.ORDER_HISTORY})
            ),
            # 按鈕3: "更改語言"。
            PostbackAction(
                label=change_lang_label,
                data=json.dumps({"action": ActionType.CHANGE_LANGUAGE}),
            ),
        ],
    )
    # 將按鈕模板包裝成一個 `TemplateMessage` 物件。
    template_message = TemplateMessage(alt_text=prompt_text, template=buttons_template)
    # 返回包含這兩則訊息的列表。LINE 會依序傳送它們。
    return [text_message, template_message]


async def create_ask_location_message(
    user: User, translate_client, lang_code_map: Dict[str, Any]
) -> TextMessage:
    """
    建立一則請求使用者分享位置的文字訊息，並附帶一個快速回覆按鈕。
    """
    # 取得翻譯後的提示文字 "請分享您目前的位置..."。
    ask_location_text = await get_translated_text(
        user,
        "ask_location",
        translate_client=translate_client,
        lang_code_map=lang_code_map,
    )
    # 建立文字訊息。
    return TextMessage(
        text=ask_location_text,
        # 附加 `QuickReply` (快速回覆)。快速回覆按鈕會顯示在輸入框上方。
        quick_reply=QuickReply(
            items=[
                # 快速回覆項目只有一個按鈕。
                QuickReplyItem(
                    # 這個按鈕的動作是 `LocationAction`，功能與模板訊息中的同類按鈕相同。
                    action=LocationAction(label="分享我的位置")
                )
            ]
        ),
    )


async def create_store_carousel_message(
    stores: List[Store], user: User, translate_client, lang_code_map: Dict[str, Any]
) -> TemplateMessage:
    """
    根據店家列表，建立一個店家輪播訊息 (Carousel Message)。
    輪播訊息可以讓使用者水平滑動瀏覽多個項目。
    """
    # --- 批次翻譯 ---
    # 為了最佳化，將所有需要翻譯的文字一次收集起來。
    
    # 1. 靜態文字：不論有幾個店家，這些文字都是固定的。
    static_template_keys = [
        "start_ordering",
        "view_store_summary",
        "partner_level_0",
        "partner_level_1",
        "partner_level_2",
    ]
    static_default_texts = [REPLY_TEMPLATES[key] for key in static_template_keys]

    # 2. 動態文字：每個店家都有自己的名稱和點擊按鈕時的顯示文字。
    dynamic_default_texts = []
    for store in stores:
        dynamic_default_texts.append(store.store_name)
        dynamic_default_texts.append(
            REPLY_TEMPLATES["querying_store_summary"].format(store_name=store.store_name)
        )

    # 將靜態和動態文字合併成一個大列表，並一次性送去翻譯。
    all_default_texts = static_default_texts + dynamic_default_texts
    all_translated_texts = await translate_texts_batch(
        all_default_texts, user, translate_client, lang_code_map
    )

    # --- 處理翻譯結果 ---
    num_static = len(static_default_texts)
    translated_static = all_translated_texts[:num_static] # 分離出翻譯後的靜態文字
    translated_dynamic = all_translated_texts[num_static:] # 分離出翻譯後的動態文字

    start_ordering_label, view_summary_label, partner_level_0, partner_level_1, partner_level_2 = (
        translated_static
    )
    # 建立一個合作等級文字的映射字典，方便後續使用。
    partner_level_map = {0: partner_level_0, 1: partner_level_1, 2: partner_level_2}

    # --- 建立輪播卡片 ---
    carousel_columns = []
    # 遍歷每一個店家，為其建立一個 `CarouselColumn` (輪播卡片)。
    for i, store in enumerate(stores):
        # 從翻譯結果中取得對應該店家的名稱和按鈕顯示文字。
        translated_store_name = translated_dynamic[i * 2]
        translated_display_text = translated_dynamic[i * 2 + 1]

        # 產生點餐用的 LIFF URL。
        liff_full_url = create_liff_url(user, store)
        # 設定卡片的預設圖片。
        card_photo_url = "https://via.placeholder.com/1024x1024.png?text=No+Image"
        # 如果店家資料中有主照片 URL...
        if store.main_photo_url:
            # 如果 URL 是相對路徑 (以 "/" 開頭)...
            if store.main_photo_url.startswith("/"):
                # 且設定檔中有設定 `BASE_URL`...
                if Config.BASE_URL:
                    # 則組合成完整的絕對路徑 URL。
                    card_photo_url = f"{Config.BASE_URL.rstrip('/')}{store.main_photo_url}"
                else:
                    logger.warning(
                        "BASE_URL is not set... Carousel will use a placeholder image."
                    )
            else:
                # 如果 URL 已經是絕對路徑，則直接使用。
                card_photo_url = store.main_photo_url

        # 根據店家的合作等級，取得對應的狀態文字。
        status_text = partner_level_map.get(store.partner_level, partner_level_0)

        # 準備 "店家介紹" 按鈕的 postback 資料。
        summary_postback_data = {
            "action": ActionType.SHOW_STORE_SUMMARY,
            "store_id": store.store_id,
        }
        # 建立一個輪播卡片 (`CarouselColumn`)。
        column = CarouselColumn(
            thumbnail_image_url=card_photo_url, # 卡片頂部的圖片
            title=translated_store_name[:40], # 卡片標題（LINE API 有長度限制）
            text=status_text[:60], # 卡片內文（LINE API 有長度限制）
            actions=[
                # 按鈕1: "開始點餐"。`URIAction` 會開啟指定的 URL (此處為 LIFF URL)。
                URIAction(label=start_ordering_label[:20], uri=liff_full_url),
                # 按鈕2: "店家介紹"。`PostbackAction`。
                PostbackAction(
                    label=view_summary_label[:20],
                    data=json.dumps(summary_postback_data),
                    displayText=translated_display_text,
                ),
            ],
        )
        carousel_columns.append(column)

    # 取得輪播訊息的替代文字。
    alt_text = await get_translated_text(
        user,
        "alt_text_store_list",
        translate_client=translate_client,
        lang_code_map=lang_code_map,
    )
    # 將所有卡片放入 `CarouselTemplate`，再包裝成 `TemplateMessage` 並返回。
    return TemplateMessage(
        alt_text=alt_text, template=CarouselTemplate(columns=carousel_columns)
    )


async def create_order_history_carousel(
    orders: List[Order], user: User, translate_client, lang_code_map: Dict[str, Any]
) -> TemplateMessage:
    """
    根據歷史訂單列表，建立一個訂單輪播訊息。
    """
    carousel_columns = []

    # --- 批次翻譯 ---
    # 1. 靜態文字：按鈕標籤。
    template_keys_to_translate = ["view_order_details", "order_again"]
    static_texts = [REPLY_TEMPLATES[key] for key in template_keys_to_translate]

    # 過濾掉沒有關聯店家資料的異常訂單。
    valid_orders = [order for order in orders if order.store]

    # 2. 動態文字：每個訂單卡片的按鈕顯示文字。
    display_texts_to_translate = [
        REPLY_TEMPLATES["querying_order_details"].format(
            store_name=order.store.store_name
        )
        for order in valid_orders
    ]

    # 3. 動態文字：每個訂單卡片的店家名稱。
    store_names_to_translate = [order.store.store_name for order in valid_orders]

    # 合併並執行批次翻譯。
    all_texts_to_translate = (
        static_texts + display_texts_to_translate + store_names_to_translate
    )
    translated_texts = await translate_texts_batch(
        all_texts_to_translate, user, translate_client, lang_code_map
    )

    # --- 處理翻譯結果 ---
    num_static = len(static_texts)
    num_orders = len(valid_orders)

    view_details_label = translated_texts[0]
    order_again_label = translated_texts[1]

    translated_display_texts = translated_texts[num_static : num_static + num_orders]
    translated_store_names = translated_texts[num_static + num_orders :]

    # --- 建立輪播卡片 ---
    for i, order in enumerate(valid_orders):
        store = order.store

        # 組合卡片內文，顯示訂單時間和總金額。
        card_text = (
            f"📅 {order.order_time.strftime('%Y-%m-%d %H:%M')}\n💰 ${order.total_amount}"
        )

        # 取得對應該訂單的翻譯結果。
        translated_display_text = translated_display_texts[i]
        translated_store_name = translated_store_names[i]

        # 準備 "查看訂單詳情" 按鈕的 postback 資料。
        details_postback_data = {
            "action": ActionType.SHOW_ORDER_DETAILS,
            "order_id": order.order_id,
        }
        # 定義卡片的兩個按鈕。
        actions = [
            PostbackAction(
                label=view_details_label,
                data=json.dumps(details_postback_data),
                displayText=translated_display_text,
            ),
            URIAction(label=order_again_label, uri=create_liff_url(user, store)),
        ]

        # 建立輪播卡片。
        column = CarouselColumn(
            title=translated_store_name[:40], text=card_text[:60], actions=actions
        )
        carousel_columns.append(column)

    # 取得輪播訊息的替代文字。
    alt_text = await get_translated_text(
        user,
        "alt_text_order_history",
        translate_client=translate_client,
        lang_code_map=lang_code_map,
    )
    # 將所有卡片組合成輪播模板訊息並返回。
    return TemplateMessage(
        alt_text=alt_text, template=CarouselTemplate(columns=carousel_columns)
    )


async def create_order_details_message(
    order: Order, user: User, translate_client, lang_code_map: Dict[str, Any]
) -> TextMessage:
    """
    建立一則顯示訂單詳細內容的純文字訊息。
    (此版本將所有需翻譯的文字合併到一次批次請求中)
    """
    if not order.store:
        logger.warning(
            f"create_order_details_message called for order_id {order.order_id} which has no associated store."
        )
        return await create_simple_text_message(
            user,
            "generic_error",
            translate_client=translate_client,
            lang_code_map=lang_code_map,
        )

    # --- 1. 合併所有待翻譯文字 ---
    # a. 靜態標籤文字
    template_keys = [
        "order_details_title",
        "order_details_store",
        "order_details_time",
        "order_details_total",
        "order_details_items_header",
    ]
    static_texts = [REPLY_TEMPLATES.get(key, "") for key in template_keys]

    # b. 動態文字：店家名稱
    store_name = order.store.store_name

    # c. 動態文字：所有品項的原始名稱
    original_item_names = [
        item.original_name
        for item in order.items
        if item.original_name
    ]

    # 將靜態標籤、店家名稱、品項名稱全部放入一個列表
    all_texts_to_translate = static_texts + [store_name] + original_item_names

    # --- 2. 執行單次批次翻譯 ---
    translated_texts = await translate_texts_batch(
        texts=all_texts_to_translate,
        user=user,
        translate_client=translate_client,
        lang_code_map=lang_code_map,
    )

    # --- 3. 拆解翻譯結果 ---
    num_static = len(static_texts)
    
    # a. 取得翻譯後的靜態標籤
    title, store_label, time_label, total_label, items_header = translated_texts[:num_static]
    
    # b. 取得翻譯後的店家名稱
    translated_store_name = translated_texts[num_static]
    
    # c. 取得翻譯後的品項名稱列表
    translated_item_names = translated_texts[num_static + 1:]
    
    # d. 建立品項名稱的映射字典，方便後續查找
    translation_map = dict(zip(original_item_names, translated_item_names))

    # --- 4. 組合最終訊息文字 ---
    details_parts = [
        f"<{title}>",
        "--------------------",
        f"{store_label}: {translated_store_name}",
        f"{time_label}: {order.order_time.strftime('%Y-%m-%d %H:%M')}",
        f"{total_label}: ${order.total_amount}",
    ]

    if order.items:
        details_parts.append("\n" + f"{items_header}:")
        for item in order.items:
            # 從映射中取得翻譯名稱，如果找不到則備用為原始名稱
            item_name = translation_map.get(item.original_name, item.original_name)
            details_parts.append(
                f"- {item_name} x {item.quantity_small}  (${item.subtotal})"
            )

    reply_text = "\n".join(details_parts)
    return TextMessage(text=reply_text)


async def create_simple_text_message(
    user: User,
    template_key: str,
    *,
    translate_client,
    lang_code_map: Dict[str, Any],
    **format_args,
) -> TextMessage:
    """
    一個通用的輔助函式，用於從範本建立一則簡單的、經過翻譯的文字訊息。
    """
    # 呼叫 `get_translated_text` 取得翻譯並格式化後的文字。
    text = await get_translated_text(
        user,
        template_key,
        translate_client=translate_client,
        lang_code_map=lang_code_map,
        **format_args,
    )
    # 將文字包裝成 `TextMessage` 物件並返回。
    return TextMessage(text=text)
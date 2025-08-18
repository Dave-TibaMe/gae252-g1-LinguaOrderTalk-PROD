# 導入第三方函式庫
import aiohttp  # 用於執行非同步 HTTP 請求

# 導入標準函式庫
import asyncio  # 用於執行非同步操作
import io       # 用於處理記憶體中的二進位資料流，如此處的圖片
import json     # 用於解析 JSON 資料
import logging  # 用於日誌記錄
import os       # 用於與作業系統互動，如此處讀取檔案路徑

# 導入非同步上下文管理器工具
from contextlib import asynccontextmanager
# 導入型別提示
from typing import Any, Dict, List

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request # FastAPI 核心元件
from fastapi.responses import StreamingResponse # 用於串流回傳圖片等大型檔案
from linebot.v3 import WebhookParser # 用於解析 LINE webhook 事件
from linebot.v3.exceptions import InvalidSignatureError # 簽章驗證失敗時的例外
from linebot.v3.messaging import ( # LINE Messaging API 的核心元件
    AsyncApiClient,
    AsyncMessagingApi as MessagingApi, # 將 AsyncMessagingApi 重新命名為 MessagingApi 方便使用
    Configuration,
    Message,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import ( # LINE webhook 事件的各種模型
    FollowEvent,
    LocationMessageContent,
    MessageEvent,
    PostbackEvent,
    StickerMessageContent,
    TextMessageContent,
)
from sqlalchemy.ext.asyncio import AsyncSession # SQLAlchemy 的非同步會話

# 導入專案內部模組
from . import clients, crud, line_messages # 導入客戶端初始化、資料庫操作、訊息產生模組
from .config import Config # 導入設定檔
from .constants import ActionType # 導入動作類型常數
from .database import AsyncSessionLocal # 導入資料庫會話工廠
from .dependencies import ( # 導入 FastAPI 依賴項
    get_aiohttp_session,
    get_lang_code_map,
    get_language_display_texts,
    get_native_language_list,
    get_translate_client,
)
from .models import User # 導入使用者模型
from .services import language_service, order_service, store_service, user_service # 導入所有服務層邏輯

# 取得 uvicorn 的錯誤日誌記錄器，讓此處的日誌與伺服器日誌整合
logger = logging.getLogger("uvicorn.error")


def _check_critical_configs():
    """在應用程式啟動時檢查所有必要的環境變數是否已設定。"""
    # 定義一個字典，包含所有攸關系統運作的必要設定
    critical_vars = {
        "CHANNEL_ACCESS_TOKEN": Config.CHANNEL_ACCESS_TOKEN,
        "CHANNEL_SECRET": Config.CHANNEL_SECRET,
        "DATABASE_URL": Config.DATABASE_URL,
        "MAPS_API_KEY": Config.MAPS_API_KEY,
    }

    # 找出所有未設定的變數名稱
    missing_vars = [name for name, value in critical_vars.items() if not value]

    # 如果有任何必要變數缺失
    if missing_vars:
        # 逐一記錄嚴重錯誤日誌
        for var_name in missing_vars:
            logger.critical(f"CRITICAL: Missing required environment variable: {var_name}")
        
        # 拋出 SystemExit 例外，直接終止應用程式啟動
        raise SystemExit(
            "Application startup failed due to missing critical environment variables."
        )

    # 如果所有必要變數都已設定，記錄一條參考訊息
    logger.info("All critical environment variables are set.")

    # 檢查可選設定 LIFF_ID，如果未設定則發出警告
    if not Config.LIFF_ID:
        logger.warning(
            "Optional environment variable 'LIFF_ID' is not set. LIFF-related features will be unavailable."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 的生命週期管理器。
    `yield` 之前的程式碼會在應用程式啟動時執行一次。
    `yield` 之後的程式碼會在應用程式關閉時執行一次。
    """
    # --- 應用程式啟動 ---
    
    # 1. 檢查關鍵設定檔
    _check_critical_configs()

    # 2. 初始化並儲存共用資源到 app.state 中
    # `app.state` 是一個可以讓你在應用程式生命週期內儲存任意物件的地方
    app.state.aiohttp_session = aiohttp.ClientSession()
    logger.info("AIOHTTP ClientSession created.")

    app.state.translate_client = clients.initialize_google_clients()

    logger.info("Application startup: Concurrently loading initial data...")

    # 3. 同時（並行）載入需要的初始資料，以加速啟動
    
    # 定義一個同步函式來讀取本地 JSON 檔案
    def load_native_languages_sync():
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(
                current_dir, "static", "data", "language_list_native.json"
            )
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load language_list_native.json: {e}")
            return []

    # 使用 `asyncio.to_thread` 將同步的檔案讀取操作放到背景執行緒，避免阻塞事件循環
    load_languages_task = asyncio.to_thread(load_native_languages_sync)

    # 定義一個非同步函式來從資料庫讀取語言映射
    async def load_db_mappings():
        lang_map = {}
        async with AsyncSessionLocal() as session:
            try:
                languages = await crud.get_all_languages(session)
                for lang in languages:
                    lang_map[lang.line_lang_code] = {
                        "translation": lang.translation_lang_code,
                        "stt": lang.stt_lang_code,
                    }
                logger.info(f"Successfully loaded {len(lang_map)} language mappings from DB.")
            except Exception as e:
                logger.error(f"Failed to load language mappings from DB: {e}")
        return lang_map

    # 使用 `asyncio.gather` 來同時執行讀取資料庫和讀取檔案這兩個任務
    results = await asyncio.gather(load_db_mappings(), load_languages_task)

    # 將載入的結果存入 app.state
    app.state.lang_code_map = results[0]
    app.state.native_language_list = results[1]

    # 4. 預先翻譯並快取語言選單中會用到的顯示文字，提升後續回應速度
    logger.info("Pre-translating language display texts...")
    app.state.language_display_texts = {}
    if app.state.translate_client:
        tasks = []
        for lang_item in app.state.native_language_list:
            lang_code = lang_item["lang_code"]
            lang_name = lang_item["lang_name"][0]
            # 為每種語言建立一個翻譯任務
            task = line_messages.get_translated_text_for_target_lang(
                template_key="setting_language_to",
                target_line_lang_code=lang_code,
                translate_client=app.state.translate_client,
                lang_code_map=app.state.lang_code_map,
                lang_name=lang_name,
            )
            tasks.append((lang_code, task))

        # 使用 `asyncio.gather` 同時執行所有翻譯任務
        translated_results = await asyncio.gather(*[t[1] for t in tasks])
        
        # 將翻譯結果存入快取字典
        for i, (lang_code, _) in enumerate(tasks):
            app.state.language_display_texts[lang_code] = translated_results[i]

        logger.info(
            f"Successfully cached {len(app.state.language_display_texts)} language display texts."
        )
    else:
        logger.warning(
            "Translate client not available. Skipping pre-translation of display texts."
        )
    
    logger.info("Successfully loaded and formatted initial data into app.state.")

    # `yield` 關鍵字：到此，啟動程序完成。FastAPI 開始接收請求。
    yield

    # --- 應用程式關閉 ---
    # `yield` 之後的程式碼在應用程式收到關閉信號時執行
    await app.state.aiohttp_session.close()
    logger.info("AIOHTTP ClientSession closed.")
    logger.info("Application shutdown.")


# 建立 FastAPI 應用程式實例，並傳入生命週期管理器
app = FastAPI(title="LinguaOrderTalk Bot Service", lifespan=lifespan)
# 使用設定檔中的 Access Token 初始化 LINE SDK 的設定
line_config = Configuration(access_token=Config.CHANNEL_ACCESS_TOKEN)
# 使用設定檔中的 Channel Secret 初始化 webhook 解析器，用於驗證簽章
parser = WebhookParser(Config.CHANNEL_SECRET)


@app.get("/api/v1/places/photo/{photo_name:path}")
async def get_google_place_photo(
    photo_name: str, aiohttp_session: aiohttp.ClientSession = Depends(get_aiohttp_session)
):
    """
    一個代理 API 端點，用於安全地取得 Google Place 的照片。
    `photo_name` 是一個路徑參數，可以包含斜線 (`/`)。
    這個端點的作用是隱藏後端的 Google MAPS_API_KEY，不讓它暴露在前端。
    """
    # 檢查 API 金鑰是否存在
    if not Config.MAPS_API_KEY:
        logger.error("MAPS_API_KEY is not configured. Cannot proxy photo request.")
        raise HTTPException(status_code=500, detail="Server configuration error.")

    # 組合 Google Places Photo API 的實際 URL
    google_photo_url = (
        f"https://places.googleapis.com/v1/{photo_name}/media"
        f"?maxHeightPx=1024&key={Config.MAPS_API_KEY}"
    )

    try:
        # 使用共用的 aiohttp session 發送 GET 請求到 Google
        async with aiohttp_session.get(google_photo_url) as response:
            # 如果 Google 回應錯誤狀態碼，則拋出例外
            response.raise_for_status()

            # 取得回應的內容類型 (e.g., 'image/jpeg')
            content_type = response.headers.get("Content-Type")

            # 讀取圖片的二進位內容
            content = await response.read()
            # 使用 StreamingResponse 將圖片內容串流回傳給客戶端，這樣更有效率
            return StreamingResponse(io.BytesIO(content), media_type=content_type)

    except aiohttp.ClientError as e:
        # 如果請求失敗，記錄錯誤並回傳 502 Bad Gateway 錯誤
        logger.error(f"Failed to fetch photo from Google Places API. Error: {e}")
        raise HTTPException(
            status_code=502, detail="Failed to retrieve image from upstream service."
        )


@app.post("/callback")
async def callback(
    request: Request,
    background_tasks: BackgroundTasks,
    # 以下都是透過 FastAPI 的依賴注入系統，從 `dependencies.py` 取得的共用資源
    aiohttp_session: aiohttp.ClientSession = Depends(get_aiohttp_session),
    translate_client=Depends(get_translate_client),
    lang_code_map: Dict[str, Any] = Depends(get_lang_code_map),
    native_language_list: List[Dict[str, Any]] = Depends(get_native_language_list),
    language_display_texts: Dict[str, str] = Depends(get_language_display_texts),
):
    """
    接收 LINE 平台 webhook 事件的主要端點。
    """
    # 從請求標頭中取得 LINE 的簽章
    signature = request.headers.get("X-Line-Signature", "")
    # 取得請求的原始內容 (body)
    body = await request.body()
    try:
        # 使用 parser 驗證簽章並解析事件內容
        events = parser.parse(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        # 如果簽章無效，回傳 400 錯誤
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 遍歷所有解析出來的事件
    for event in events:
        # 對於每一個事件，將其處理邏輯 `handle_single_event_task` 作為一個背景任務加入。
        # FastAPI 會在回傳 `200 OK` 給 LINE 平台之後，才在背景執行這些任務。
        # 這是處理 LINE webhook 的標準做法，可以避免因處理時間過長導致 LINE 平台認為請求失敗。
        background_tasks.add_task(
            handle_single_event_task,
            event=event,
            aiohttp_session=aiohttp_session,
            translate_client=translate_client,
            lang_code_map=lang_code_map,
            native_language_list=native_language_list,
            language_display_texts=language_display_texts,
        )
    # 立即回傳 "OK"，表示已成功接收到事件
    return "OK"


async def handle_single_event_task(
    event,
    aiohttp_session: aiohttp.ClientSession,
    translate_client,
    lang_code_map: dict,
    native_language_list: list,
    language_display_texts: dict,
):
    """
    在背景執行的單一事件處理函式。
    """
    # 建立一個非同步資料庫會話，使用 `async with` 確保會話在使用後能被正確關閉。
    async with AsyncSessionLocal() as db:

        # 定義一個巢狀函式，用於在發生未知錯誤時，嘗試發送一則通用的錯誤訊息給使用者。
        async def _send_error_reply(event):
            try:
                # 建立錯誤訊息物件
                error_message = await line_messages.create_simple_text_message(
                    user=None, # 此時可能還不知道 user 物件
                    template_key="generic_error",
                    translate_client=translate_client,
                    lang_code_map=lang_code_map,
                )
                async with AsyncApiClient(line_config) as api_client:
                    messaging_api = MessagingApi(api_client)
                    # 如果事件有 reply_token，就用 replyMessage
                    if hasattr(event, "reply_token") and event.reply_token:
                        await messaging_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token, messages=[error_message]
                            )
                        )
                    # 否則，如果能取得 user_id，就用 pushMessage
                    elif hasattr(event, "source") and hasattr(event.source, "user_id"):
                        await messaging_api.push_message(
                            PushMessageRequest(
                                to=event.source.user_id, messages=[error_message]
                            )
                        )
            except Exception as e:
                logger.error(f"Failed to send error message to user: {e}")

        # 使用一個大的 try...except 區塊來捕捉處理過程中所有的可能錯誤
        try:
            # --- 事件路由邏輯 ---
            # 判斷事件類型
            if isinstance(event, FollowEvent):
                # 如果是使用者加入好友或解除封鎖事件
                await user_service.handle_new_user_follow(
                    db, event.source.user_id, translate_client, lang_code_map
                )
                return # 處理完畢，直接返回

            elif isinstance(event, MessageEvent):
                # 如果是訊息事件
                user = await crud.get_user_by_line_id(db, event.source.user_id)
                if not user:
                    # 如果在資料庫找不到使用者，準備一則 "user not found" 訊息
                    reply_messages = [
                        await line_messages.create_simple_text_message(
                            None,
                            "user_not_found",
                            translate_client=translate_client,
                            lang_code_map=lang_code_map,
                        )
                    ]
                else:
                    # 根據訊息的具體內容類型，分派到不同的處理器
                    if isinstance(event.message, TextMessageContent):
                        # 文字訊息
                        reply_messages = await process_text_command(
                            user,
                            event.message.text,
                            db,
                            translate_client,
                            lang_code_map,
                            native_language_list,
                            language_display_texts,
                        )
                    elif isinstance(event.message, LocationMessageContent):
                        # 位置訊息
                        reply_messages = await handle_location_message(
                            event, user, db, aiohttp_session, translate_client, lang_code_map
                        )
                    elif isinstance(event.message, StickerMessageContent):
                        # 貼圖訊息，當作未知指令處理，回傳主選單
                        reply_messages = await user_service.handle_unknown_command(
                            user, translate_client, lang_code_map
                        )

            elif isinstance(event, PostbackEvent):
                # 如果是 Postback 事件（使用者點擊了 PostbackAction 按鈕）
                user = await crud.get_user_by_line_id(db, event.source.user_id)
                if not user:
                    reply_messages = [
                        await line_messages.create_simple_text_message(
                            None,
                            "user_not_found",
                            translate_client=translate_client,
                            lang_code_map=lang_code_map,
                        )
                    ]
                else:
                    reply_messages = await handle_postback(
                        event,
                        user,
                        db,
                        translate_client,
                        lang_code_map,
                        native_language_list,
                        language_display_texts,
                    )

            else:
                # 如果是其他未處理的事件類型，直接返回
                return

            # 如果前面邏輯產生了需要回覆的訊息 (`reply_messages`)
            async with AsyncApiClient(line_config) as api_client:
                # 呼叫 LINE API 的 replyMessage 方法來回覆訊息
                await MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token, messages=reply_messages
                    )
                )

        except Exception as e:
            # 如果在整個處理過程中發生任何未被捕獲的例外
            user_id = (
                event.source.user_id
                if hasattr(event, "source") and hasattr(event.source, "user_id")
                else "N/A"
            )
            # 記錄詳細的錯誤日誌，包括錯誤資訊和堆疊追蹤
            logger.error(
                f"Error processing event for user {user_id}: {event}", exc_info=True
            )
            # 嘗試發送通用錯誤訊息給使用者
            await _send_error_reply(event)


async def handle_location_message(
    event: MessageEvent,
    user: User,
    db: AsyncSession,
    aiohttp_session: aiohttp.ClientSession,
    translate_client,
    lang_code_map: dict,
) -> List[Message]:
    """
    處理使用者傳送的位置訊息。
    """
    loc = event.message
    # 呼叫店家服務，根據使用者位置尋找並同步附近的店家資料
    stores = await store_service.find_and_sync_nearby_stores(
        db=db,
        aiohttp_session=aiohttp_session,
        user_lat=loc.latitude,
        user_lng=loc.longitude,
        title=loc.title,
        address=loc.address,
    )

    if not stores:
        # 如果找不到店家，回傳 "no stores found" 訊息
        return [
            await line_messages.create_simple_text_message(
                user,
                "no_stores_found",
                translate_client=translate_client,
                lang_code_map=lang_code_map,
            )
        ]
    else:
        # 如果找到店家，建立並回傳店家輪播訊息
        return [
            await line_messages.create_store_carousel_message(
                stores, user, translate_client, lang_code_map
            )
        ]


async def handle_postback(
    event: PostbackEvent,
    user: User,
    db: AsyncSession,
    translate_client,
    lang_code_map: dict,
    native_language_list: list,
    language_display_texts: dict,
) -> List[Message]:
    """
    處理 Postback 事件。
    """
    try:
        # 解析 postback data 欄位中的 JSON 字串
        data = json.loads(event.postback.data)
        # 取得 action 類型
        action_str = data.get("action")

        # --- Postback 路由邏輯 ---
        if action_str == ActionType.SHOW_ORDER_DETAILS:
            # 如果是 "顯示訂單詳情"
            raw_order_id = data.get("order_id")
            try:
                if raw_order_id is None:
                    raise ValueError("order_id is missing from postback data")
                
                order_id = int(raw_order_id)
                # 呼叫訂單服務處理
                return await order_service.handle_show_order_details_request(
                    db, user, order_id, translate_client, lang_code_map
                )

            except (ValueError, TypeError):
                # 如果 order_id 格式不正確，記錄錯誤並回傳通用錯誤訊息
                logger.error(
                    f"Invalid order_id '{raw_order_id}' received in postback for user {user.line_user_id}."
                )
                return [
                    await line_messages.create_simple_text_message(
                        user,
                        "generic_error",
                        translate_client=translate_client,
                        lang_code_map=lang_code_map,
                    )
                ]

        elif action_str == ActionType.ORDER_HISTORY:
            # 如果是 "查詢歷史訂單"，呼叫訂單服務處理
            return await order_service.handle_order_history_request(
                db, user, translate_client, lang_code_map
            )

        elif action_str == ActionType.CHANGE_LANGUAGE:
            # 如果是 "變更語言"，呼叫語言服務處理
            return await language_service.handle_change_language_request(
                user,
                translate_client,
                lang_code_map,
                native_language_list,
                language_display_texts,
            )

        elif action_str == ActionType.SET_LANGUAGE:
            # 如果是 "設定語言"
            lang_code = data.get("lang_code")
            # 呼叫語言服務處理
            return await language_service.handle_set_language_request(
                db, user, lang_code, translate_client, lang_code_map, native_language_list
            )

        elif action_str == ActionType.SHOW_STORE_SUMMARY:
            # 如果是 "顯示店家介紹"
            raw_store_id = data.get("store_id")
            try:
                if raw_store_id is None:
                    raise ValueError("store_id is missing from postback data")

                store_id = int(raw_store_id)
                # 直接呼叫 crud 函式查詢翻譯摘要
                summary = await crud.get_store_translation_summary(
                    db, store_id, user.preferred_lang
                )
                if summary:
                    # 如果有摘要，直接回傳文字訊息
                    return [TextMessage(text=summary)]
                else:
                    # 如果沒有摘要，回傳 "not found" 訊息
                    return [
                        await line_messages.create_simple_text_message(
                            user,
                            "store_summary_not_found",
                            translate_client=translate_client,
                            lang_code_map=lang_code_map,
                        )
                    ]

            except (ValueError, TypeError):
                logger.error(
                    f"Invalid store_id '{raw_store_id}' received in postback for user {user.line_user_id}."
                )
                return [
                    await line_messages.create_simple_text_message(
                        user,
                        "generic_error",
                        translate_client=translate_client,
                        lang_code_map=lang_code_map,
                    )
                ]
        
        else:
            # 如果是未知的 action
            logger.warning(f"Unknown postback action '{action_str}' received.")
            return await user_service.handle_unknown_command(
                user, translate_client, lang_code_map
            )

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # 如果 postback data 格式錯誤 (例如無法解析 JSON)，記錄錯誤並回傳通用錯誤訊息
        logger.error(
            f"Error processing postback data for user {user.line_user_id}: {e}",
            exc_info=True,
        )
        return [
            await line_messages.create_simple_text_message(
                user,
                "generic_error",
                translate_client=translate_client,
                lang_code_map=lang_code_map,
            )
        ]


async def process_text_command(
    user: User,
    text: str,
    db: AsyncSession,
    translate_client,
    lang_code_map: dict,
    native_language_list: list,
    language_display_texts: dict,
) -> List[Message]:
    """
    處理使用者傳送的文字訊息中的簡單指令。
    """
    # 將使用者輸入的文字去除頭尾空白並轉為小寫，方便比對
    user_text = text.strip().lower()

    # --- 文字指令路由 ---
    # 這裡的指令是英文，因為主要互動是透過按鈕。這部分可以視為一個備用或開發時的快速指令。
    if user_text == "order now":
        return await order_service.handle_order_now_request(
            user, translate_client, lang_code_map
        )

    elif user_text == "change language":
        return await language_service.handle_change_language_request(
            user,
            translate_client,
            lang_code_map,
            native_language_list,
            language_display_texts,
        )

    elif user_text == "order history":
        return await order_service.handle_order_history_request(
            db, user, translate_client, lang_code_map
        )

    else:
        # 如果不是任何已知的指令，回傳主選單
        return await user_service.handle_unknown_command(
            user, translate_client, lang_code_map
        )
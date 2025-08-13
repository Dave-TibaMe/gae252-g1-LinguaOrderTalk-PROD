import os
import json
import asyncio
import logging
from typing import List
from urllib.parse import quote, parse_qs

import aiohttp

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from sqlalchemy import select, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

# 匯入 LINE Bot 元件
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    AsyncApiClient, Configuration,
    AsyncMessagingApi as MessagingApi,
    AsyncMessagingApiBlob as MessagingApiBlob,
    TextMessage, PushMessageRequest, ReplyMessageRequest,
    TemplateMessage, CarouselTemplate, CarouselColumn,
    QuickReply, QuickReplyItem, LocationAction,
    URIAction, PostbackAction, ButtonsTemplate
)
from linebot.v3.webhooks import (
    MessageEvent, TextMessageContent, AudioMessageContent,
    FollowEvent, LocationMessageContent, PostbackEvent,
    StickerMessageContent
)

# 匯入 Google 服務和本地模組
from google.cloud import translate_v2 as translate
from google.cloud import speech

from app.config import Config
from app.database import AsyncSessionLocal
from app.models import User, Language, Store, Order, OrderItem

language_lookup_dict = {}
LANG_CODE_MAP = {}
LANGUAGE_LIST_STRING = ""

# --- 【修改處】建立 Lifespan 管理員 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 在應用程式啟動時執行
    global LANGUAGE_LIST_STRING, LANG_CODE_MAP, language_lookup_dict # 宣告我們要修改的是全域變數

    # --- 1. 載入 language_lookup.json (從全域搬移至此) ---
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, 'static', 'data', 'languages_lookup.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            language_list = json.load(f)
        for item in language_list:
            lang_code = item['lang_code']
            for name in item['lang_name']:
                language_lookup_dict[name.lower()] = lang_code
        logging.info("成功載入並處理 language_lookup_dict。")
    except Exception as e:
        logging.warning(f"警告：載入 languages_lookup.json 失敗: {e}")


    # --- 2. 從資料庫載入語言對照表 ---
    logging.info("應用程式啟動中，正在從資料庫載入語言對照表...")
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(Language))
            languages = result.scalars().all()
            for lang in languages:
                LANG_CODE_MAP[lang.line_lang_code] = {
                    "translation": lang.translation_lang_code,
                    "stt": lang.stt_lang_code
                }
            logging.info(f"成功載入 {len(LANG_CODE_MAP)} 筆語言對照資料。")
        except Exception as e:
            logging.error(f"從資料庫載入語言對照表失敗: {e}")

    # --- 3. 讀取並格式化原生語言列表 JSON ---
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, 'static', 'data', 'language_list_native.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            native_languages = json.load(f)
        lang_items = []
        for item in native_languages:
            native_name = item['lang_name'][0]
            lang_items.append(f"{native_name}")
        LANGUAGE_LIST_STRING = "\n".join(lang_items)
        logging.info("成功載入並格式化原生語言列表。")
    except Exception as e:
        logging.warning(f"警告：載入 language_list_native.json 失敗: {e}")
        LANGUAGE_LIST_STRING = ""

    yield

    logging.info("應用程式正在關閉...")

# --- 初始化應用程式與服務 ---
logging.basicConfig(level=logging.INFO)
app = FastAPI(title="LinguaOrderTalk Bot Service", lifespan=lifespan)

line_config = Configuration(access_token=Config.CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(Config.CHANNEL_SECRET)

translate_client = translate.Client()
speech_client = speech.SpeechClient()

# --- 回覆訊息樣板 ---
REPLY_TEMPLATES = {
    "welcome_text_message": "您可以透過下方的按鈕開始使用我們的服務，或隨時輸入文字與我互動。",
    "button_card_prompt": "請選擇服務項目：",
    "button_label_change_language": "更改語言",
    "button_label_order_now": "立即點餐",
    "button_label_order_history": "歷史訂單",
    "ask_language": "請直接說出或輸入您想設定的語言。(輸入 0 可取消)",
    "language_set_success": "語言已成功設定為: {lang_name}。",
    "language_not_recognized": "對不起，無法識別您輸入的語言，請再試一次。(輸入 0 可取消)",
    "user_not_found": "錯誤：找不到您的使用者資料，請嘗試重新加入好友。",
    "audio_processing_error": "處理錄音時發生錯誤，請稍後再試。(輸入 0 可取消)",
    "audio_not_recognized": "對不起，我聽不清楚您說的內容，請再試一次。(輸入 0 可取消)",
    "ask_location": "請分享您目前的位置，為您尋找附近的店家。(輸入 0 可取消)",
    "no_stores_found": "對不起，您附近找不到任何店家。",
    "reprompt_location": "請點擊下方的按鈕來分享您的位置。(輸入 0 可取消)",
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
    "operation_cancelled": "好的，已取消操作。請問還有什麼可以為您服務的嗎？",
    "partner_level_0": "非合作店家",
    "partner_level_1": "合作店家",
    "partner_level_2": "VIP店家"
}

async def translate_arbitrary_text(user: User, text_to_translate: str, source_lang: str = 'zh-TW') -> str:
    """
    根據使用者偏好語言，翻譯任意指定的文字。
    如果翻譯失敗或無需翻譯，則回傳原始文字。
    """
    # 如果沒有提供文字、使用者或其偏好語言，直接回傳原文
    if not text_to_translate or not user or not user.preferred_lang:
        return text_to_translate

    # 從全域對照表中找到 Google Translate API 需要的目標語言代碼
    lang_map = LANG_CODE_MAP.get(user.preferred_lang)
    target_lang = "" # 初始化為空字串
    if lang_map and lang_map.get("translation"):
        target_lang = lang_map["translation"]
    else:
        # 如果在對照表中找不到，則直接使用 user.preferred_lang
        target_lang = user.preferred_lang

    # 如果目標語言與來源語言相同，則無需呼叫 API，直接回傳原文以節省資源
    # (例如，用戶設定為繁體中文，店家名稱也是繁體中文)
    if target_lang == source_lang:
        return text_to_translate

    try:
        # 執行緒中安全地呼叫同步的翻譯 API
        result = await asyncio.to_thread(
            translate_client.translate,
            text_to_translate,
            target_language=target_lang,
            source_language=source_lang # 明確指定來源語言以提高準確度
        )
        # 回傳翻譯後的文字
        return result['translatedText']

    except Exception as e:
        # 如果 API 呼叫失敗，記錄錯誤並安全地回傳原始文字
        logging.error(f"Arbitrary translation of '{text_to_translate}' to {target_lang} failed: {e}")
        return text_to_translate

# --- 翻譯輔助函式 (異步) ---
async def get_translated_text(user: User, template_key: str, **kwargs) -> str:
    """
    根據使用者偏好語言，取得翻譯後的文字。
    """
    default_text = REPLY_TEMPLATES.get(template_key, "Message template undefined.")

    # 如果找不到使用者或其偏好語言，直接回傳預設文字
    if not user or not user.preferred_lang:
        return default_text.format(**kwargs)
        
    # 從記憶體的對照表中，找到對應的 translation_lang_code
    lang_map = LANG_CODE_MAP.get(user.preferred_lang)
    target_lang = ""
    if lang_map and lang_map.get("translation"):
        target_lang = lang_map["translation"]
    else:
        # 如果在對照表中找不到，則退回使用原始的 preferred_lang
        target_lang = user.preferred_lang

    # 如果目標語言我們預設樣板的語言，則無需呼叫 API，直接回傳原文以節省資源
    if target_lang == 'zh-TW':
        return default_text.format(**kwargs)

    try:
        # 呼叫翻譯 API
        result = await asyncio.to_thread(
            translate_client.translate,
            default_text,
            target_language=target_lang,
            source_language='zh-TW'
        )
        translated_text = result['translatedText']
        return translated_text.format(**kwargs)
    
    except Exception as e:
        logging.error(f"Translation to {target_lang} for key '{template_key}' failed: {e}")
        # 若翻譯失敗，安全地退回到預設文字
        return default_text.format(**kwargs)

async def localize_lang_name(canonical_name: str, target_lang: str) -> str:
    if target_lang != 'zh-Hant': # 假設標準名稱都是中文
        try:
            result = await asyncio.to_thread(
                translate_client.translate,
                canonical_name, 
                target_language=target_lang,
                source_language='zh-TW'
            )
            return result['translatedText']
        except Exception as e:
            logging.error(f"Failed to localize lang_name '{canonical_name}' to {target_lang}: {e}")
    return canonical_name

# 【新功能】建立主選單訊息列表的輔助函式
async def get_main_menu_messages(user: User) -> list:
    """
    建立並回傳一個包含主要引導文字和主選單按鈕的訊息列表。
    """
    # 1. 準備第一則訊息：純文字說明
    welcome_text = await get_translated_text(user, "welcome_text_message")
    text_message = TextMessage(text=welcome_text)

    # 2. 準備第二則訊息：按鈕卡片
    translated_texts = await asyncio.gather(
        get_translated_text(user, "button_card_prompt"), # 極簡提示文字
        get_translated_text(user, "button_label_order_now"),
        get_translated_text(user, "button_label_order_history"),
        get_translated_text(user, "button_label_change_language"),
    )
    prompt_text, order_now_label, history_label, change_lang_label = translated_texts

    buttons_template = ButtonsTemplate(
        # 這裡的 text 使用我們新的極簡提示文字
        text=prompt_text,
        actions=[
            PostbackAction(label=order_now_label, data="action=order_now"),
            PostbackAction(label=history_label, data="action=order_history"),
            PostbackAction(label=change_lang_label, data="action=change_language"),
        ]
    )
    template_message = TemplateMessage(alt_text=prompt_text, template=buttons_template)

    # 回傳包含兩則訊息的列表
    return [text_message, template_message]

def create_liff_url(user: User, store: Store) -> str:
    """
    根據使用者和店家物件，產生一個標準化的 LIFF 啟動 URL。
    包含了所有必要的查詢參數，並對店名進行 URL 編碼。
    """
    liff_id = Config.LIFF_ID
    # 對店家名稱進行 URL 編碼，避免中文或特殊符號造成網址錯誤
    encoded_store_name = quote(store.store_name)
    is_partner = 'true' if store.partner_level > 0 else 'false'
    
    # 【新增】取得使用者的偏好語言
    user_lang = user.preferred_lang if user else 'en' # 加上保護，以防 user 物件不存在

    # 【修改】在 URL 中附加上 lang 參數
    return f"line://app/{liff_id}?store_id={store.store_id}&store_name={encoded_store_name}&is_partner={is_partner}&lang={user_lang}"

# --- Webhook 主路由 ---
@app.post("/callback")
async def callback(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get('X-Line-Signature', '')
    body = await request.body()
    try:
        events = parser.parse(body.decode('utf-8'), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    background_tasks.add_task(handle_events, events=events)
    return 'OK'

# --- 事件處理總管 ---
async def handle_events(events: List):
    """
    為背景任務建立一個獨立的資料庫 session。
    """
    async with AsyncSessionLocal() as session:
        for event in events:
            if isinstance(event, FollowEvent):
                await handle_follow(event, session)
            elif isinstance(event, MessageEvent):
                if isinstance(event.message, TextMessageContent):
                    await handle_message(event, session)
                elif isinstance(event.message, AudioMessageContent):
                    await handle_audio_message(event, session)
                elif isinstance(event.message, LocationMessageContent):
                    await handle_location_message(event, session)
                elif isinstance(event.message, StickerMessageContent):
                    await handle_sticker_message(event, session)
            elif isinstance(event, PostbackEvent):
                await handle_postback(event, session)

# --- 【核心修改】事件處理器：處理使用者加入好友 ---
async def handle_follow(event: FollowEvent, db: AsyncSession):
    line_user_id = event.source.user_id
    logging.info(f"User {line_user_id} has followed our bot.")
    
    # 預設語言為英文，以防 API 呼叫失敗或沒有回傳語言
    user_language = 'en'

    # 呼叫 Get Profile API 來取得使用者語言
    try:
        async with AsyncApiClient(line_config) as api_client:
            line_bot_api = MessagingApi(api_client)
            profile = await line_bot_api.get_profile(line_user_id)
            
            if profile.language:
                user_language = profile.language
                logging.info(f"Detected user language from profile: {user_language}")

    except Exception as e:
        logging.error(f"Failed to get user profile for {line_user_id}: {e}")
        # 如果 API 呼叫失敗，我們會繼續使用預設的 'en'

    # 查詢使用者是否存在
    result = await db.execute(select(User).filter_by(line_user_id=line_user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        # 使用從 API 取得的語言 (或預設的 'en') 來建立新使用者
        user = User(
            line_user_id=line_user_id, 
            preferred_lang=user_language, 
            state='normal'
        )
        db.add(user)
        await db.commit()
        await db.refresh(user) # 取得剛寫入的 user 物件，確保後續 get_translated_text 能使用
        logging.info(f"New user {line_user_id} has been added with lang: {user_language}.")
    else:
        # 如果使用者已存在，也更新他的語言設定
        user.preferred_lang = user_language
        await db.commit()
        logging.info(f"Updated user {line_user_id}'s language to: {user_language}.")
    
    # 呼叫新的函式來取得訊息列表
    welcome_messages = await get_main_menu_messages(user)
    
    # 主動推送按鈕卡片訊息
    async with AsyncApiClient(line_config) as api_client:
        line_bot_api = MessagingApi(api_client)
        await line_bot_api.push_message(
            PushMessageRequest(to=line_user_id, messages=welcome_messages)
        )

# --- 【核心修改】修改 handle_message 以處理多訊息回覆 ---
async def handle_message(event: MessageEvent, db: AsyncSession):
    line_user_id = event.source.user_id
    user_text = event.message.text
    
    # process_language_text 現在會回傳一個訊息物件的列表
    reply_messages = await process_language_text(line_user_id, user_text, db)
    
    async with AsyncApiClient(line_config) as api_client:
        line_bot_api = MessagingApi(api_client)
        # 直接使用回傳的訊息物件列表
        await line_bot_api.reply_message(
            ReplyMessageRequest(reply_token=event.reply_token, messages=reply_messages)
        )

async def handle_audio_message(event: MessageEvent, db: AsyncSession):
    line_user_id = event.source.user_id
    result = await db.execute(select(User).filter_by(line_user_id=line_user_id))
    user = result.scalar_one_or_none()

    if not user:
        error_text = await get_translated_text(None, "user_not_found")
        reply_messages = [TextMessage(text=error_text)] # 確保是列表

    # --- 【核心修改】只有在等待語言輸入的狀態下，才處理語音 ---
    elif user.state == 'awaiting_language':
        message_id = event.message.id
        logging.info(f"Processing audio message from {line_user_id} in state 'awaiting_language'")

         # 1. 從 LANG_CODE_MAP 查找對應的 stt_lang_code
        primary_stt_code = "en-US" # 預設的主要辨識語言
        if user.preferred_lang:
            lang_map = LANG_CODE_MAP.get(user.preferred_lang)
            if lang_map and lang_map.get("stt"):
                primary_stt_code = lang_map["stt"]
        
        # 2. 準備您指定的備選語言列表
        alternative_codes = [
            'cmn-Hant-TW', 'cmn-Hans-CN', 'tr-TR', 'ja-JP', 'id-ID', 
            'es-ES', 'es-MX', 'fr-FR', 'ar-AE', 'ru-RU', 'en-US', 
            'th-TH', 'ms-MY', 'vi-VN', 'it-IT', 'pt-BR', 'pt-PT', 
            'de-DE', 'ko-KR'
        ]
        # 確保主要語言不會重複出現在備選列表中
        if primary_stt_code in alternative_codes:
            alternative_codes.remove(primary_stt_code)

        logging.info(f"Setting STT primary language to: {primary_stt_code}")

        reply_messages = []

        try:
            async with AsyncApiClient(line_config) as api_client:
                line_bot_blob_api = MessagingApiBlob(api_client)
                audio_content = await line_bot_blob_api.get_message_content(message_id=message_id)

            audio = speech.RecognitionAudio(content=audio_content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.MP3,
                sample_rate_hertz=16000,
                language_code=primary_stt_code, # 使用從資料庫查出的 stt code
                alternative_language_codes=alternative_codes # 使用您指定的備選列表
            )
            response = await asyncio.to_thread(speech_client.recognize, config=config, audio=audio)
            
            if response.results and response.results[0].alternatives:
                transcript = response.results[0].alternatives[0].transcript
                logging.info(f"Speech-to-Text transcript: {transcript}")
                reply_messages = await process_language_text(line_user_id, transcript, db)
            else:
                logging.warning("Speech-to-Text API returned no result.")
                error_text = await get_translated_text(user, "audio_not_recognized")
                messages_to_reply = [TextMessage(text=error_text)]
                # 附上語言列表
                if LANGUAGE_LIST_STRING:
                    messages_to_reply.append(TextMessage(text=LANGUAGE_LIST_STRING))
                reply_messages = messages_to_reply
        except Exception as e:
            logging.error(f"Error processing audio message: {e}")
            error_text = await get_translated_text(user, "audio_processing_error")
            reply_messages = [TextMessage(text=error_text)]
    
    else: # user.state is 'normal' or 'awaiting_location'
        logging.info(f"Received unexpected audio from user {line_user_id} in state '{user.state}'")
        reply_messages = await process_language_text(line_user_id, "", db)

    # 回覆訊息給使用者
    async with AsyncApiClient(line_config) as api_client:
        line_bot_api = MessagingApi(api_client)
        await line_bot_api.reply_message(
            ReplyMessageRequest(reply_token=event.reply_token, messages=reply_messages)
        )

# --- 處理貼圖訊息的事件處理器 ---
async def handle_sticker_message(event: MessageEvent, db: AsyncSession):
    line_user_id = event.source.user_id
    result = await db.execute(select(User).filter_by(line_user_id=line_user_id))
    user = result.scalar_one_or_none()

    if not user:
        error_text = await get_translated_text(None, "user_not_found")
        reply_messages = [TextMessage(text=error_text)] # 確保是列表

    logging.info(f"Received unexpected sticker from user {line_user_id} in state '{user.state}'")
    reply_messages = await process_language_text(line_user_id, "", db)

    async with AsyncApiClient(line_config) as api_client:
        line_bot_api = MessagingApi(api_client)
        await line_bot_api.reply_message(
            ReplyMessageRequest(reply_token=event.reply_token, messages=reply_messages)
        )

# --- 處理位置訊息的事件處理器 ---
async def handle_location_message(event: MessageEvent, db: AsyncSession):
    line_user_id = event.source.user_id
    
    result = await db.execute(select(User).filter_by(line_user_id=line_user_id))
    user = result.scalar_one_or_none()

    if not user:
        error_text = await get_translated_text(None, "user_not_found")
        reply_messages = [TextMessage(text=error_text)] # 確保是列表

    # 2. 只有在使用者處於 'awaiting_location' 狀態時才處理位置
    elif user.state == 'awaiting_location':

        # 將狀態改回正常
        user.state = 'normal'
        await db.commit()
        
        # 2. 取得位置訊息的所有資訊
        location_message = event.message
        user_lat = location_message.latitude
        user_lng = location_message.longitude
        title = location_message.title
        address = location_message.address
        
        final_places = []

        # --- 3. 【核心修改】採用混合 API 策略 ---
        
        # 步驟 B (探索): 先執行 Nearby Search 取得背景列表
        logging.info(f"Executing Nearby Search for user {line_user_id}...")
        nearby_search_url = "https://places.googleapis.com/v1/places:searchNearby"
        nearby_headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": Config.MAPS_API_KEY,
            "X-Goog-FieldMask": "places.displayName,places.id,places.photos,places.location"
        }
        nearby_payload = {
            "includedPrimaryTypes": ["restaurant"],
            "maxResultCount": 10,
            "locationRestriction": {
                "circle": {"center": { "latitude": user_lat, "longitude": user_lng }, "radius": 200.0}
            },
            "rankPreference": "POPULARITY",
            "languageCode": "zh-TW"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(nearby_search_url, headers=nearby_headers, json=nearby_payload) as response:
                    response.raise_for_status()
                    nearby_result = await response.json()
                    final_places = nearby_result.get("places", [])
        except Exception as e:
            logging.error(f"Google Nearby Search API error: {e}")
            # 如果 Nearby Search 失敗，至少也要嘗試 Text Search
            pass

        if title and address:
            # 情境一：使用者分享的是「地標」，執行步驟 A (驗證)
            logging.info(f"Executing Text Search for landmark: '{title}'")
            text_search_url = "https://places.googleapis.com/v1/places:searchText"
            text_headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": Config.MAPS_API_KEY,
                "X-Goog-FieldMask": "places.id,places.displayName,places.photos,places.types,places.location"
            }
            text_payload = {
                "textQuery": f"{title} {address}",
                "maxResultCount": 1,
                "locationBias": {
                    "circle": {"center": { "latitude": user_lat, "longitude": user_lng }, "radius": 50.0} # 縮小偏差半徑以求精準
                },
                "languageCode": "zh-TW"
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(text_search_url, headers=text_headers, json=text_payload) as response:
                        response.raise_for_status()
                        text_result = await response.json()
                        landmark_place = text_result.get("places", [None])[0]
                        
                        # 步驟 C (組合): 如果驗證的地標是餐廳，就把它放到列表最前面
                        if landmark_place and "restaurant" in landmark_place.get('types', []):
                            logging.info(f"Landmark is a restaurant, prepending to the list.")
                            # 移除 Nearby Search 結果中可能重複的地標
                            final_places = [p for p in final_places if p.get('id') != landmark_place.get('id')]
                            # 將地標插入到最前面
                            final_places.insert(0, landmark_place)
            except Exception as e:
                logging.error(f"Google Text Search API error: {e}")
                # Text Search 失敗不影響 Nearby Search 的結果

        if not final_places:
            not_found_text = await get_translated_text(user, "no_stores_found")
            async with AsyncApiClient(line_config) as api_client:
                line_bot_api = MessagingApi(api_client)
                await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=not_found_text)]))
            return

        # 處理搜尋結果並建立輪播卡片
        carousel_columns = []

        for place in final_places[:10]:
            place_id = place.get('id')
            
            # 步驟 A：用 place_id 檢查店家是否已在我們的資料庫中
            store_result = await db.execute(select(Store).filter_by(place_id=place_id))
            store_in_db = store_result.scalar_one_or_none()

            # 步驟 B：如果店家不在資料庫中，就新增它
            if not store_in_db:
                logging.info(f"Store with place_id {place_id} not found in DB. Creating new entry.")
                
                # 從 Google API 的回傳中組合新店家的資料
                new_store_name = place.get('displayName', {}).get('text', 'N/A')
                new_photo_url = "https://via.placeholder.com/1024x1024.png?text=No+Image"
                if place.get('photos'):
                    photo_name = place['photos'][0]['name']
                    new_photo_url = f"https://places.googleapis.com/v1/{photo_name}/media?maxHeightPx=1024&key={Config.MAPS_API_KEY}"

                new_store = Store(
                    store_name=new_store_name,
                    partner_level=0, # 預設為 0 (非合作店家)
                    gps_lat=place.get('location', {}).get('latitude'),
                    gps_lng=place.get('location', {}).get('longitude'),
                    place_id=place_id,
                    main_photo_url=new_photo_url
                    # created_at 和 store_id 會由資料庫自動產生
                )
                db.add(new_store)
                await db.commit()
                # 【重要】新增後，重新整理物件以取得自動增長的 store_id
                await db.refresh(new_store)
                # 將剛新增的物件賦值給 store_in_db，以便後續使用
                store_in_db = new_store
                logging.info(f"Successfully added new store: {new_store_name}")

            # 【修正】傳入 user 和 store_in_db 兩個物件
            liff_full_url = create_liff_url(user, store_in_db)

            # 步驟 C：建立輪播卡片 (現在 store_in_db 必定有值)
            # 確保店名非空，並先存成原始店名
            original_store_name = store_in_db.store_name if store_in_db else "店家名稱不詳"
            
            # --- 【修改處】呼叫新的翻譯函式來翻譯店名 ---
            #translated_store_name = await translate_arbitrary_text(user, original_store_name, source_lang='zh-TW')
            
            # 確保照片 URL 永遠有有效的 URL
            card_photo_url = store_in_db.main_photo_url if store_in_db and store_in_db.main_photo_url else "https://via.placeholder.com/1024x1024.png?text=No+Image"
            
            # --- 【修改處】組合包含 partner_level 的狀態文字 ---
            partner_level = store_in_db.partner_level if store_in_db else 0
            
            # 組合出對應的樣板鍵，例如 "partner_level_0", "partner_level_1"
            status_template_key = f"partner_level_{partner_level}"
            
            # 使用 get_translated_text 進行翻譯
            translated_status = await get_translated_text(user, status_template_key)
            
            final_card_text = f"{translated_status}"

            # --- 【新增邏輯】翻譯按鈕標籤 ---
            translated_action_label = await get_translated_text(user, "start_ordering")

            # 步驟 C：建立輪播卡片
            column = CarouselColumn(
                thumbnail_image_url=card_photo_url,
                title=original_store_name[:40], # 標題最多40字元
                text=final_card_text[:60], # 內文最多60字元
                actions=[
                    URIAction(
                        label=translated_action_label[:20], # <-- 使用翻譯後的文字 (標籤上限20字元)
                        uri=liff_full_url # <-- 使用我們新組合的、包含所有參數的網址
                    )
                ]
            )
            carousel_columns.append(column)

        # 如果處理完後，有效的卡片數量為 0，則回覆找不到
        if not carousel_columns:
            not_found_text = await get_translated_text(user, "no_stores_found")
            async with AsyncApiClient(line_config) as api_client:
                line_bot_api = MessagingApi(api_client)
                await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=not_found_text)]))
            return

        # --- 回傳輪播卡片訊息 ---
        carousel_template = TemplateMessage(
            alt_text='附近的店家列表',
            template=CarouselTemplate(columns=carousel_columns)
        )

        # 【修正】呼叫函式以取得主選單訊息
        #main_menu_messages = await get_main_menu_messages(user)

        # 【修正】將店家輪播卡片和主選單合併到一個列表中回傳
        messages_to_reply = [carousel_template]
        #messages_to_reply = [carousel_template] + main_menu_messages
        
        async with AsyncApiClient(line_config) as api_client:
            line_bot_api = MessagingApi(api_client)
            await line_bot_api.reply_message(
                ReplyMessageRequest(reply_token=event.reply_token, messages=messages_to_reply)
            )

    # --- 如果使用者在其他狀態傳送位置 ---
    else:
        logging.info(f"Received unexpected location from user {line_user_id} in state '{user.state}'")
        
        # 呼叫共用的文字處理邏輯，讓它根據當前狀態回覆對應的提示
        # 我們傳入一個不會被識別的文字 (例如空字串)，來觸發預設的回應
        reply_messages = await process_language_text(line_user_id, "", db)
        
        async with AsyncApiClient(line_config) as api_client:
            line_bot_api = MessagingApi(api_client)
            await line_bot_api.reply_message(
                ReplyMessageRequest(reply_token=event.reply_token, messages=reply_messages)
            )

# --- 【核心修改】建立並回傳歷史訂單輪播卡片 (功能升級版) ---
async def handle_order_history(user: User, db: AsyncSession) -> List:
    """
    查詢使用者最新的 10 筆訂單，並將其格式化為 LINE 輪播卡片。
    每張卡片有兩個按鈕：
    1. 再次訂購 (LIFF)
    2. 查看訂單詳情 (Postback)
    """
    order_stmt = (
        select(Order)
        .options(joinedload(Order.store))
        .where(Order.user_id == user.user_id)
        .order_by(desc(Order.order_time))
        .limit(10)
    )
    orders_result = await db.execute(order_stmt)
    latest_orders = orders_result.scalars().all()

    if not latest_orders:
        no_history_text = await get_translated_text(user, "no_order_history")
        return [TextMessage(text=no_history_text)]

    carousel_columns = []
    
    # --- 平行翻譯按鈕標籤 ---
    # 透過 asyncio.gather 可以同時執行多個 awaitable，節省等待時間
    translated_labels = await asyncio.gather(
        get_translated_text(user, "view_order_details"),
        get_translated_text(user, "order_again")
    )

    view_details_label = translated_labels[0]
    order_again_label = translated_labels[1]

    for order in latest_orders:
        store = order.store
        store_name = store.store_name if store else "店家資訊遺失"
        
        # 卡片文字不變，只顯示摘要資訊
        card_text = (
            f"📅 {order.order_time.strftime('%Y-%m-%d %H:%M')}\n"
            f"💰 ${order.total_amount}"
        )
        
        actions = []

        translated_display_text = await get_translated_text(
            user, 
            "querying_order_details", 
            store_name=store_name
        )

        # --- 按鈕一：查看訂單詳情 (Postback) ---
        # data 格式設計為 'action=show_order_details&order_id=...'
        # 這樣未來若有其他 postback 動作，可以輕易擴充
        postback_data = f"action=show_order_details&order_id={order.order_id}"
        actions.append(PostbackAction(
            label=view_details_label,
            data=postback_data,
            # 使用翻譯後的文字
            displayText=translated_display_text
        ))

        # --- 按鈕二：再次訂購 (LIFF) ---
        if store and store.store_id and store.store_name:
            # 【修正】傳入 user 和 store 兩個物件
            liff_full_url = create_liff_url(user, store)
            actions.append(URIAction(label=order_again_label, uri=liff_full_url))

        # 建立輪播卡片欄位
        column = CarouselColumn(
            title=store_name[:40],
            text=card_text[:60], # 內文維持簡潔
            actions=actions # 將兩個按鈕都放進去
        )
        carousel_columns.append(column)

    carousel_template = TemplateMessage(
        alt_text='您的歷史訂單',
        template=CarouselTemplate(columns=carousel_columns)
    )
    
    # 【修正】呼叫函式以取得主選單訊息
    #main_menu_messages = await get_main_menu_messages(user)

    # 【修正】將歷史訂單輪播卡片和主選單合併到一個列表中回傳
    return [carousel_template]
    #return [carousel_template] + main_menu_messages

# --- 【修改處】擴充 Postback 事件處理器 ---
async def handle_postback(event: PostbackEvent, db: AsyncSession):
    line_user_id = event.source.user_id
    # postback.data 的內容是我們在建立按鈕時自己定義的
    postback_data = event.postback.data
    
    user_result = await db.execute(select(User).filter_by(line_user_id=line_user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        error_text = await get_translated_text(None, "user_not_found")
        reply_messages = [TextMessage(text=error_text)]
        # 如果找不到使用者，後續邏輯無法執行，直接回覆並返回
        async with AsyncApiClient(line_config) as api_client:
            line_bot_api = MessagingApi(api_client)
            await line_bot_api.reply_message(
                ReplyMessageRequest(reply_token=event.reply_token, messages=reply_messages)
            )
        return

    # --- 新增的判斷邏輯：處理主選單按鈕 ---
    if postback_data == "action=change_language":
        # 模擬使用者輸入 'change language'
        reply_messages = await process_language_text(line_user_id, 'change language', db)
    
    elif postback_data == "action=order_now":
        # 模擬使用者輸入 'order now'
        reply_messages = await process_language_text(line_user_id, 'order now', db)

    elif postback_data == "action=order_history":
        # 模擬使用者輸入 'order history'
        reply_messages = await process_language_text(line_user_id, 'order history', db)

    # --- 原有的判斷邏輯：處理訂單詳情 ---
    elif postback_data.startswith("action=show_order_details"):
        parsed_data = parse_qs(postback_data)
        order_id = parsed_data.get('order_id', [None])[0]
        if not order_id:
            error_text = await get_translated_text(user, "generic_error")
            reply_messages = [TextMessage(text=error_text)]
        else:
            stmt = (
                select(Order)
                .where(Order.order_id == int(order_id))
                .options(joinedload(Order.store), joinedload(Order.items))
            )
            result = await db.execute(stmt)
            order = result.unique().scalar_one_or_none()
            if not order:
                error_text = await get_translated_text(user, "generic_error")
                reply_messages = [TextMessage(text=error_text)]
            else:
                trans_texts = await asyncio.gather(
                    get_translated_text(user, "order_details_title"),
                    get_translated_text(user, "order_details_store"),
                    get_translated_text(user, "order_details_time"),
                    get_translated_text(user, "order_details_total"),
                    get_translated_text(user, "order_details_items_header")
                )
                title, store_label, time_label, total_label, items_header = trans_texts
                store_name = order.store.store_name if order.store else "N/A"
                details_parts = [
                    f"<{title}>", "--------------------",
                    f"{store_label}: {store_name}",
                    f"{time_label}: {order.order_time.strftime('%Y-%m-%d %H:%M')}",
                    f"{total_label}: ${order.total_amount}",
                    "\n" + f"{items_header}:"
                ]
                if order.items:
                    for item in order.items:
                        item_name = item.translated_name or item.original_name
                        details_parts.append(f"- {item_name} x {item.quantity_small}  (${item.subtotal})")
                reply_text = "\n".join(details_parts)
                reply_messages = [TextMessage(text=reply_text)]

    # --- 如果收到無法識別的 postback data ---
    else:
        error_text = await get_translated_text(user, "generic_error")
        reply_messages = [TextMessage(text=error_text)]

    # --- 統一回覆訊息給使用者 ---
    async with AsyncApiClient(line_config) as api_client:
        line_bot_api = MessagingApi(api_client)
        await line_bot_api.reply_message(
            ReplyMessageRequest(reply_token=event.reply_token, messages=reply_messages)
        )

# --- 共用的文字處理邏輯 ---
async def process_language_text(line_user_id: str, text: str, db: AsyncSession) -> List[TextMessage]:
    user_text = text.strip().lower()
    
    result = await db.execute(select(User).filter_by(line_user_id=line_user_id))
    user = result.scalar_one_or_none()

    if not user:
        error_text = await get_translated_text(None, "user_not_found")
        return [TextMessage(text=error_text)]

    # 只有當使用者處於特定等待狀態時，取消指令才生效
    if user_text == '0' and user.state in ['awaiting_location', 'awaiting_language']:
        previous_state = user.state # 記錄一下是從哪個狀態取消的
        user.state = 'normal'  # 將狀態重設為正常
        await db.commit()
        # 使用回覆樣板來通知使用者操作已取消
        cancelled_text = await get_translated_text(user, "operation_cancelled")
        logging.info(f"User {line_user_id} cancelled the operation from state '{previous_state}'.")
        # 【修正】呼叫函式以取得主選單訊息
        main_menu_messages = await get_main_menu_messages(user)
        # 【修正】將取消訊息和主選單合併回傳
        return [TextMessage(text=cancelled_text)] + main_menu_messages

    # --- 狀態一：等待位置 ---
    if user.state == 'awaiting_location':
        # 使用新的回覆樣板 "reprompt_location"
        reprompt_text = await get_translated_text(user, "reprompt_location")
        return [TextMessage(
            text=reprompt_text,
            quick_reply=QuickReply(items=[
                QuickReplyItem(action=LocationAction(label="分享我的位置"))
            ])
        )]

    # 狀態二：等待語言輸入
    elif user.state == 'awaiting_language':
        lang_code = language_lookup_dict.get(user_text)
        if lang_code:
            user.preferred_lang = lang_code
            user.state = 'normal'
            
            result = await db.execute(select(Language).filter_by(line_lang_code=lang_code))
            language = result.scalar_one_or_none()
            canonical_lang_name = language.lang_name if language else lang_code
            
            localized_lang_name = await localize_lang_name(canonical_lang_name, user.preferred_lang)

            await db.commit()
            
            success_text = await get_translated_text(user, "language_set_success", lang_name=localized_lang_name)
            # 【修正】呼叫函式以取得主選單訊息
            #main_menu_messages = await get_main_menu_messages(user)
            # 【修正】將成功訊息和主選單合併回傳
            return [TextMessage(text=success_text)]
            #return [TextMessage(text=success_text)] + main_menu_messages
        else:
            # 準備第一則訊息：無法識別的錯誤提示
            not_recognized_text = await get_translated_text(user, "language_not_recognized")
            messages_to_reply = [TextMessage(text=not_recognized_text)]

            # 準備第二則訊息：再次附上語言列表
            # 我們使用之前建立的全域變數 LANGUAGE_LIST_STRING
            if LANGUAGE_LIST_STRING:
                messages_to_reply.append(TextMessage(text=LANGUAGE_LIST_STRING))
            
            return messages_to_reply
            
    # 狀態三：正常
    else: # user.state == 'normal'
        if user_text == 'order now':
            user.state = 'awaiting_location'
            await db.commit()
            
            ask_location_text = await get_translated_text(user, "ask_location")
            return [TextMessage(
                text=ask_location_text,
                quick_reply=QuickReply(items=[
                    QuickReplyItem(action=LocationAction(label="分享我的位置"))
                ])
            )]
        
        elif user_text == 'change language':
            user.state = 'awaiting_language'
            await db.commit()
            
            ask_language_text = await get_translated_text(user, "ask_language")
            messages_to_reply = [TextMessage(text=ask_language_text)]

            # 如果我們成功讀取並格式化了語言列表，就將它作為第二則訊息加入
            if LANGUAGE_LIST_STRING:
                messages_to_reply.append(TextMessage(text=LANGUAGE_LIST_STRING))

            return messages_to_reply
        
        elif user_text == 'order history':
            # 我們將在這裡呼叫一個新的函式來處理複雜的查詢與卡片生成邏輯
            # 這樣可以讓 process_language_text 保持簡潔
            return await handle_order_history(user, db)
        
        # --- 【修改處】當沒有任何指令匹配時，回覆主選單按鈕 ---
        else:
            # 回傳訊息列表
            return await get_main_menu_messages(user)
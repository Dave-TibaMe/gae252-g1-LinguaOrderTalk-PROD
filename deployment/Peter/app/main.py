import os
import json
import asyncio
import logging
from typing import List
from urllib.parse import parse_qsl
import aiohttp # <-- 匯入 aiohttp

from fastapi import FastAPI, Request, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 匯入 LINE Bot 元件
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    AsyncApiClient, Configuration,
    AsyncMessagingApi as MessagingApi,
    AsyncMessagingApiBlob as MessagingApiBlob,
    TextMessage, PushMessageRequest, ReplyMessageRequest,
    TemplateMessage, CarouselTemplate, CarouselColumn, URIAction,
    QuickReply, QuickReplyItem, LocationAction
)
from linebot.v3.webhooks import (
    MessageEvent, TextMessageContent, AudioMessageContent, FollowEvent,
    LocationMessageContent, PostbackEvent,
    StickerMessageContent # <-- 匯入貼圖訊息元件
)

# 匯入 Google 服務和本地模組
from google.cloud import translate_v2 as translate
from google.cloud import speech

# --- 在這裡加入 AsyncSessionLocal 的匯入 ---
from app.config import Config
from app.database import get_db, AsyncSessionLocal
from app.models import User, Language, Store

# --- 初始化應用程式與服務 ---
logging.basicConfig(level=logging.INFO)
app = FastAPI(title="LinguaOrderTalk Bot Service")

line_config = Configuration(access_token=Config.CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(Config.CHANNEL_SECRET)

translate_client = translate.Client()
speech_client = speech.SpeechClient()

# --- 載入語言對照表 ---
language_lookup_dict = {}
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

# --- 回覆訊息樣板 ---
REPLY_TEMPLATES = {
    "welcome": 'Welcome! Please click "Change Language" in the menu to set your language.\n歡迎！請點擊圖文選單中的 "Change Language" 來設定您的語言。',
    "ask_language": '請直接說出或輸入您想設定的語言。',
    "language_set_success": "語言已成功設定為: {lang_name}。",
    "language_not_recognized": "對不起，無法識別您輸入的語言，請再試一次。",
    "user_not_found": "錯誤：找不到您的使用者資料，請嘗試重新加入好友。",
    "prompt_change_language": "您好，請點擊圖文選單，Change Language 來設定語言，Order Now 來點餐。",
    "audio_processing_error": "處理錄音時發生錯誤，請稍後再試。",
    "audio_not_recognized": "對不起，我聽不清楚您說的內容，請再試一次。",
    "ask_location": "請分享您目前的位置，為您尋找附近的店家。",
    "no_stores_found": "對不起，您附近找不到任何店家。",
    "reprompt_location": "請點擊下方的按鈕來分享您的位置。"
}
PARTNER_LEVEL_TEXT = {
    0: "非合作店家",
    1: "合作店家",
    2: "VIP店家"
}

# --- 翻譯輔助函式 (異步) ---
async def get_translated_text(user: User, template_key: str, **kwargs) -> str:
    """
    根據使用者偏好語言，取得翻譯後的文字，並處理換行。
    """
    default_text = REPLY_TEMPLATES.get(template_key, "Message template undefined.")
    
    # 如果找不到使用者或其偏好語言，直接處理換行後回傳
    if not user or not user.preferred_lang:
        return default_text.format(**kwargs)
        
    try:
        # 呼叫翻譯 API
        result = await asyncio.to_thread(
            translate_client.translate,
            default_text,
            target_language=user.preferred_lang
        )
        translated_text = result['translatedText']

        return translated_text.format(**kwargs)
        
    except Exception as e:
        logging.error(f"Translation failed for {user.preferred_lang}: {e}")
        # 若翻譯失敗，安全地退回到預設文字
        return default_text.format(**kwargs)

async def localize_lang_name(canonical_name: str, target_lang: str) -> str:
    if target_lang != 'zh-TW': # 假設標準名稱都是中文
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
    # --- 在這裡為背景任務建立一個新的 session ---
    async with AsyncSessionLocal() as session:
        for event in events:
            if isinstance(event, FollowEvent):
                await handle_follow(event, session) # 將新的 session 傳下去
            elif isinstance(event, MessageEvent):
                if isinstance(event.message, TextMessageContent):
                    await handle_message(event, session) # 將新的 session 傳下去
                elif isinstance(event.message, AudioMessageContent):
                    await handle_audio_message(event, session)
                elif isinstance(event.message, LocationMessageContent):
                    await handle_location_message(event, session)
                elif isinstance(event.message, StickerMessageContent):
                    await handle_sticker_message(event, session)
            elif isinstance(event, PostbackEvent):
                await handle_postback(event, session)

# --- 事件處理器：處理使用者加入好友 ---
async def handle_follow(event: FollowEvent, db: AsyncSession):
    line_user_id = event.source.user_id
    logging.info(f"User {line_user_id} has followed our bot.")
    
    result = await db.execute(select(User).filter_by(line_user_id=line_user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(line_user_id=line_user_id, preferred_lang='en', state='normal')
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logging.info(f"New user {line_user_id} has been added.")
    
    # --- 直接從樣板字典取用文字，不進行翻譯 ---
    welcome_text = REPLY_TEMPLATES.get("welcome")
    
    async with AsyncApiClient(line_config) as api_client:
        line_bot_api = MessagingApi(api_client)
        await line_bot_api.push_message(
            PushMessageRequest(to=line_user_id, messages=[TextMessage(text=welcome_text)])
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
        try:
            async with AsyncApiClient(line_config) as api_client:
                line_bot_blob_api = MessagingApiBlob(api_client)
                audio_content = await line_bot_blob_api.get_message_content(message_id=message_id)

            primary_lang_code = user.preferred_lang if user.preferred_lang else "en-US"
            alternative_codes = ["en-US", "zh-TW", "ja-JP", "ko-KR"]
            if primary_lang_code in alternative_codes:
                alternative_codes.remove(primary_lang_code)

            audio = speech.RecognitionAudio(content=audio_content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.MP3,
                sample_rate_hertz=16000,
                language_code=primary_lang_code,
                alternative_language_codes=alternative_codes
            )
            response = await asyncio.to_thread(speech_client.recognize, config=config, audio=audio)
            
            if response.results and response.results[0].alternatives:
                transcript = response.results[0].alternatives[0].transcript
                logging.info(f"Speech-to-Text transcript: {transcript}")
                reply_messages = await process_language_text(line_user_id, transcript, db)
            else:
                logging.warning("Speech-to-Text API returned no result.")
                error_text = await get_translated_text(user, "audio_not_recognized")
                reply_messages = [TextMessage(text=error_text)] # 確保是列表
        except Exception as e:
            logging.error(f"Error processing audio message: {e}")
            error_text = await get_translated_text(user, "audio_processing_error")
            reply_messages = [TextMessage(text=error_text)] # 確保是列表
    
    # 如果在其他狀態收到錄音，則回覆對應的提示
    else:
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
        
        user_lat = event.message.latitude
        user_lng = event.message.longitude
        
        logging.info(f"Searching nearby places for user {line_user_id} at ({user_lat}, {user_lng})")
        
        # --- 改用 aiohttp 直接呼叫 Places API (New) ---
        places_api_url = "https://places.googleapis.com/v1/places:searchNearby"
        
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": Config.Maps_API_KEY,
            # 欄位遮罩，只請求我們需要的欄位以節省費用
            "X-Goog-FieldMask": "places.displayName,places.id,places.photos"
        }
        
        payload = {
            "includedTypes": ["restaurant"],
            "maxResultCount": 10,
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": user_lat,
                        "longitude": user_lng
                    },
                    "radius": 500.0
                }
            },
            "languageCode": user.preferred_lang if user else 'en'
        }

        places = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(places_api_url, headers=headers, json=payload) as response:
                    response.raise_for_status() # 如果 API 回傳錯誤 (如 4xx, 5xx)，會在此拋出例外
                    places_result = await response.json()
                    places = places_result.get("places", [])
        except Exception as e:
            logging.error(f"Google Maps API (New) error: {e}")
            error_text = await get_translated_text(user, "api_error_message") # 可以在樣板中新增此項
            async with AsyncApiClient(line_config) as api_client:
                line_bot_api = MessagingApi(api_client)
                await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=error_text)]))
            return

        if not places:
            not_found_text = await get_translated_text(user, "no_stores_found")
            async with AsyncApiClient(line_config) as api_client:
                line_bot_api = MessagingApi(api_client)
                await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=not_found_text)]))
            return

        # 處理搜尋結果並建立輪播卡片
        carousel_columns = []

        for place in places:
            place_id = place.get('id')
            store_name = place.get('displayName', {}).get('text', 'N/A')
            
            store_result = await db.execute(select(Store).filter_by(place_id=place_id))
            store_in_db = store_result.scalar_one_or_none()

            photo_url = "https://via.placeholder.com/1024x1024.png?text=No+Image" # 預設圖片
            partner_level = 0

            if store_in_db and store_in_db.main_photo_url:
                partner_level = store_in_db.partner_level
                photo_url = store_in_db.main_photo_url
            elif place.get('photos'):
                photo_name = place['photos'][0]['name']
                # 新版 API 的照片 URL 取得方式
                photo_url = f"https://places.googleapis.com/v1/{photo_name}/media?maxHeightPx=1024&key={Config.Maps_API_KEY}"
            
            status_text_default = PARTNER_LEVEL_TEXT.get(partner_level, "非合作店家")
            translated_status = await get_translated_text(user, status_text_default, lang_name=status_text_default)

            # 4. 建立卡片，並將 action 設為不含參數的 URIAction
            column = CarouselColumn(
                thumbnail_image_url=photo_url,
                title=store_name[:40],
                text=translated_status[:60],
                actions=[
                    URIAction(
                        label='開始點餐',
                        uri=f"line://app/{Config.LIFF_ID}?storeId={store_in_db.store_id if store_in_db else place_id}&isPartner={'true' if store_in_db else 'false'}"
                    )
                ]
            )
            carousel_columns.append(column)

        carousel_template = TemplateMessage(alt_text='附近的店家列表', template=CarouselTemplate(columns=carousel_columns))
        
        async with AsyncApiClient(line_config) as api_client:
            line_bot_api = MessagingApi(api_client)
            await line_bot_api.reply_message(
                ReplyMessageRequest(reply_token=event.reply_token, messages=[carousel_template])
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

# --- 處理來自輪播卡片的 Postback 事件 ---
async def handle_postback(event: PostbackEvent, db: AsyncSession):
    line_user_id = event.source.user_id
    # 解析 postback.data 中的資料
    # 例如: 'action=select_store&place_id=ChIJ...&store_name=麥當勞'
    postback_data = dict(parse_qsl(event.postback.data))
    action = postback_data.get('action')

    # 查詢使用者物件
    result = await db.execute(select(User).filter_by(line_user_id=line_user_id))
    user = result.scalar_one_or_none()

    reply_message = None

    if action == 'select_store':
        place_id = postback_data.get('place_id')
        store_name = postback_data.get('store_name')
        logging.info(f"User {line_user_id} selected store: {store_name} ({place_id})")

        # TODO: 在這裡接續點餐的下一步流程
        # 例如：查詢這家店的菜單並顯示
        
        reply_text = await get_translated_text(user, "store_selected", store_name=store_name)
        # 可以在 REPLY_TEMPLATES 新增 "store_selected": "You have selected: {store_name}. What's next?"
        
        # 暫時先回覆一個確認訊息
        reply_message = TextMessage(text=f"您選擇了: {store_name}")

    if reply_message:
        async with AsyncApiClient(line_config) as api_client:
            line_bot_api = MessagingApi(api_client)
            await line_bot_api.reply_message(
                ReplyMessageRequest(reply_token=event.reply_token, messages=[reply_message])
            )

# --- 共用的文字處理邏輯 ---
async def process_language_text(line_user_id: str, text: str, db: AsyncSession) -> List[TextMessage]:
    user_text = text.strip().lower()
    
    result = await db.execute(select(User).filter_by(line_user_id=line_user_id))
    user = result.scalar_one_or_none()

    if not user:
        error_text = await get_translated_text(None, "user_not_found")
        return [TextMessage(text=error_text)]

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
            
            result = await db.execute(select(Language).filter_by(lang_code=lang_code))
            language = result.scalar_one_or_none()
            canonical_lang_name = language.lang_name if language else lang_code
            
            localized_lang_name = await localize_lang_name(canonical_lang_name, user.preferred_lang)

            await db.commit()
            
            success_text = await get_translated_text(user, "language_set_success", lang_name=localized_lang_name)
            return [TextMessage(text=success_text)]
        else:
            not_recognized_text = await get_translated_text(user, "language_not_recognized")
            return [TextMessage(text=not_recognized_text)]
            
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
            return [TextMessage(text=ask_language_text)]
        
        else:
            prompt_text = await get_translated_text(user, "prompt_change_language")
            return [TextMessage(text=prompt_text)]
# =============================================================================
# 檔案名稱：app/webhook/routes.py
# 功能描述：處理 LINE Bot 的 Webhook 請求，實現 LINE Bot 的核心功能
# 主要職責：
# - 處理 LINE 平台發送的訊息事件
# - 管理使用者語言設定
# - 處理店家查詢請求
# - 處理訂單記錄查詢
# - 發送語音訂單訊息
# - 處理餐飲需求推薦
# 支援功能：
# - 多語言歡迎訊息
# - 位置分享處理
# - 訂單狀態查詢
# - 語音訊息推送
# - AI 店家推薦
# =============================================================================

from flask import request, abort, Blueprint, jsonify
from ..models import db, User, Store, Order, VoiceFile
import os
import json
import threading
import logging
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, 
    ImageMessage, LocationMessage, FlexSendMessage,
    AudioSendMessage, QuickReply, QuickReplyButton,
    MessageAction, FollowEvent, CarouselContainer,
    CarouselColumn, ImageCarouselColumn, ImageCarouselTemplate,
    URIAction, PostbackAction, PostbackEvent
)
# 移除舊版導入，使用新版

webhook_bp = Blueprint('webhook', __name__)

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# LINE Bot 設定（延遲初始化）
def get_line_bot_api():
    """取得 LINE Bot API 實例"""
    try:
        channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
        if not channel_access_token:
            logger.warning("LINE_CHANNEL_ACCESS_TOKEN 環境變數未設定")
            return None
        return LineBotApi(channel_access_token)
    except Exception as e:
        logger.error(f"LINE Bot API 初始化失敗: {e}")
        return None

def get_line_bot_handler():
    """取得 LINE Bot Webhook Handler 實例"""
    try:
        channel_secret = os.getenv('LINE_CHANNEL_SECRET')
        if not channel_secret:
            print("警告: LINE_CHANNEL_SECRET 環境變數未設定")
            return None
        return WebhookHandler(channel_secret)
    except Exception as e:
        print(f"LINE Bot Handler 初始化失敗: {e}")
        return None

# =============================================================================
# 背景任務處理函數
# 解決容器重啟中斷語音處理的問題
# =============================================================================

def process_voice_order_background(order_id, user_id):
    """
    背景處理語音訂單生成和推送
    避免 webhook 超時和容器重啟中斷
    """
    try:
        logger.info(f"🎵 開始背景處理語音訂單: {order_id}")
        
        # 1. 生成語音檔案
        from ..api.helpers import generate_voice_order
        voice_file_path = generate_voice_order(order_id)
        
        if voice_file_path and os.path.exists(voice_file_path):
            logger.info(f"✅ 語音檔案生成成功: {voice_file_path}")
            
            # 2. 構建語音檔 URL
            fname = os.path.basename(voice_file_path)
            base_url = os.getenv('BASE_URL', 'https://ordering-helper-backend-1095766716155.asia-east1.run.app')
            audio_url = f"{base_url}/api/voices/{fname}"
            
            # 3. 發送語音訊息到 LINE
            line_bot_api = get_line_bot_api()
            if line_bot_api:
                try:
                    line_bot_api.push_message(
                        user_id,
                        AudioSendMessage(
                            original_content_url=audio_url,
                            duration=30000  # 30秒
                        )
                    )
                    logger.info(f"✅ 語音訊息推送成功: user={user_id}, audio_url={audio_url}")
                except LineBotApiError as e:
                    logger.exception(f"❌ LINE 語音推送失敗: status={getattr(e, 'status_code', None)}, error={getattr(e, 'error', None)}")
                except Exception as e:
                    logger.exception(f"❌ 語音推送異常: {e}")
            else:
                logger.error("❌ LINE Bot API 不可用")
        else:
            logger.warning(f"⚠️ 語音檔案生成失敗: {order_id}")
            
    except Exception as e:
        logger.exception(f"❌ 背景語音處理失敗: order_id={order_id}, error={e}")

def send_processing_message(event, user_language='zh'):
    """
    立即發送處理中訊息，避免 webhook 超時
    """
    try:
        processing_messages = {
            "en": "🔄 Processing your order... Please wait a moment.",
            "ja": "🔄 注文を処理中です... しばらくお待ちください。",
            "ko": "🔄 주문을 처리 중입니다... 잠시만 기다려 주세요.",
            "zh": "🔄 正在處理您的訂單... 請稍候片刻。"
        }
        
        message = processing_messages.get(user_language, processing_messages["zh"])
        
        line_bot_api = get_line_bot_api()
        if line_bot_api:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=message)
            )
            logger.info(f"✅ 處理中訊息已發送: user_lang={user_language}")
            return True
        else:
            logger.error("❌ LINE Bot API 不可用，無法發送處理中訊息")
            return False
            
    except Exception as e:
        logger.exception(f"❌ 發送處理中訊息失敗: {e}")
        return False

# Gemini API 設定（延遲初始化）
def get_gemini_model():
    """取得 Gemini 模型實例"""
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("警告: GEMINI_API_KEY 環境變數未設定")
            return None
        from google import genai
        genai.Client(api_key=api_key)
        return genai.Client().models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=["測試訊息"],
            config={
                "thinking_config": genai.types.ThinkingConfig(thinking_budget=512)
            }
        )
    except Exception as e:
        print(f"Gemini API 初始化失敗: {e}")
        return None

@webhook_bp.route("/callback", methods=['POST'])
def callback():
    """LINE Bot Webhook 處理器"""
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler = get_line_bot_handler()
        if handler:
            # 註冊事件處理器
            register_event_handlers()
            # 處理 webhook
            handler.handle(body, signature)
        else:
            print("LINE Bot Handler 未初始化")
            abort(500)
    except InvalidSignatureError:
        abort(400)
    
    return 'OK'

def handle_follow(event):
    """處理新使用者加入好友"""
    user_id = event.source.user_id
    
    try:
        # 檢查使用者是否已存在
        user = User.query.filter_by(line_user_id=user_id).first()
        
        if not user:
            # 建立新使用者記錄（預設語言為中文）
            new_user = User(
                line_user_id=user_id,
                preferred_lang='zh'  # 預設中文
            )
            db.session.add(new_user)
            db.session.commit()
            print(f"✅ 新使用者已註冊：{user_id}")
        
        # 發送語言選擇訊息
        handle_new_user(event)
        
    except Exception as e:
        print(f"❌ 處理新使用者加入失敗：{e}")
        # 即使註冊失敗，也要發送語言選擇訊息
        handle_new_user(event)

# 註冊事件處理器
def register_event_handlers():
    """註冊事件處理器"""
    try:
        handler = get_line_bot_handler()
        if handler:
            handler.add(FollowEvent)(handle_follow)
            handler.add(MessageEvent, message=TextMessage)(handle_text_message)
            handler.add(MessageEvent, message=LocationMessage)(handle_location_message)
            handler.add(PostbackEvent)(handle_postback)
        else:
            print("警告: LINE Bot Handler 未初始化，無法註冊事件處理器")
    except Exception as e:
        print(f"註冊事件處理器失敗: {e}")

def handle_text_message(event):
    """處理文字訊息"""
    user_id = event.source.user_id
    text = event.message.text
    
    # 檢查使用者是否存在
    user = User.query.filter_by(line_user_id=user_id).first()
    
    if not user:
        # 新使用者，引導選擇語言
        handle_new_user(event)
    else:
        # 現有使用者，處理一般訊息
        handle_existing_user(event, user, text)

def handle_new_user(event):
    """處理新使用者加入"""
    user_id = event.source.user_id
    
    # 建立語言選擇選單
    quick_reply = QuickReply(
        items=[
            QuickReplyButton(
                action=MessageAction(label="English", text="I prefer English")
            ),
            QuickReplyButton(
                action=MessageAction(label="日本語", text="日本語を選択")
            ),
            QuickReplyButton(
                action=MessageAction(label="한국어", text="한국어를 선택")
            ),
            QuickReplyButton(
                action=MessageAction(label="中文", text="我選擇中文")
            )
        ]
    )
    
    welcome_message = "歡迎使用點餐小幫手！\n請選擇您的語言偏好：\n\nWelcome to Ordering Helper!\nPlease select your language preference:"
    
    line_bot_api = get_line_bot_api()
    if line_bot_api:
        get_line_bot_api().reply_message(
            event.reply_token,
            TextSendMessage(text=welcome_message, quick_reply=quick_reply)
        )
    else:
        print("LINE Bot API 未初始化")

def handle_existing_user(event, user, text):
    """處理現有使用者的訊息"""
    user_id = event.source.user_id
    
    if text in ["I prefer English", "日本語を選択", "한국어를 선택", "我選擇中文"]:
        # 處理語言選擇
        lang_map = {
            "I prefer English": "en",
            "日本語を選択": "ja", 
            "한국어를 선택": "ko",
            "我選擇中文": "zh"
        }
        
        # 更新使用者語言偏好
        user.preferred_lang = lang_map[text]
        db.session.commit()
        
        # 發送歡迎訊息
        welcome_messages = {
            "en": "Welcome! I'm your ordering assistant. I can help you find restaurants and order food in Chinese.",
            "ja": "ようこそ！注文アシスタントです。中国語でレストランを見つけて注文するお手伝いをします。",
            "ko": "환영합니다! 주문 도우미입니다. 중국어로 레스토랑을 찾고 음식을 주문하는 것을 도와드릴 수 있습니다.",
            "zh": "歡迎！我是您的點餐小幫手。我可以幫您找到餐廳並用中文點餐。"
        }
        
        # 建立功能選單
        quick_reply = QuickReply(
            items=[
                QuickReplyButton(
                    action=MessageAction(label="找餐廳", text="找餐廳")
                ),
                QuickReplyButton(
                    action=MessageAction(label="訂單記錄", text="訂單記錄")
                ),
                QuickReplyButton(
                    action=MessageAction(label="推薦店家", text="推薦店家")
                )
            ]
        )
        
        get_line_bot_api().reply_message(
            event.reply_token,
            TextSendMessage(
                text=welcome_messages[user.preferred_lang],
                quick_reply=quick_reply
            )
        )
    
    elif text.lower() in ["find restaurants", "レストランを探す", "레스토랑 찾기", "找餐廳"]:
        # 處理找餐廳請求
        handle_find_restaurants(event, user)
    
    elif text.lower() in ["order history", "注文履歴", "주문 내역", "訂單記錄"]:
        # 處理查詢訂單記錄
        handle_order_history(event, user)
    
    elif text.lower() in ["recommend restaurants", "レストランを推薦", "레스토랑 추천", "推薦店家"]:
        # 處理推薦店家請求
        handle_recommend_restaurants(event, user)
    
    elif text.startswith("voice_"):
        # 處理語音控制按鈕
        handle_voice_control(event, user, text)
    
    elif text.startswith("temp_voice_"):
        # 處理臨時訂單語音控制按鈕
        handle_temp_voice_control(event, user, text)
    
    else:
        # 檢查是否為餐飲需求描述
        if is_food_request(text):
            handle_food_request(event, user, text)
        else:
            # 一般對話處理
            handle_general_conversation(event, user, text)

def is_food_request(text):
    """判斷是否為餐飲需求描述"""
    food_keywords = [
        "想吃", "想要", "推薦", "找", "尋找", "附近", "餐廳", "美食", "料理", "菜", "飯", "麵", "火鍋", "燒烤", "壽司", "披薩", "漢堡", "咖啡", "飲料", "甜點", "早餐", "午餐", "晚餐", "宵夜"
    ]
    
    return any(keyword in text for keyword in food_keywords)

def handle_food_request(event, user, text):
    """處理餐飲需求並推薦店家"""
    try:
        # 調用 Gemini API 進行推薦
        recommended_stores = get_ai_recommendations(text, user.preferred_lang)
        
        if recommended_stores:
            # 發送推薦結果
            send_recommendation_results(event, recommended_stores, user.preferred_lang)
        else:
            # 沒有找到推薦
            no_recommendation_messages = {
                "en": "Sorry, I couldn't find suitable restaurants for your request. Please try sharing your location to find nearby restaurants.",
                "ja": "申し訳ございませんが、ご要望に合うレストランが見つかりませんでした。位置情報を共有して近くのレストランを探してみてください。",
                "ko": "죄송합니다. 요청에 맞는 레스토랑을 찾을 수 없습니다. 위치를 공유하여 근처 레스토랑을 찾아보세요。",
                "zh": "抱歉，我無法為您的需求找到合適的店家。請分享您的位置來尋找附近的餐廳。"
            }
            message = no_recommendation_messages.get(user.preferred_lang, no_recommendation_messages["zh"])
            
            get_line_bot_api().reply_message(
                event.reply_token,
                TextSendMessage(text=message)
            )
            
    except Exception as e:
        print(f"處理餐飲需求失敗：{e}")
        error_messages = {
            "en": "Sorry, there was an error processing your request. Please try again.",
            "ja": "リクエストの処理中にエラーが発生しました。もう一度お試しください。",
            "ko": "요청 처리 중 오류가 발생했습니다. 다시 시도해 주세요.",
            "zh": "抱歉，處理您的請求時發生錯誤。請再試一次。"
        }
        message = error_messages.get(user.preferred_lang, error_messages["zh"])
        
        get_line_bot_api().reply_message(
            event.reply_token,
            TextSendMessage(text=message)
        )

def get_ai_recommendations(food_request, user_language='zh'):
    """使用 Gemini API 分析餐飲需求並推薦店家"""
    try:
        # 取得所有店家資料
        stores = Store.query.all()
        
        if not stores:
            return []
        
        # 建立店家資料列表
        store_data = []
        for store in stores:
            store_info = {
                'store_id': store.store_id,
                'store_name': store.store_name,
                'partner_level': store.partner_level,
                'review_summary': store.review_summary or '',
                'top_dishes': [
                    store.top_dish_1, store.top_dish_2, store.top_dish_3,
                    store.top_dish_4, store.top_dish_5
                ],
                'main_photo_url': store.main_photo_url
            }
            # 過濾掉空的熱門菜色
            store_info['top_dishes'] = [dish for dish in store_info['top_dishes'] if dish]
            store_data.append(store_info)
        
        # 建立 Gemini 提示詞
        prompt = f"""
你是一個專業的餐飲推薦專家。請根據使用者的餐飲需求，從以下店家列表中推薦最適合的店家。

## 使用者需求：
{food_request}

## 可用店家列表：
{json.dumps(store_data, ensure_ascii=False, indent=2)}

## 推薦規則：
1. **優先順序**：VIP店家 (partner_level=2) > 合作店家 (partner_level=1) > 非合作店家 (partner_level=0)
2. **需求匹配**：根據使用者需求選擇最適合的店家
3. **菜色特色**：考慮店家的熱門菜色和評論摘要
4. **推薦數量**：最多推薦5家店家

## 輸出格式要求：
請嚴格按照以下 JSON 格式輸出，不要包含任何其他文字：

{{
  "recommendations": [
    {{
      "store_id": 店家ID,
      "store_name": "店家名稱",
      "partner_level": 合作等級,
      "reason": "推薦理由",
      "matched_keywords": ["匹配的關鍵字"],
      "estimated_rating": "預估評分 (1-5星)"
    }}
  ],
  "analysis": {{
    "user_preference": "分析出的使用者偏好",
    "recommendation_strategy": "推薦策略說明"
  }}
}}

## 重要注意事項：
- 確保推薦理由符合使用者需求
- 考慮店家的合作等級和特色
- 提供有價值的推薦理由
- 確保 JSON 格式完全正確
- **一律不要使用 ``` 或任何程式碼區塊語法**
- **只輸出 JSON**，不要其他文字
"""

        # 調用 Gemini 2.5 Flash Lite API
        from google import genai
        response = genai.Client().models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[prompt],
            config={
                "response_mime_type": "application/json",  # 新版 JSON Mode
                "thinking_config": genai.types.ThinkingConfig(thinking_budget=512)
            }
        )
        
        # 解析回應
        try:
            result = json.loads(response.text)
            
            if 'recommendations' in result and result['recommendations']:
                # 按照合作等級排序
                recommendations = sorted(
                    result['recommendations'], 
                    key=lambda x: x.get('partner_level', 0), 
                    reverse=True
                )
                return recommendations[:5]  # 最多返回5個推薦
            else:
                return []
                
        except json.JSONDecodeError:
            print("Gemini API 回應格式錯誤")
            return []
            
    except Exception as e:
        print(f"AI 推薦失敗：{e}")
        return []

def send_recommendation_results(event, recommendations, user_language):
    """發送推薦結果"""
    try:
        # 建立推薦結果訊息
        if user_language == "zh":
            message = "🍽️ 根據您的需求，我為您推薦以下店家：\n\n"
        elif user_language == "en":
            message = "🍽️ Based on your request, I recommend the following restaurants:\n\n"
        elif user_language == "ja":
            message = "🍽️ ご要望に基づいて、以下のレストランをお勧めします：\n\n"
        elif user_language == "ko":
            message = "🍽️ 요청에 따라 다음 레스토랑을 추천합니다:\n\n"
        else:
            message = "🍽️ 根據您的需求，我為您推薦以下店家：\n\n"
        
        # 合作等級標籤
        partner_labels = {
            "en": {0: "Non-partner", 1: "Partner", 2: "VIP"},
            "ja": {0: "非提携", 1: "提携", 2: "VIP"},
            "ko": {0: "비제휴", 1: "제휴", 2: "VIP"},
            "zh": {0: "非合作", 1: "合作", 2: "VIP"}
        }
        
        labels = partner_labels.get(user_language, partner_labels["zh"])
        
        for i, rec in enumerate(recommendations, 1):
            store_name = rec.get('store_name', 'Unknown Store')
            partner_level = rec.get('partner_level', 0)
            reason = rec.get('reason', '')
            rating = rec.get('estimated_rating', '')
            
            partner_label = labels.get(partner_level, "非合作")
            
            if user_language == "zh":
                message += f"{i}. **{store_name}** ({partner_label})\n"
                message += f"   📝 {reason}\n"
                if rating:
                    message += f"   ⭐ {rating}\n"
                message += "\n"
            elif user_language == "en":
                message += f"{i}. **{store_name}** ({partner_label})\n"
                message += f"   📝 {reason}\n"
                if rating:
                    message += f"   ⭐ {rating}\n"
                message += "\n"
            elif user_language == "ja":
                message += f"{i}. **{store_name}** ({partner_label})\n"
                message += f"   📝 {reason}\n"
                if rating:
                    message += f"   ⭐ {rating}\n"
                message += "\n"
            elif user_language == "ko":
                message += f"{i}. **{store_name}** ({partner_label})\n"
                message += f"   📝 {reason}\n"
                if rating:
                    message += f"   ⭐ {rating}\n"
                message += "\n"
            else:
                message += f"{i}. **{store_name}** ({partner_label})\n"
                message += f"   📝 {reason}\n"
                if rating:
                    message += f"   ⭐ {rating}\n"
                message += "\n"
        
        # 加入後續操作提示
        if user_language == "zh":
            message += "💡 您可以分享位置來查看這些店家的詳細資訊和開始點餐。"
        elif user_language == "en":
            message += "💡 You can share your location to view detailed information and start ordering from these restaurants."
        elif user_language == "ja":
            message += "💡 位置情報を共有すると、これらのレストランの詳細情報を確認して注文を開始できます。"
        elif user_language == "ko":
            message += "💡 위치를 공유하면 이러한 레스토랑의 자세한 정보를 보고 주문을 시작할 수 있습니다."
        else:
            message += "💡 您可以分享位置來查看這些店家的詳細資訊和開始點餐。"
        
        get_line_bot_api().reply_message(
            event.reply_token,
            TextSendMessage(text=message)
        )
        
    except Exception as e:
        print(f"發送推薦結果失敗：{e}")
        error_messages = {
            "en": "Sorry, there was an error sending the recommendations. Please try again.",
            "ja": "推奨の送信中にエラーが発生しました。もう一度お試しください。",
            "ko": "추천을 보내는 중 오류가 발생했습니다. 다시 시도해 주세요.",
            "zh": "抱歉，發送推薦時發生錯誤。請再試一次。"
        }
        message = error_messages.get(user_language, error_messages["zh"])
        
        get_line_bot_api().reply_message(
            event.reply_token,
            TextSendMessage(text=message)
        )

def handle_recommend_restaurants(event, user):
    """處理推薦店家請求"""
    recommendation_prompts = {
        "en": "Please tell me what kind of food you'd like to eat or any specific requirements (e.g., 'I want spicy food', 'I'm looking for Italian cuisine', 'I need vegetarian options').",
        "ja": "どのような食べ物がお好みか、または特定の要件をお教えください（例：「辛い食べ物が欲しい」「イタリア料理を探している」「ベジタリアンオプションが必要」）。",
        "ko": "어떤 종류의 음식을 원하시는지 또는 특정 요구사항을 알려주세요 (예: '매운 음식을 원해요', '이탈리아 요리를 찾고 있어요', '채식 옵션이 필요해요').",
        "zh": "請告訴我您想要吃什麼樣的食物或任何特定需求（例如：「我想要吃辣的食物」、「我在找義大利料理」、「我需要素食選項」）。"
    }
    
    message = recommendation_prompts.get(user.preferred_lang, recommendation_prompts["zh"])
    
    get_line_bot_api().reply_message(
        event.reply_token,
        TextSendMessage(text=message)
    )

def handle_find_restaurants(event, user):
    """處理找餐廳請求"""
    # 根據使用者語言發送位置請求訊息
    location_messages = {
        "en": "Please share your location so I can find nearby restaurants for you.",
        "ja": "近くのレストランを見つけるために、位置情報を共有してください。",
        "ko": "근처 레스토랑을 찾기 위해 위치를 공유해 주세요.",
        "zh": "請分享您的位置，我將為您找到附近的餐廳。"
    }
    
    message = location_messages.get(user.preferred_lang, location_messages["zh"])
    
    get_line_bot_api().reply_message(
        event.reply_token,
        TextSendMessage(text=message)
    )

def handle_order_history(event, user):
    """處理查詢訂單記錄"""
    try:
        # 查詢使用者的訂單記錄（最近10筆）
        orders = Order.query.filter_by(user_id=user.user_id).order_by(Order.order_time.desc()).limit(10).all()
        
        if not orders:
            # 沒有訂單記錄
            no_orders_messages = {
                "en": "You don't have any order history yet. Start ordering to see your records here!",
                "ja": "まだ注文履歴がありません。注文を開始すると、ここに履歴が表示されます！",
                "ko": "아직 주문 내역이 없습니다. 주문을 시작하면 여기에 내역이 표시됩니다!",
                "zh": "您還沒有訂單記錄。開始點餐後，您的訂單記錄會顯示在這裡！"
            }
            message = no_orders_messages.get(user.preferred_lang, no_orders_messages["zh"])
        else:
            # 有訂單記錄，建立詳細摘要
            order_summary_messages = {
                "en": f"Your recent orders ({len(orders)} orders):",
                "ja": f"最近の注文履歴（{len(orders)}件）:",
                "ko": f"최근 주문 내역 ({len(orders)}건):",
                "zh": f"您的最近訂單記錄（共{len(orders)}筆）:"
            }
            
            message = order_summary_messages.get(user.preferred_lang, order_summary_messages["zh"]) + "\n\n"
            
            for i, order in enumerate(orders, 1):
                store = Store.query.get(order.store_id)
                store_name = store.store_name if store else "Unknown Store"
                
                # 格式化訂單時間
                order_time = order.order_time.strftime("%Y-%m-%d %H:%M")
                
                # 根據使用者語言建立訂單摘要
                if user.preferred_lang == "zh":
                    order_line = f"{i}. {store_name}\n"
                    order_line += f"   時間：{order_time}\n"
                    order_line += f"   金額：${order.total_amount}\n"
                    order_line += f"   狀態：{get_order_status_text(order.status, 'zh')}\n"
                elif user.preferred_lang == "en":
                    order_line = f"{i}. {store_name}\n"
                    order_line += f"   Time: {order_time}\n"
                    order_line += f"   Amount: ${order.total_amount}\n"
                    order_line += f"   Status: {get_order_status_text(order.status, 'en')}\n"
                elif user.preferred_lang == "ja":
                    order_line = f"{i}. {store_name}\n"
                    order_line += f"   時間：{order_time}\n"
                    order_line += f"   金額：${order.total_amount}\n"
                    order_line += f"   状態：{get_order_status_text(order.status, 'ja')}\n"
                elif user.preferred_lang == "ko":
                    order_line = f"{i}. {store_name}\n"
                    order_line += f"   시간: {order_time}\n"
                    order_line += f"   금액: ${order.total_amount}\n"
                    order_line += f"   상태: {get_order_status_text(order.status, 'ko')}\n"
                else:
                    order_line = f"{i}. {store_name}\n"
                    order_line += f"   時間：{order_time}\n"
                    order_line += f"   金額：${order.total_amount}\n"
                    order_line += f"   狀態：{get_order_status_text(order.status, 'zh')}\n"
                
                message += order_line + "\n"
            
            # 加入提示訊息
            tip_messages = {
                "en": "💡 Tip: You can replay the voice for any order by clicking the voice control buttons.",
                "ja": "💡 ヒント：音声制御ボタンをクリックすると、どの注文でも音声を再生できます。",
                "ko": "💡 팁: 음성 제어 버튼을 클릭하면 어떤 주문의 음성도 재생할 수 있습니다.",
                "zh": "💡 小提示：您可以點擊語音控制按鈕來重播任何訂單的語音。"
            }
            message += tip_messages.get(user.preferred_lang, tip_messages["zh"])
        
        get_line_bot_api().reply_message(
            event.reply_token,
            TextSendMessage(text=message)
        )
        
    except Exception as e:
        print(f"查詢訂單記錄失敗：{e}")
        error_messages = {
            "en": "Sorry, there was an error retrieving your order history. Please try again.",
            "ja": "注文履歴の取得中にエラーが発生しました。もう一度お試しください。",
            "ko": "주문 내역을 가져오는 중 오류가 발생했습니다. 다시 시도해 주세요.",
            "zh": "抱歉，查詢訂單記錄時發生錯誤。請重試。"
        }
        message = error_messages.get(user.preferred_lang, error_messages["zh"])
        
        get_line_bot_api().reply_message(
            event.reply_token,
            TextSendMessage(text=message)
        )

def get_order_status_text(status, language):
    """取得訂單狀態的多語言文字"""
    status_texts = {
        "zh": {
            "pending": "處理中",
            "completed": "已完成",
            "cancelled": "已取消"
        },
        "en": {
            "pending": "Processing",
            "completed": "Completed",
            "cancelled": "Cancelled"
        },
        "ja": {
            "pending": "処理中",
            "completed": "完了",
            "cancelled": "キャンセル"
        },
        "ko": {
            "pending": "처리 중",
            "completed": "완료",
            "cancelled": "취소됨"
        }
    }
    
    return status_texts.get(language, status_texts["zh"]).get(status, status)

def handle_general_conversation(event, user, text):
    """處理一般對話"""
    # 這裡可以加入 AI 對話功能
    response = "我理解您的訊息，但我目前主要專注於點餐服務。請告訴我您想要找餐廳還是查看訂單記錄。"
    
    get_line_bot_api().reply_message(
        event.reply_token,
        TextSendMessage(text=response)
    )

def handle_location_message(event):
    """處理位置訊息"""
    user_id = event.source.user_id
    user = User.query.filter_by(line_user_id=user_id).first()
    
    if not user:
        return
    
    # 取得位置資訊
    latitude = event.message.latitude
    longitude = event.message.longitude
    
    try:
        # 呼叫 API 取得鄰近店家
        from app.api.helpers import get_nearby_stores_with_translations
        
        nearby_stores = get_nearby_stores_with_translations(
            latitude, longitude, user.preferred_lang
        )
        
        if not nearby_stores:
            # 沒有找到鄰近店家
            no_stores_messages = {
                "en": "Sorry, no restaurants found nearby. Please try a different location.",
                "ja": "申し訳ございませんが、近くにレストランが見つかりませんでした。別の場所をお試しください。",
                "ko": "죄송합니다. 근처에 레스토랑을 찾을 수 없습니다. 다른 위치를 시도해 주세요.",
                "zh": "抱歉，附近沒有找到餐廳。請嘗試其他位置。"
            }
            message = no_stores_messages.get(user.preferred_lang, no_stores_messages["zh"])
            
            get_line_bot_api().reply_message(
                event.reply_token,
                TextSendMessage(text=message)
            )
            return
        
        # 建立店家清單
        if len(nearby_stores) == 1:
            # 單一店家，直接顯示詳細資訊
            store = nearby_stores[0]
            send_store_detail(event, store, user.preferred_lang)
        else:
            # 多個店家，顯示清單
            send_store_list(event, nearby_stores, user.preferred_lang)
            
    except Exception as e:
        print(f"處理位置訊息失敗：{e}")
        error_messages = {
            "en": "Sorry, there was an error processing your location. Please try again.",
            "ja": "位置情報の処理中にエラーが発生しました。もう一度お試しください。",
            "ko": "위치 처리 중 오류가 발생했습니다. 다시 시도해 주세요.",
            "zh": "抱歉，處理位置時發生錯誤。請再試一次。"
        }
        message = error_messages.get(user.preferred_lang, error_messages["zh"])
        
        get_line_bot_api().reply_message(
            event.reply_token,
            TextSendMessage(text=message)
        )

def send_store_list(event, stores, user_language):
    """發送店家清單"""
    # 建立 Carousel 容器
    columns = []
    
    for store in stores[:10]:  # 最多顯示10個店家
        # 取得合作標籤
        partner_labels = {
            "en": {0: "Non-partner", 1: "Partner", 2: "VIP"},
            "ja": {0: "非提携", 1: "提携", 2: "VIP"},
            "ko": {0: "비제휴", 1: "제휴", 2: "VIP"},
            "zh": {0: "非合作", 1: "合作", 2: "VIP"}
        }
        
        partner_label = partner_labels.get(user_language, partner_labels["zh"]).get(
            store.get('partner_level', 0), "非合作"
        )
        
        # 建立店家資訊
        title = store.get('store_name', 'Unknown Store')
        description = store.get('description', '')
        if description:
            description = f"{description}\n{partner_label}"
        else:
            description = partner_label
        
        # 建立按鈕
        actions = [
            PostbackAction(
                label="查看詳情" if user_language == "zh" else "Details",
                data=f"store_detail_{store['store_id']}"
            )
        ]
        
        column = CarouselColumn(
            title=title,
            text=description,
            actions=actions
        )
        
        # 如果有照片，加入照片
        if store.get('main_photo_url'):
            column.thumbnail_image_url = store['main_photo_url']
        
        columns.append(column)
    
    # 建立 Carousel 模板
    carousel = CarouselContainer(columns=columns)
    
    # 發送訊息
    get_line_bot_api().reply_message(
        event.reply_token,
        FlexSendMessage(
            alt_text="附近餐廳清單",
            contents=carousel
        )
    )

def send_store_detail(event, store, user_language):
    """發送店家詳細資訊"""
    # 取得合作標籤
    partner_labels = {
        "en": {0: "Non-partner", 1: "Partner", 2: "VIP"},
        "ja": {0: "非提携", 1: "提携", 2: "VIP"},
        "ko": {0: "비제휴", 1: "제휴", 2: "VIP"},
        "zh": {0: "非合作", 1: "合作", 2: "VIP"}
    }
    
    partner_label = partner_labels.get(user_language, partner_labels["zh"]).get(
        store.get('partner_level', 0), "非合作"
    )
    
    # 建立詳細資訊
    title = store.get('store_name', 'Unknown Store')
    description = store.get('description', '')
    reviews = store.get('reviews', '')
    
    # 組合完整描述
    full_description = f"{description}\n\n{partner_label}"
    if reviews:
        full_description += f"\n\n評論：{reviews}"
    
    # 建立按鈕
    actions = [
        PostbackAction(
            label="開始點餐" if user_language == "zh" else "Start Ordering",
            data=f"start_ordering_{store['store_id']}"
        ),
        PostbackAction(
            label="返回清單" if user_language == "zh" else "Back to List",
            data="back_to_list"
        )
    ]
    
    # 建立 Flex 訊息
    bubble = {
        "type": "bubble",
        "hero": {
            "type": "image",
            "url": store.get('main_photo_url', 'https://via.placeholder.com/400x200'),
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": title,
                    "weight": "bold",
                    "size": "lg"
                },
                {
                    "type": "text",
                    "text": full_description,
                    "wrap": True,
                    "color": "#666666",
                    "size": "sm",
                    "margin": "md"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "開始點餐" if user_language == "zh" else "Start Ordering",
                        "data": f"start_ordering_{store['store_id']}"
                    },
                    "style": "primary"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "返回清單" if user_language == "zh" else "Back to List",
                        "data": "back_to_list"
                    },
                    "style": "secondary",
                    "margin": "sm"
                }
            ]
        }
    }
    
    get_line_bot_api().reply_message(
        event.reply_token,
        FlexSendMessage(
            alt_text=f"{title} 詳細資訊",
            contents=bubble
        )
    )

def send_voice_order(order_id, user_id=None):
    """
    發送語音訂單到 LINE（使用背景處理）
    這個函數會在訂單建立後被呼叫
    """
    if user_id:
        # 使用背景處理，避免 webhook 超時
        logger.info(f"🎵 啟動背景語音處理: order_id={order_id}, user_id={user_id}")
        thread = threading.Thread(
            target=process_voice_order_background,
            args=(order_id, user_id),
            daemon=True
        )
        thread.start()
        logger.info(f"✅ 背景語音處理已啟動: order_id={order_id}")
    else:
        # 備用方案：使用舊的同步處理
        logger.warning(f"⚠️ 未提供 user_id，使用同步處理: order_id={order_id}")
        from ..api.helpers import send_complete_order_notification
        # 在 webhook 中沒有 store_name 資訊，傳遞 None 使用資料庫中的店名
        send_complete_order_notification(order_id, None)

def handle_postback(event):
    """處理 Postback 事件"""
    data = event.postback.data
    user_id = event.source.user_id
    user = User.query.filter_by(line_user_id=user_id).first()
    
    if not user:
        return
    
    try:
        if data.startswith("store_detail_"):
            # 查看店家詳細資訊
            store_id = int(data.split("_")[2])
            handle_store_detail(event, store_id, user)
        elif data.startswith("start_ordering_"):
            # 開始點餐
            store_id = int(data.split("_")[2])
            handle_start_ordering(event, store_id, user)
        elif data == "back_to_list":
            # 返回店家清單
            handle_back_to_list(event, user)
        else:
            # 未知的 postback 事件
            print(f"未知的 postback 事件：{data}")
            
    except Exception as e:
        logger.exception(f"❌ 處理 postback 事件失敗：{e}")
        error_messages = {
            "en": "Sorry, there was an error processing your request. Please try again.",
            "ja": "リクエストの処理中にエラーが発生しました。もう一度お試しください。",
            "ko": "요청 처리 중 오류가 발생했습니다. 다시 시도해 주세요.",
            "zh": "抱歉，處理您的請求時發生錯誤。請再試一次。"
        }
        message = error_messages.get(user.preferred_lang, error_messages["zh"])
        
        try:
            line_bot_api = get_line_bot_api()
            if line_bot_api:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=message)
                )
                logger.info(f"✅ 錯誤訊息已發送: user_id={user.line_user_id}")
            else:
                logger.error("❌ LINE Bot API 不可用，無法發送錯誤訊息")
        except Exception as reply_error:
            logger.exception(f"❌ 發送錯誤訊息失敗: {reply_error}")

def handle_store_detail(event, store_id, user):
    """處理店家詳細資訊查看"""
    try:
        from ..models import Store
        from .api.helpers import get_store_translation_from_db
        
        store = Store.query.get(store_id)
        if not store:
            not_found_messages = {
                "en": "Store not found.",
                "ja": "店舗が見つかりません。",
                "ko": "매장을 찾을 수 없습니다.",
                "zh": "找不到店家。"
            }
            message = not_found_messages.get(user.preferred_lang, not_found_messages["zh"])
            
            get_line_bot_api().reply_message(
                event.reply_token,
                TextSendMessage(text=message)
            )
            return
        
        # 取得店家翻譯
        store_translation = get_store_translation_from_db(store.store_id, user.preferred_lang)
        
        # 建立店家資料
        store_data = {
            'store_id': store.store_id,
            'store_name': store.store_name,
            'partner_level': store.partner_level,
            'main_photo_url': store.main_photo_url,
            'gps_lat': store.gps_lat or store.latitude,
            'gps_lng': store.gps_lng or store.longitude
        }
        
        # 加入翻譯資訊
        if store_translation:
            store_data['description'] = store_translation.description_trans or store.review_summary or ''
            store_data['reviews'] = store_translation.reviews or ''
        else:
            if user.preferred_lang != 'zh':
                store_data['description'] = translate_text_with_fallback(
                    store.review_summary or '', user.preferred_lang
                )
                store_data['reviews'] = ''
            else:
                store_data['description'] = store.review_summary or ''
                store_data['reviews'] = ''
        
        # 發送詳細資訊
        send_store_detail(event, store_data, user.preferred_lang)
        
    except Exception as e:
        logger.exception(f"❌ 處理店家詳細資訊失敗：{e}")
        raise

def handle_start_ordering(event, store_id, user):
    """處理開始點餐"""
    try:
        from ..models import Store
        
        # 立即發送處理中訊息，避免 webhook 超時
        if not send_processing_message(event, user.preferred_lang):
            logger.error("❌ 無法發送處理中訊息，可能導致 webhook 超時")
        
        store = Store.query.get(store_id)
        if not store:
            not_found_messages = {
                "en": "Store not found.",
                "ja": "店舗が見つかりません。",
                "ko": "매장을 찾을 수 없습니다.",
                "zh": "找不到店家。"
            }
            message = not_found_messages.get(user.preferred_lang, not_found_messages["zh"])
            
            get_line_bot_api().reply_message(
                event.reply_token,
                TextSendMessage(text=message)
            )
            return
        
        # 根據店家類型決定下一步
        if store.partner_level > 0:
            # 合作店家，跳轉到 LIFF
            liff_url = f"https://green-beach-0f9c8c70f.azurestaticapps.net/?store_id={store_id}&partner=true&store_name={store.store_name}&lang={user.preferred_lang}"
            
            messages = {
                "en": f"Starting to order from {store.store_name}...",
                "ja": f"{store.store_name}での注文を開始します...",
                "ko": f"{store.store_name}에서 주문을 시작합니다...",
                "zh": f"開始從 {store.store_name} 點餐..."
            }
            message = messages.get(user.preferred_lang, messages["zh"])
            
            # 建立 LIFF 按鈕
            actions = [
                URIAction(
                    label="進入點餐頁面" if user.preferred_lang == "zh" else "Enter Ordering Page",
                    uri=liff_url
                )
            ]
            
            quick_reply = QuickReply(items=actions)
            
            get_line_bot_api().reply_message(
                event.reply_token,
                TextSendMessage(text=message, quick_reply=quick_reply)
            )
        else:
            # 非合作店家，建立記錄並跳轉到 LIFF
            # 先檢查是否已經有店家記錄
            if not store:
                # 建立非合作店家記錄
                new_store = Store(
                    store_name=f"Non-partner Store {store_id}",
                    partner_level=0,  # 非合作店家
                    gps_lat=None,
                    gps_lng=None
                )
                db.session.add(new_store)
                db.session.commit()
                store_id = new_store.store_id
            
            # 跳轉到非合作店家的 LIFF 頁面
            liff_url = f"https://green-beach-0f9c8c70f.azurestaticapps.net/?store_id={store_id}&partner=false&store_name={store.store_name}&lang={user.preferred_lang}"
            
            messages = {
                "en": f"Please take a photo of the menu from {store.store_name} to start ordering.",
                "ja": f"{store.store_name}のメニューの写真を撮って注文を開始してください。",
                "ko": f"{store.store_name}의 메뉴 사진을 찍어 주문을 시작하세요.",
                "zh": f"請拍攝 {store.store_name} 的菜單照片開始點餐。"
            }
            message = messages.get(user.preferred_lang, messages["zh"])
            
            # 建立 LIFF 按鈕
            actions = [
                URIAction(
                    label="拍攝菜單" if user.preferred_lang == "zh" else "Take Menu Photo",
                    uri=liff_url
                )
            ]
            
            quick_reply = QuickReply(items=actions)
            
            get_line_bot_api().reply_message(
                event.reply_token,
                TextSendMessage(text=message, quick_reply=quick_reply)
            )
        
    except Exception as e:
        logger.exception(f"❌ 處理開始點餐失敗：{e}")
        raise

def handle_back_to_list(event, user):
    """處理返回店家清單"""
    try:
        messages = {
            "en": "Please share your location again to see the restaurant list.",
            "ja": "レストランリストを表示するために、もう一度位置情報を共有してください。",
            "ko": "레스토랑 목록을 보려면 위치를 다시 공유해 주세요.",
            "zh": "請再次分享您的位置以查看餐廳清單。"
        }
        message = messages.get(user.preferred_lang, messages["zh"])
        
        line_bot_api = get_line_bot_api()
        if line_bot_api:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=message)
            )
            logger.info(f"✅ 返回清單訊息已發送: user_id={user.line_user_id}")
        else:
            logger.error("❌ LINE Bot API 不可用，無法發送返回清單訊息")
    except Exception as e:
        logger.exception(f"❌ 處理返回店家清單失敗：{e}")

# 語音控制處理函數已移除（節省成本）

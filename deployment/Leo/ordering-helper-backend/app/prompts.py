# =============================================================================
# 檔案名稱：app/prompts.py
# 功能描述：提示詞工程模組，包含各種 AI 功能的優化提示詞
# 主要職責：
# - 菜單 OCR 辨識提示詞
# - 語音指令處理提示詞
# - 多語言翻譯提示詞
# - 訂單摘要生成提示詞
# 支援功能：
# - 結構化輸出格式
# - 多語言支援
# - 錯誤處理和回退
# - 上下文感知
# =============================================================================

import json
from typing import Dict, List, Optional

class PromptEngineer:
    """提示詞工程師類別"""
    
    def __init__(self):
        self.system_prompts = {
            'menu_ocr': self._get_menu_ocr_prompt(),
            'voice_processing': self._get_voice_processing_prompt(),
            'translation': self._get_translation_prompt(),
            'order_summary': self._get_order_summary_prompt()
        }
    
    def _get_menu_ocr_prompt(self) -> str:
        """菜單 OCR 辨識提示詞"""
        return """
你是一個專業的菜單辨識專家。請仔細分析這張菜單圖片，並執行以下任務：

## 任務要求：
1. **OCR 辨識**：準確辨識所有菜單項目、價格和描述
2. **結構化處理**：將辨識結果整理成結構化資料
3. **語言翻譯**：將菜名翻譯為目標語言
4. **價格標準化**：統一價格格式（數字）

## 輸出格式要求：
請嚴格按照以下 JSON 格式輸出，不要包含任何其他文字：

```json
{
  "success": true,
  "menu_items": [
    {
      "original_name": "原始菜名（中文）",
      "translated_name": "翻譯後菜名",
      "price": 數字價格,
      "description": "菜單描述（如果有）",
      "category": "分類（如：主食、飲料、小菜等）"
    }
  ],
  "store_info": {
    "name": "店家名稱",
    "address": "地址（如果有）",
    "phone": "電話（如果有）"
  },
  "processing_notes": "處理備註"
}
```

## 重要注意事項：
- 價格必須是數字格式
- 如果無法辨識某個項目，請在 processing_notes 中說明
- 確保 JSON 格式完全正確，可以直接解析
- 如果圖片模糊或無法辨識，請將 success 設為 false
"""

    def _get_voice_processing_prompt(self) -> str:
        """語音指令處理提示詞"""
        return """
你是一個專業的語音指令處理專家。請分析用戶的語音指令，並執行以下任務：

## 任務要求：
1. **語音辨識**：準確理解用戶的語音指令
2. **意圖識別**：識別用戶的點餐意圖
3. **實體提取**：提取菜名、數量、特殊要求等
4. **結構化輸出**：將結果整理成結構化資料

## 輸出格式要求：
```json
{
  "success": true,
  "intent": "點餐意圖（如：add_item, remove_item, confirm_order等）",
  "extracted_items": [
    {
      "item_name": "菜名",
      "quantity": 數量,
      "special_requests": ["特殊要求"],
      "confidence": 0.95
    }
  ],
  "user_message": "用戶原始語音文字",
  "processed_message": "處理後的指令",
  "language": "識別出的語言"
}
```

## 支援的指令類型：
- 新增項目：「我要點牛肉麵」
- 修改數量：「牛肉麵改成兩份」
- 移除項目：「不要牛肉麵了」
- 確認訂單：「就這樣，確認訂單」
- 查詢菜單：「有什麼推薦的？」
"""

    def _get_translation_prompt(self) -> str:
        """多語言翻譯提示詞"""
        return """
你是一個專業的多語言翻譯專家。請將以下內容翻譯為目標語言，保持語境和語調的準確性。

## 翻譯要求：
1. **保持語境**：確保翻譯後的內容符合目標語言的文化背景
2. **專業術語**：使用正確的餐飲專業術語
3. **語調一致**：保持原文的語調和風格
4. **格式保持**：保持原有的格式和結構

## 輸出格式：
```json
{
  "success": true,
  "original_text": "原文",
  "translated_text": "翻譯後文字",
  "target_language": "目標語言",
  "translation_notes": "翻譯備註"
}
```

## 支援的語言：
- 中文 (zh-TW)
- 英文 (en-US)
- 日文 (ja-JP)
- 韓文 (ko-KR)
"""

    def _get_order_summary_prompt(self) -> str:
        """訂單摘要生成提示詞"""
        return """
你是一個專業的訂單摘要生成專家。請根據訂單資訊生成清晰、完整的訂單摘要。

## 摘要要求：
1. **完整性**：包含所有訂單項目和數量
2. **清晰性**：使用清晰的格式和語言
3. **專業性**：使用適當的餐飲術語
4. **多語言**：支援多語言輸出

## 輸出格式：
```json
{
  "success": true,
  "summary": {
    "chinese": "中文摘要",
    "english": "英文摘要",
    "japanese": "日文摘要"
  },
  "order_details": {
    "order_id": "訂單編號",
    "store_name": "店家名稱",
    "total_amount": 總金額,
    "item_count": 項目數量
  }
}
```

## 摘要內容應包含：
- 訂單編號
- 店家資訊
- 訂購項目清單
- 數量統計
- 總金額
- 訂單時間
"""

    def get_menu_ocr_prompt(self, target_language: str = 'en') -> str:
        """獲取菜單 OCR 提示詞"""
        prompt = self.system_prompts['menu_ocr']
        return prompt.replace("目標語言", target_language)

    def get_voice_processing_prompt(self, language: str = 'zh-TW') -> str:
        """獲取語音處理提示詞"""
        prompt = self.system_prompts['voice_processing']
        return prompt.replace("識別出的語言", language)

    def get_translation_prompt(self, target_language: str = 'en') -> str:
        """獲取翻譯提示詞"""
        prompt = self.system_prompts['translation']
        return prompt.replace("目標語言", target_language)

    def get_order_summary_prompt(self) -> str:
        """獲取訂單摘要提示詞"""
        return self.system_prompts['order_summary']

    def create_contextual_prompt(self, base_prompt: str, context: Dict) -> str:
        """創建上下文感知的提示詞"""
        contextual_prompt = base_prompt
        
        # 添加用戶偏好
        if 'user_preferences' in context:
            prefs = context['user_preferences']
            contextual_prompt += f"\n\n## 用戶偏好：\n"
            for key, value in prefs.items():
                contextual_prompt += f"- {key}: {value}\n"
        
        # 添加歷史記錄
        if 'order_history' in context:
            history = context['order_history']
            contextual_prompt += f"\n\n## 歷史訂單：\n"
            for order in history[:3]:  # 只顯示最近3筆
                contextual_prompt += f"- {order}\n"
        
        # 添加特殊要求
        if 'special_requests' in context:
            requests = context['special_requests']
            contextual_prompt += f"\n\n## 特殊要求：\n"
            for req in requests:
                contextual_prompt += f"- {req}\n"
        
        return contextual_prompt

    def validate_response(self, response: str) -> Dict:
        """驗證 AI 回應格式"""
        try:
            # 嘗試解析 JSON
            result = json.loads(response)
            
            # 檢查必要欄位
            if 'success' not in result:
                return {"valid": False, "error": "缺少 success 欄位"}
            
            return {"valid": True, "data": result}
            
        except json.JSONDecodeError as e:
            return {"valid": False, "error": f"JSON 格式錯誤: {str(e)}"}
        except Exception as e:
            return {"valid": False, "error": f"驗證失敗: {str(e)}"}

    def create_fallback_prompt(self, original_prompt: str, error_message: str) -> str:
        """創建回退提示詞"""
        return f"""
{original_prompt}

## 錯誤處理：
之前的處理遇到問題：{error_message}

請嘗試以下方法：
1. 重新分析輸入內容
2. 使用更寬鬆的標準
3. 提供部分結果而不是完全失敗
4. 在 processing_notes 中說明遇到的問題

請確保輸出格式正確，即使結果不完整。
"""

# 全域提示詞工程師實例
prompt_engineer = PromptEngineer() 
import google.generativeai as genai
from utils.logger import setup_logger

logger = setup_logger('analyzer')

class ReviewAnalyzer:
    def __init__(self, config):
        self.api_key = config['api_keys']['REVIEW_GEMINI_API_KEY']
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-pro')
    
    def analyze_reviews(self, reviews, store_name):
        """分析評論並生成摘要"""
        try:
            if not reviews:
                logger.warning(f"店家 {store_name} 沒有評論資料")
                return ""
            
            # 準備評論文字 - 修正欄位名稱匹配
            review_texts = []
            for review in reviews:
                # 修正：根據 database.py 回傳的結構，使用正確的欄位名稱
                if 'review_text' in review and review['review_text']:
                    review_texts.append(review['review_text'])
                elif 'snippet' in review and review['snippet']:
                    review_texts.append(review['snippet'])
                elif 'text' in review and review['text']:
                    review_texts.append(review['text'])
            
            if not review_texts:
                logger.warning(f"店家 {store_name} 沒有可分析的評論文字")
                return ""
            
            # 記錄找到的評論數量
            logger.info(f"店家 {store_name} 找到 {len(review_texts)} 則可分析的評論")
            
            # 限制評論數量避免token過多
            review_texts = review_texts[:50]
            reviews_content = "\n".join(review_texts)
            
            prompt = f"""
請分析以下餐廳「{store_name}」的Google評論，並生成繁體中文的分析報告，直接輸出繁體中文的分析報告，不要加任何前言或說明：

評論內容：
{reviews_content}

請按照以下格式輸出：

[請用100字以內描述餐廳菜系、特色料理和平均價位]

## 網友好評Top5
1. [菜品名稱] - [10-20字摘要評論]
2. [菜品名稱] - [10-20字摘要評論]
3. [菜品名稱] - [10-20字摘要評論]
4. [菜品名稱] - [10-20字摘要評論]
5. [菜品名稱] - [10-20字摘要評論]

注意事項：
- 直接輸出分析報告，不要有「好的，這是...」等開場白
- 請使用繁體中文
- 如果評論中沒有足夠的菜品資訊，請根據現有資訊盡量分析
- 評論摘要要友善，突出餐廳特色，濾除負面情緒和不相關內容
"""
            
            logger.info(f"開始分析店家 {store_name} 的評論")
            response = self.model.generate_content(prompt)
            
            if response and response.text:
                logger.info(f"成功分析店家 {store_name} 的評論")
                return response.text.strip()
            else:
                logger.error(f"Gemini API 沒有返回分析結果")
                return ""
                
        except Exception as e:
            logger.error(f"分析評論時發生錯誤: {e}")
            return ""
    
    def extract_dishes_from_reviews(self, reviews):
        """從評論中提取菜品資訊（輔助方法）"""
        try:
            dishes = {}
            
            for review in reviews:
                # 修正：使用正確的欄位名稱
                text = review.get('review_text', '') or review.get('snippet', '') or review.get('text', '')
                if not text:
                    continue
                
                # 簡單的菜品關鍵字提取（可以根據需要擴展）
                food_keywords = ['好吃', '美味', '推薦', '必點', '招牌', '特色']
                
                for keyword in food_keywords:
                    if keyword in text:
                        # 這裡可以實現更複雜的菜品名稱提取邏輯
                        # 目前簡化處理
                        pass
            
            return dishes
            
        except Exception as e:
            logger.error(f"提取菜品資訊時發生錯誤: {e}")
            return {}
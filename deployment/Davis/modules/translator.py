import google.generativeai as genai
from utils.logger import setup_logger
import mysql.connector.pooling
from mysql.connector import Error

logger = setup_logger('translator')

class ReviewTranslator:
    def __init__(self, config):
        self.api_key = config['api_keys']['REVIEW_GEMINI_API_KEY']
        genai.configure(api_key=self.api_key)
        #self.model = genai.GenerativeModel('gemini-2.5-pro')
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # 資料庫配置
        self.db_config = config['mysql']
        self.db_pool = None
        
        # 語言對應表 - 將從資料庫動態載入
        self.language_mapping = {}
        
        # 初始化資料庫連線池並載入語言設定
        self._create_db_pool()
        self._load_languages()
    
    def _create_db_pool(self):
        """建立資料庫連線池"""
        try:
            self.db_pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="review_translator_pool",
                pool_size=10,  # 設定連線池大小
                host=self.db_config['host'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                port=int(self.db_config['port']),
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
            logger.info("翻譯器資料庫連線池建立成功")
            
        except Error as e:
            logger.error(f"翻譯器資料庫連線池建立失敗: {e}")
            raise
    
    def _load_languages(self):
        """從資料庫載入語言設定"""
        connection = None
        cursor = None
        try:
            connection = self.db_pool.get_connection()
            cursor = connection.cursor(dictionary=True)
            
            query = """
                SELECT line_lang_code lang_code, lang_name 
                FROM languages 
                WHERE line_lang_code in (
                    'tr','vi','zh','zh-Hans','zh-Hant'
                )
            """
            query = """
                SELECT line_lang_code lang_code, lang_name 
                FROM languages 
            """
            cursor.execute(query)
            languages = cursor.fetchall()
            
            # 建立語言對應表
            for lang in languages:
                lang_code = lang['lang_code']
                lang_name = lang['lang_name']
                
                if lang_code == 'en':
                    self.language_mapping[lang_code] = 'English'
                elif lang_code == 'ja':
                    self.language_mapping[lang_code] = 'Japanese'
                elif lang_code == 'ko':
                    self.language_mapping[lang_code] = 'Korean'
                elif lang_code == 'zh':
                    self.language_mapping[lang_code] = 'Traditional Chinese (Taiwan)'
                elif lang_code == 'zh-Hant':
                    self.language_mapping[lang_code] = 'Traditional Chinese (Taiwan)'
                else:
                    self.language_mapping[lang_code] = lang_name
            
            logger.info(f"成功載入 {len(self.language_mapping)} 種語言設定")
            
        except Error as e:
            logger.error(f"載入語言設定失敗: {e}")
            # 使用預設語言設定
            self.language_mapping = {
                'en': 'English',
                'ja': 'Japanese', 
                'ko': 'Korean',
                'zh-Hant': 'Traditional Chinese (Taiwan)',
                'zh': 'Traditional Chinese (Taiwan)'
            }
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close() # 歸還連線到連線池
    
    def _extract_response_text(self, response):
        """安全地提取 Gemini API 回應文字內容"""
        try:
            if not response:
                logger.error("Gemini API 回應為空")
                return ""
            
            if not hasattr(response, 'candidates') or not response.candidates:
                logger.error("Gemini API 回應中沒有 candidates")
                return ""
            
            candidate = response.candidates[0]
            
            if not hasattr(candidate, 'content') or not candidate.content:
                logger.error("Gemini API 回應中沒有 content")
                return ""
            
            if not hasattr(candidate.content, 'parts') or not candidate.content.parts:
                logger.error("Gemini API 回應中沒有 parts")
                return ""
            
            text_parts = []
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text:
                    text_parts.append(part.text)
            
            if not text_parts:
                try:
                    if hasattr(response, 'text') and response.text:
                        return response.text
                except Exception as e:
                    logger.warning(f"無法使用 response.text: {e}")
                
                logger.error("Gemini API 回應中沒有可用的文字內容")
                return ""
            
            return ''.join(text_parts)
            
        except Exception as e:
            logger.error(f"提取 Gemini API 回應文字時發生錯誤: {e}")
            try:
                if hasattr(response, 'text'):
                    return response.text
            except:
                pass
            return ""
    
    def translate_review_summary(self, review_summary, target_lang_code):
        """翻譯評論摘要"""
        try:
            if not review_summary or not review_summary.strip():
                logger.warning("評論摘要為空，跳過翻譯")
                return ""
            
            if target_lang_code == 'zh-Hant' or target_lang_code == 'zh':
                logger.info(f"目標語言為繁體中文 ({target_lang_code})，直接返回原文")
                return review_summary
            
            target_language = self.language_mapping.get(target_lang_code, target_lang_code)
            
            prompt = f"""
請將以下繁體中文的餐廳評論摘要翻譯成{target_language}，保持原有格式和結構，不要加任何前言或說明：

{review_summary}

翻譯要求：
1. 保持原有的標題格式（## 標題）
2. 保持菜品Top5的編號格式
3. 翻譯要自然流暢，符合目標語言的表達習慣
4. 菜品名稱可以保留中文並加上{target_language}翻譯
5. 數字和統計資訊保持不變
6. 使用專業的餐廳評論術語
7. 直接輸出分析報告，不要有「好的，這是...」等開場白
"""
            
            logger.info(f"開始翻譯評論摘要到 {target_language} ({target_lang_code})")
            
            response = self.model.generate_content(prompt)
            
            translated_text = self._extract_response_text(response)
            
            if translated_text:
                translated_text = translated_text.strip()
                logger.info(f"成功翻譯評論摘要到 {target_language}")
                logger.debug(f"翻譯結果長度: {len(translated_text)} 字符")
                return translated_text
            else:
                logger.error(f"Gemini API 翻譯失敗，沒有返回有效結果")
                return ""
                
        except Exception as e:
            logger.error(f"翻譯評論摘要到 {target_lang_code} 時發生錯誤: {e}")
            import traceback
            logger.error(f"詳細錯誤資訊: {traceback.format_exc()}")
            return ""
    
    def batch_translate_and_save(self, store_id, review_summary):
        """批量翻譯並儲存到資料庫"""
        try:
            if not review_summary or not review_summary.strip():
                logger.warning("評論摘要為空，跳過批量翻譯")
                return {}
            
            target_languages = [
                lang_code for lang_code in self.language_mapping.keys() 
                #if lang_code != 'zh-Hant'
                #if lang_code != 'zh'
            ]
            
            logger.info(f"開始批量翻譯店家 {store_id} 到 {len(target_languages)} 種語言")
            
            translations = {}
            success_count = 0
            fail_count = 0
            
            for lang_code in target_languages:
                try:
                    lang_name = self.language_mapping[lang_code]
                    logger.info(f"正在翻譯到 {lang_name} ({lang_code})")
                    
                    translation = self.translate_review_summary(review_summary, lang_code)
                    
                    if translation:
                        if self._save_translation_to_db(store_id, lang_code, translation):
                            translations[lang_code] = translation
                            logger.info(f"成功翻譯並儲存到 {lang_name}")
                            success_count += 1
                        else:
                            logger.warning(f"翻譯成功但儲存失敗: {lang_name}")
                            fail_count += 1
                    else:
                        logger.warning(f"翻譯到 {lang_name} 失敗")
                        fail_count += 1
                    
                    import time
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"處理語言 {lang_code} 時發生錯誤: {e}")
                    fail_count += 1
                    continue
            
            if self._save_translation_to_db(store_id, 'zhh-Hant', review_summary):
                translations['zh-Hant'] = review_summary
                logger.info("成功儲存原文（繁體中文）")
                success_count += 1
            elif self._save_translation_to_db(store_id, 'zh', review_summary):
                translations['zh'] = review_summary
                logger.info("成功儲存原文（繁體中文）")
                success_count += 1
            
            logger.info(f"批量翻譯完成，成功 {success_count} 種語言，失敗 {fail_count} 種語言")
            return translations
            
        except Exception as e:
            logger.error(f"批量翻譯處理失敗: {e}")
            import traceback
            logger.error(f"詳細錯誤資訊: {traceback.format_exc()}")
            return {}
    
    def _save_translation_to_db(self, store_id, lang_code, translation):
        """將翻譯結果儲存到資料庫"""
        connection = None
        cursor = None
        try:
            connection = self.db_pool.get_connection()
            cursor = connection.cursor()

            # 使用 ON DUPLICATE KEY UPDATE 以實現存在即更新，不存在即插入
            query = """
                INSERT INTO store_translations (
                    store_id, language_code, translated_summary
                ) VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                translated_summary = VALUES(translated_summary);
            """
            cursor.execute(query, (store_id, lang_code, translation))
            
            connection.commit()
            logger.debug(f"成功儲存或更新店家 {store_id} 語言 {lang_code} 的翻譯")
            return True
            
        except Error as e:
            logger.error(f"儲存翻譯到資料庫失敗: {e}")
            if connection:
                connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close() # 歸還連線到連線池
    
    def get_translation_from_db(self, store_id, lang_code):
        """從資料庫取得翻譯"""
        connection = None
        cursor = None
        try:
            connection = self.db_pool.get_connection()
            cursor = connection.cursor(dictionary=True)
            
            query = """
                SELECT translated_summary FROM store_translations 
                WHERE store_id = %s AND language_code = %s
            """
            cursor.execute(query, (store_id, lang_code))
            result = cursor.fetchone()
            
            if result:
                return result['translated_summary']
            else:
                logger.info(f"找不到店家 {store_id} 語言 {lang_code} 的翻譯")
                return None
                
        except Error as e:
            logger.error(f"從資料庫取得翻譯失敗: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def get_all_translations_for_store(self, store_id):
        """取得店家所有語言的翻譯"""
        connection = None
        cursor = None
        try:
            connection = self.db_pool.get_connection()
            cursor = connection.cursor(dictionary=True)
            
            query = """
                SELECT st.language_code, st.translated_summary, l.lang_name
                FROM store_translations st
                JOIN languages l ON st.language_code = l.line_lang_code
                WHERE st.store_id = %s
            """
            cursor.execute(query, (store_id,))
            results = cursor.fetchall()
            
            translations = {}
            for row in results:
                translations[row['language_code']] = {
                    'translation': row['translated_summary'],
                    'lang_name': row['lang_name']
                }
            
            logger.info(f"取得店家 {store_id} 的 {len(translations)} 種語言翻譯")
            return translations
            
        except Error as e:
            logger.error(f"取得店家翻譯失敗: {e}")
            return {}
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def validate_translation(self, original_text, translated_text, target_lang_code):
        """驗證翻譯品質（可選功能）"""
        try:
            if not translated_text or len(translated_text.strip()) < 10:
                logger.warning(f"翻譯結果過短，可能翻譯失敗: {target_lang_code}")
                return False
            
            if "##" in original_text and "##" not in translated_text:
                logger.warning(f"翻譯結果缺少標題格式: {target_lang_code}")
                return False
            
            if "Top5" in original_text or "top5" in original_text.lower():
                if not any(char.isdigit() for char in translated_text):
                    logger.warning(f"翻譯結果缺少數字編號: {target_lang_code}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"驗證翻譯時發生錯誤: {e}")
            return True  # 驗證失敗時預設為通過
    
    def get_supported_languages(self):
        """取得支援的語言列表"""
        return list(self.language_mapping.keys())
    
    def is_language_supported(self, lang_code):
        """檢查是否支援特定語言"""
        return lang_code in self.language_mapping.keys()
    
    def close_pool(self):
        """關閉連線池 (實際上不做任何事，因為連線池會在程式結束時自動釋放)"""
        # 這裡不需要任何操作，避免 AttributeError
        pass
    
    def __del__(self):
        """析構函數，確保連線池被關閉 (可選)"""
        # 由於連線池會在程式結束時自動釋放，這個函數可以選擇性地移除
        # 如果你保留它，它也不需要做任何事
        pass
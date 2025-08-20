import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
from dateutil import parser
import json
import sys
import os

# 確保能夠找到 utils 模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.logger import setup_logger
    logger = setup_logger('database')
except ImportError as e:
    # 如果無法導入 logger，使用標準 logging
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('database')
    logger.warning(f"無法導入自定義 logger，使用標準 logging: {e}")

class DatabaseManager:
    def __init__(self, config):
        try:
            # 檢查 config 是否包含 mysql 區塊
            if hasattr(config, 'sections'):
                # ConfigParser 物件
                if 'mysql' not in config.sections():
                    raise ValueError("設定檔中找不到 'mysql' 區塊")
                
                # 檢查必要的MySQL設定項目
                required_keys = ['host', 'database', 'user', 'password', 'port']
                missing_keys = []
                
                for key in required_keys:
                    if not config.has_option('mysql', key):
                        missing_keys.append(key)
                
                if missing_keys:
                    raise ValueError(f"MySQL設定缺少以下項目: {', '.join(missing_keys)}")
                
                self.config = config
            elif isinstance(config, dict):
                # 字典格式的 config
                if 'mysql' not in config:
                    raise ValueError("設定檔中找不到 'mysql' 區塊")
                
                required_keys = ['host', 'database', 'user', 'password', 'port']
                missing_keys = []
                
                for key in required_keys:
                    if key not in config['mysql']:
                        missing_keys.append(key)
                
                if missing_keys:
                    raise ValueError(f"MySQL設定缺少以下項目: {', '.join(missing_keys)}")
                
                self.config = config
            else:
                raise ValueError("不支援的設定檔格式")
            
            self.connection = None
            self.cursor = None
            
            logger.info("DatabaseManager 初始化成功")
            
        except Exception as e:
            logger.error(f"DatabaseManager 初始化失敗: {e}")
            raise
    
    def connect(self):
        """連接到MySQL資料庫"""
        try:
            logger.info("正在連接資料庫...")
            
            if hasattr(self.config, 'sections'):
                # ConfigParser 格式
                db_config = {
                    'host': self.config['mysql']['host'],
                    'database': self.config['mysql']['database'],
                    'user': self.config['mysql']['user'],
                    'password': self.config['mysql']['password'],
                    'port': int(self.config['mysql']['port'])
                }
            else:
                # 字典格式
                db_config = {
                    'host': self.config['mysql']['host'],
                    'database': self.config['mysql']['database'],
                    'user': self.config['mysql']['user'],
                    'password': self.config['mysql']['password'],
                    'port': int(self.config['mysql']['port'])
                }
            
            self.connection = mysql.connector.connect(
                **db_config,
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
            
            if self.connection.is_connected():
                self.cursor = self.connection.cursor(dictionary=True)
                db_info = self.connection.get_server_info()
                logger.info(f"資料庫連接成功，MySQL 版本: {db_info}")
                
                # 檢查並創建必要的表和欄位
                self._check_and_update_schema()
                
                return True
                
        except Error as e:
            logger.error(f"資料庫連接失敗: {e}")
            if hasattr(self.config, 'sections'):
                logger.error(f"連接參數: host={self.config['mysql']['host']}, "
                            f"database={self.config['mysql']['database']}, "
                            f"user={self.config['mysql']['user']}, "
                            f"port={self.config['mysql']['port']}")
            else:
                logger.error(f"連接參數: host={self.config['mysql']['host']}, "
                            f"database={self.config['mysql']['database']}, "
                            f"user={self.config['mysql']['user']}, "
                            f"port={self.config['mysql']['port']}")
            return False
        except Exception as e:
            logger.error(f"資料庫連接時發生未預期錯誤: {e}")
            return False
    
    def _check_and_update_schema(self):
        """檢查並更新資料庫結構"""
        try:
            # 檢查並創建 languages 表
            self._check_languages_table()
            # 檢查並創建 store_translations 表
            self._check_store_translations_table()
            
        except Exception as e:
            logger.error(f"檢查資料庫結構時發生錯誤: {e}")
    
    def _check_languages_table(self):
        """檢查並創建 languages 表"""
        try:
            if hasattr(self.config, 'sections'):
                database_name = self.config['mysql']['database']
            else:
                database_name = self.config['mysql']['database']
                
            check_table_query = """
                SELECT COUNT(*) as count
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = 'languages'
            """
            self.cursor.execute(check_table_query, (database_name,))
            result = self.cursor.fetchone()
            
            if result['count'] == 0:
                create_languages_query = """
                    CREATE TABLE languages (
                        translation_lang_code VARCHAR(10) UNIQUE NOT NULL,
                        lang_name VARCHAR(100) NOT NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin
                """
                self.cursor.execute(create_languages_query)
                self.connection.commit()
                logger.info("創建 languages 表")
            
        except Error as e:
            logger.error(f"檢查 languages 表時發生錯誤: {e}")
    
    def _check_store_translations_table(self):
        """檢查並創建 store_translations 表"""
        try:
            if hasattr(self.config, 'sections'):
                database_name = self.config['mysql']['database']
            else:
                database_name = self.config['mysql']['database']
                
            check_table_query = """
                SELECT COUNT(*) as count
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = 'store_translations'
            """
            self.cursor.execute(check_table_query, (database_name,))
            result = self.cursor.fetchone()
            
            if result['count'] == 0:
                # 根據 order_menu.sql 創建正確的表結構
                create_translations_query = """
                    CREATE TABLE store_translations (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        store_id INT NOT NULL,
                        language_code VARCHAR(5) NOT NULL,
                        description TEXT,
                        translated_summary TEXT,
                        UNIQUE KEY uk_store_language (store_id, language_code)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin
                """
                self.cursor.execute(create_translations_query)
                self.connection.commit()
                logger.info("創建 store_translations 表")
            
        except Error as e:
            logger.error(f"檢查 store_translations 表時發生錯誤: {e}")
    
    def disconnect(self):
        """關閉資料庫連接"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection and self.connection.is_connected():
                self.connection.close()
                logger.info("資料庫連接已關閉")
        except Error as e:
            logger.error(f"關閉資料庫連接時發生錯誤: {e}")
    
    def get_stores(self):
        """取得所有店家資料（根據實際資料庫結構）"""
        try:
            # 從 crawl_logs 表取得最後爬取時間
            query = """
                SELECT 
                    s.store_id, 
                    s.store_name, 
                    s.place_id,
                    cl.last_crawl_time
                FROM stores s
                LEFT JOIN crawl_logs cl ON s.store_id = cl.store_id
                WHERE s.place_id IS NOT NULL AND s.place_id != ''
                AND s.partner_level=1
                ORDER BY s.store_id
            """
            # 'ChIJdWk3iYerQjQRF1p1og3XSZA',小螺波 慶城店 - 台灣螺螄粉第一品牌
            # 'ChIJT3kS-92rQjQRMox_EZZCP0Q',聚馥園餐廳
            # 'ChIJobbAd-erQjQRTyr_YtJbjOc',
            self.cursor.execute(query)
            stores = self.cursor.fetchall()
            logger.info(f"取得 {len(stores)} 家店家資訊")
            return stores
            
        except Error as e:
            logger.error(f"取得店家資料失敗: {e}")
            return []
    
    def save_reviews(self, store_id, place_id, reviews):
        """儲存評論到資料庫（根據實際資料庫結構）"""
        try:
            saved_count = 0
            
            for review in reviews:
                try:
                    # 解析並轉換評論時間
                    review_time_str = review.get('date', '')
                    review_datetime = self._parse_review_time(review_time_str)
                    
                    # 檢查評論是否已存在（根據評論時間和部分內容）
                    review_text = review.get('snippet', '')
                    check_query = """
                        SELECT review_id FROM reviews 
                        WHERE store_id = %s AND place_id = %s 
                        AND review_time = %s AND JSON_EXTRACT(review_data, '$.snippet') = %s
                    """
                    
                    self.cursor.execute(check_query, (store_id, place_id, review_datetime, review_text))
                    existing = self.cursor.fetchone()
                    
                    if existing:
                        logger.debug(f"評論已存在，跳過: {review.get('user', {}).get('name', 'Anonymous')}")
                        continue
                    
                    # 插入新評論
                    insert_query = """
                        INSERT INTO reviews (
                            store_id, place_id, review_data, review_time, rating, created_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, NOW()
                        )
                    """
                    
                    values = (
                        store_id,
                        place_id,
                        json.dumps(review, ensure_ascii=False),  # 儲存完整JSON資料
                        review_datetime,
                        review.get('rating', 0)
                    )
                    
                    self.cursor.execute(insert_query, values)
                    saved_count += 1
                    
                except Exception as e:
                    logger.warning(f"儲存單則評論失敗: {e}")
                    continue
            
            # 提交所有變更
            self.connection.commit()
            logger.info(f"成功儲存 {saved_count} 則評論")
            return saved_count
            
        except Error as e:
            logger.error(f"儲存評論失敗: {e}")
            if self.connection:
                self.connection.rollback()
            return 0
    
    def _parse_review_time(self, date_str):
        """解析評論時間並轉換為datetime格式"""
        try:
            if not date_str:
                return datetime.now()
            
            now = datetime.now()
            date_str_lower = date_str.lower().strip()
            
            # 處理中文相對時間
            if '小時前' in date_str or 'hour' in date_str_lower:
                numbers = ''.join(filter(str.isdigit, date_str))
                if numbers:
                    hours = int(numbers)
                    return now - timedelta(hours=hours)
                return now - timedelta(hours=1)  # 預設1小時前
                
            elif '天前' in date_str or 'day' in date_str_lower:
                numbers = ''.join(filter(str.isdigit, date_str))
                if numbers:
                    days = int(numbers)
                    return now - timedelta(days=days)
                return now - timedelta(days=1)  # 預設1天前
                
            elif '週前' in date_str or '周前' in date_str or 'week' in date_str_lower:
                numbers = ''.join(filter(str.isdigit, date_str))
                if numbers:
                    weeks = int(numbers)
                    return now - timedelta(weeks=weeks)
                return now - timedelta(weeks=1)  # 預設1週前
                
            elif '月前' in date_str or 'month' in date_str_lower:
                numbers = ''.join(filter(str.isdigit, date_str))
                if numbers:
                    months = int(numbers)
                    return now - timedelta(days=months*30)  # 近似計算
                return now - timedelta(days=30)  # 預設1月前
                
            elif '年前' in date_str or 'year' in date_str_lower:
                numbers = ''.join(filter(str.isdigit, date_str))
                if numbers:
                    years = int(numbers)
                    return now - timedelta(days=years*365)  # 近似計算
                return now - timedelta(days=365)  # 預設1年前
            
            # 處理英文 "a/an" 格式
            elif date_str_lower.startswith('a ') or date_str_lower.startswith('an '):
                if 'hour' in date_str_lower:
                    return now - timedelta(hours=1)
                elif 'day' in date_str_lower:
                    return now - timedelta(days=1)
                elif 'week' in date_str_lower:
                    return now - timedelta(weeks=1)
                elif 'month' in date_str_lower:
                    return now - timedelta(days=30)
                elif 'year' in date_str_lower:
                    return now - timedelta(days=365)
            
            # 嘗試直接解析標準日期格式
            try:
                return parser.parse(date_str)
            except:
                pass
                
            # 如果都無法解析，返回當前時間
            logger.warning(f"無法解析時間格式: '{date_str}'，使用當前時間")
            return now
            
        except Exception as e:
            logger.warning(f"解析評論時間失敗: '{date_str}', 錯誤: {e}")
            return datetime.now()
    
    def get_store_reviews(self, store_id):
        """取得店家的所有評論（根據實際資料庫結構）"""
        try:
            query = """
                SELECT 
                    review_id, 
                    review_data, 
                    review_time, 
                    rating, 
                    created_at
                FROM reviews 
                WHERE store_id = %s 
                ORDER BY review_time DESC
            """
            self.cursor.execute(query, (store_id,))
            raw_reviews = self.cursor.fetchall()
            
            # 解析JSON資料
            reviews = []
            for row in raw_reviews:
                try:
                    review_data = json.loads(row['review_data'])
                    reviews.append({
                        'review_id': row['review_id'],
                        'author_name': review_data.get('user', {}).get('name', 'Anonymous'),
                        'rating': row['rating'],
                        'review_text': review_data.get('snippet', ''),
                        'review_time': row['review_time'],
                        'likes_count': review_data.get('likes', 0),
                        'created_at': row['created_at']
                    })
                except json.JSONDecodeError as e:
                    logger.warning(f"解析評論JSON失敗: {e}")
                    continue
            
            logger.info(f"取得店家 {store_id} 的 {len(reviews)} 則評論")
            return reviews
            
        except Error as e:
            logger.error(f"取得評論資料失敗: {e}")
            return []
    
    def update_crawl_log(self, store_id, review_count, status='success'):
        """更新爬蟲日誌（根據實際資料庫結構）"""
        try:
            # 檢查是否已存在該店家的記錄
            check_query = "SELECT log_id FROM crawl_logs WHERE store_id = %s"
            self.cursor.execute(check_query, (store_id,))
            existing = self.cursor.fetchone()
            
            if existing:
                # 更新現有記錄
                update_query = """
                    UPDATE crawl_logs 
                    SET last_crawl_time = NOW(), reviews_count = %s, status = %s
                    WHERE store_id = %s
                """
                self.cursor.execute(update_query, (review_count, status, store_id))
            else:
                # 插入新記錄
                insert_query = """
                    INSERT INTO crawl_logs (
                        store_id, last_crawl_time, reviews_count, status, created_at
                    ) VALUES (%s, NOW(), %s, %s, NOW())
                """
                self.cursor.execute(insert_query, (store_id, review_count, status))
            
            self.connection.commit()
            logger.info(f"更新店家 {store_id} 爬蟲日誌")
            
        except Error as e:
            logger.error(f"更新爬蟲日誌失敗: {e}")
            if self.connection:
                self.connection.rollback()
    
    def update_store_summary(self, store_id, summary):
        """更新店家評論摘要"""
        try:
            query = """
                UPDATE stores 
                SET review_summary = %s
                WHERE store_id = %s
            """
            self.cursor.execute(query, (summary, store_id))
            self.connection.commit()
            logger.info(f"更新店家 {store_id} 評論摘要")
            
        except Error as e:
            logger.error(f"更新評論摘要失敗: {e}")
            if self.connection:
                self.connection.rollback()
    
    def get_languages(self):
        """取得所有啟用的語言"""
        try:
            query = """
                SELECT line_lang_code lang_code, lang_name 
                FROM languages 
            """
            self.cursor.execute(query)
            languages = self.cursor.fetchall()
            logger.info(f"取得 {len(languages)} 種語言")
            return languages
            
        except Error as e:
            logger.error(f"取得語言資料失敗: {e}")
            return []
    
    def update_store_translation(self, store_id, lang_code, translation):
        """更新店家翻譯"""
        try:
            # 先檢查是否已存在
            check_query = """
                SELECT id FROM store_translations 
                WHERE store_id = %s AND language_code = %s
            """
            self.cursor.execute(check_query, (store_id, lang_code))
            existing = self.cursor.fetchone()
            
            if existing:
                # 更新現有記錄
                update_query = """
                    UPDATE store_translations 
                    SET translated_summary = %s
                    WHERE store_id = %s AND language_code = %s
                """
                self.cursor.execute(update_query, (translation, store_id, lang_code))
            else:
                # 插入新記錄
                insert_query = """
                    INSERT INTO store_translations (
                        store_id, language_code, translated_summary
                    ) VALUES (%s, %s, %s)
                """
                self.cursor.execute(insert_query, (store_id, lang_code, translation))
            
            self.connection.commit()
            logger.info(f"更新店家 {store_id} 的 {lang_code} 翻譯")
            
        except Error as e:
            logger.error(f"更新翻譯失敗: {e}")
            if self.connection:
                self.connection.rollback()

# 測試 DatabaseManager 是否能正確導入
if __name__ == "__main__":
    print("DatabaseManager 類別定義成功！")
    print(f"DatabaseManager 位置: {DatabaseManager}")
    print(f"DatabaseManager 方法: {[method for method in dir(DatabaseManager) if not method.startswith('_')]}")
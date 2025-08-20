import requests
import time
from datetime import datetime, timedelta
from dateutil import parser
from utils.logger import setup_logger

logger = setup_logger('crawler')

class ReviewCrawler:
    def __init__(self, config):
        self.api_key = config['serp']['SERP_API_KEY']
        self.engine = config['serp']['SERP_ENGINE']
        self.hl = config['serp']['SERP_H1']
        self.sort_by = config['serp']['SERP_SORT_BY']
        self.review_limit = int(config['serp']['SERP_REVIEW_LIMIT'])
        self.base_url = "https://serpapi.com/search.json"
    
    def crawl_reviews(self, place_id, last_crawl_time=None):
        """爬取Google評論"""
        try:
            params = {
                'engine': self.engine,
                'place_id': place_id,
                'api_key': self.api_key,
                'hl': self.hl,
                'limit': self.review_limit,
                'sort_by': self.sort_by
            }
            
            logger.info(f"開始爬取 place_id: {place_id} 的評論")
            logger.info(f"請求參數: engine={self.engine}, hl={self.hl}, sort_by={self.sort_by}, num={self.review_limit}")
            
            # 判斷是否為首次爬取
            if last_crawl_time is None:
                # 首次爬取，設定為365天前
                cutoff_time = datetime.now() - timedelta(days=365)
                logger.info(f"首次爬取該店家，將抓取 {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} 之後的評論")
            else:
                cutoff_time = last_crawl_time
                logger.info(f"上次爬取時間: {cutoff_time}")

            response = requests.get(self.base_url, params=params)
            
            if response.status_code == 401:
                logger.error("API認證失敗 (401)，請檢查 SerpAPI Key 是否正確")
                logger.error(f"使用的API Key: {self.api_key[:10]}...")
                return []
            elif response.status_code == 429:
                logger.error("API請求次數超過限制 (429)，請稍後再試")
                return []
            elif response.status_code != 200:
                logger.error(f"API請求失敗，狀態碼: {response.status_code}")
                logger.error(f"回應內容: {response.text[:500]}")
                return []
            
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"JSON解析失敗: {e}")
                logger.error(f"回應內容: {response.text[:500]}")
                return []
            
            if 'error' in data:
                logger.error(f"SerpAPI 返回錯誤: {data['error']}")
                return []
            
            if 'reviews' not in data:
                logger.warning(f"place_id: {place_id} 沒有找到評論資料")
                logger.info(f"API回應結構: {list(data.keys())}")
                return []
            
            reviews = data['reviews']
            logger.info(f"API返回 {len(reviews)} 則評論")
            
            # 過濾評論（首次爬取時使用365天前作為cutoff_time）
            filtered_reviews = self._filter_reviews_by_time(reviews, cutoff_time)
            
            if last_crawl_time is None:
                logger.info(f"首次爬取，過濾後取得 {len(filtered_reviews)} 則評論（365天內）")
            else:
                logger.info(f"過濾後取得 {len(filtered_reviews)} 則新評論")
            
            return filtered_reviews
            
        except requests.RequestException as e:
            logger.error(f"網路請求錯誤: {e}")
            return []
        except Exception as e:
            logger.error(f"爬取評論時發生錯誤: {e}")
            return []
    
    def _filter_reviews_by_time(self, reviews, cutoff_time):
        """根據時間過濾評論"""
        try:
            # 確保 cutoff_time 是 datetime 物件
            if isinstance(cutoff_time, str):
                cutoff_datetime = parser.parse(cutoff_time)
            else:
                cutoff_datetime = cutoff_time
            
            filtered_reviews = []
            
            for i, review in enumerate(reviews):
                try:
                    # 解析評論時間
                    review_date_str = review.get('date', '')
                    if review_date_str:
                        review_datetime = self._parse_relative_date(review_date_str)
                        
                        if review_datetime:
                            if review_datetime > cutoff_datetime:
                                filtered_reviews.append(review)
                                logger.debug(f"評論 {i+1}: {review_date_str} -> 符合條件")
                            else:
                                logger.debug(f"評論 {i+1}: {review_date_str} -> 太舊，過濾掉")
                        else:
                            # 無法解析時間，預設為符合條件
                            filtered_reviews.append(review)
                            logger.warning(f"評論 {i+1}: 無法解析時間 '{review_date_str}'，預設保留")
                    else:
                        # 如果沒有時間資訊，預設為符合條件
                        filtered_reviews.append(review)
                        logger.warning(f"評論 {i+1}: 沒有時間資訊，預設保留")
                        
                except Exception as e:
                    logger.warning(f"處理評論 {i+1} 時發生錯誤: {e}")
                    # 處理失敗時，預設為符合條件
                    filtered_reviews.append(review)
            
            return filtered_reviews
            
        except Exception as e:
            logger.error(f"過濾評論時發生錯誤: {e}")
            return reviews
    
    def _filter_new_reviews(self, reviews, last_crawl_time):
        """過濾新評論（向後兼容的方法）"""
        return self._filter_reviews_by_time(reviews, last_crawl_time)
    
    def _parse_relative_date(self, date_str):
        """解析相對時間"""
        try:
            now = datetime.now()
            date_str_lower = date_str.lower().strip()
            
            # 處理英文相對時間
            if 'hour' in date_str_lower or '小時' in date_str_lower:
                # 提取數字
                numbers = ''.join(filter(str.isdigit, date_str))
                if numbers:
                    hours = int(numbers)
                    result = now - timedelta(hours=hours)
                    logger.debug(f"解析 '{date_str}' 為 {hours} 小時前: {result}")
                    return result
                    
            elif 'day' in date_str_lower or '天' in date_str_lower:
                numbers = ''.join(filter(str.isdigit, date_str))
                if numbers:
                    days = int(numbers)
                    result = now - timedelta(days=days)
                    logger.debug(f"解析 '{date_str}' 為 {days} 天前: {result}")
                    return result
                    
            elif 'week' in date_str_lower or '週' in date_str_lower or '周' in date_str_lower:
                numbers = ''.join(filter(str.isdigit, date_str))
                if numbers:
                    weeks = int(numbers)
                    result = now - timedelta(weeks=weeks)
                    logger.debug(f"解析 '{date_str}' 為 {weeks} 週前: {result}")
                    return result
                    
            elif 'month' in date_str_lower or '月' in date_str_lower:
                numbers = ''.join(filter(str.isdigit, date_str))
                if numbers:
                    months = int(numbers)
                    result = now - timedelta(days=months*30)  # 近似計算
                    logger.debug(f"解析 '{date_str}' 為 {months} 月前: {result}")
                    return result
                    
            elif 'year' in date_str_lower or '年' in date_str_lower:
                numbers = ''.join(filter(str.isdigit, date_str))
                if numbers:
                    years = int(numbers)
                    result = now - timedelta(days=years*365)  # 近似計算
                    logger.debug(f"解析 '{date_str}' 為 {years} 年前: {result}")
                    return result
            
            # 處理 "a day ago", "an hour ago" 等格式
            elif date_str_lower.startswith('a ') or date_str_lower.startswith('an '):
                if 'hour' in date_str_lower:
                    result = now - timedelta(hours=1)
                    logger.debug(f"解析 '{date_str}' 為 1 小時前: {result}")
                    return result
                elif 'day' in date_str_lower:
                    result = now - timedelta(days=1)
                    logger.debug(f"解析 '{date_str}' 為 1 天前: {result}")
                    return result
                elif 'week' in date_str_lower:
                    result = now - timedelta(weeks=1)
                    logger.debug(f"解析 '{date_str}' 為 1 週前: {result}")
                    return result
                elif 'month' in date_str_lower:
                    result = now - timedelta(days=30)
                    logger.debug(f"解析 '{date_str}' 為 1 月前: {result}")
                    return result
                elif 'year' in date_str_lower:
                    result = now - timedelta(days=365)
                    logger.debug(f"解析 '{date_str}' 為 1 年前: {result}")
                    return result
            
            # 嘗試直接解析日期格式
            else:
                try:
                    result = parser.parse(date_str)
                    logger.debug(f"直接解析日期 '{date_str}': {result}")
                    return result
                except:
                    pass
                
        except Exception as e:
            logger.warning(f"解析相對時間失敗: '{date_str}', 錯誤: {e}")
            
        return None

    def test_api_connection(self):
        """測試 SerpAPI 連接"""
        try:
            test_params = {
                'engine': 'google',
                'q': 'test',
                'api_key': self.api_key
            }
            
            response = requests.get("https://serpapi.com/search", params=test_params, timeout=10)
            logger.info(f"API測試回應狀態碼: {response.status_code}")
            
            if response.status_code == 200:
                logger.info("SerpAPI 連接測試成功")
                return True
            elif response.status_code == 401:
                logger.error("SerpAPI Key 無效")
                return False
            else:
                logger.error(f"API測試失敗，狀態碼: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"API連接測試失敗: {e}")
            return False

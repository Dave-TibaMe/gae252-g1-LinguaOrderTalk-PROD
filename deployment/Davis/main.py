#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import configparser
import sys
import time
import os
from modules.database import DatabaseManager
from modules.crawler import ReviewCrawler
from modules.analyzer import ReviewAnalyzer
from modules.translator import ReviewTranslator
from utils.logger import setup_logger

logger = setup_logger('main')

class ReviewAnalysisSystem:
    def __init__(self, config_file='config.ini'):
        try:
            # 檢查設定檔是否存在
            if not os.path.exists(config_file):
                raise FileNotFoundError(f"設定檔 {config_file} 不存在")
            
            # 讀取設定檔
            self.config = configparser.ConfigParser()
            self.config.read(config_file, encoding='utf-8')
            
            # 檢查必要的設定區塊
            required_sections = ['mysql', 'api_keys', 'serp']
            missing_sections = []
            
            for section in required_sections:
                if not self.config.has_section(section):
                    missing_sections.append(section)
            
            if missing_sections:
                raise ValueError(f"設定檔缺少以下區塊: {', '.join(missing_sections)}")
            
            # 檢查MySQL設定的必要項目
            mysql_required_keys = ['host', 'database', 'user', 'password', 'port']
            missing_mysql_keys = []
            
            for key in mysql_required_keys:
                if not self.config.has_option('mysql', key):
                    missing_mysql_keys.append(key)
            
            if missing_mysql_keys:
                raise ValueError(f"MySQL設定缺少以下項目: {', '.join(missing_mysql_keys)}")
            
            # 顯示設定檔資訊
            logger.info(f"成功讀取設定檔: {config_file}")
            logger.info(f"資料庫主機: {self.config['mysql']['host']}")
            logger.info(f"資料庫名稱: {self.config['mysql']['database']}")
            
            # 初始化各模組
            logger.info("正在初始化系統模組...")
            self.db_manager = DatabaseManager(self.config)
            self.crawler = ReviewCrawler(self.config)
            self.analyzer = ReviewAnalyzer(self.config)
            self.translator = ReviewTranslator(self.config)
            logger.info("系統模組初始化完成")
            
        except Exception as e:
            logger.error(f"系統初始化失敗: {e}")
            # 顯示更詳細的錯誤資訊
            import traceback
            logger.error(f"詳細錯誤: {traceback.format_exc()}")
            raise
    
    def test_apis(self):
        """測試所有API連接"""
        logger.info("=== 開始測試API連接 ===")
        
        try:
            # 測試 SerpAPI
            if not self.crawler.test_api_connection():
                logger.error("SerpAPI 連接測試失敗，請檢查 API Key")
                return False
            
            logger.info("所有API連接測試通過")
            return True
            
        except Exception as e:
            logger.error(f"API測試時發生錯誤: {e}")
            return False
    
    def run(self, force_crawl=False):
        """執行主要流程"""
        try:
            logger.info("=== 開始執行店家Google評論分析系統 ===")
            
            # 測試API連接
            if not self.test_apis():
                logger.error("API連接測試失敗，程式終止")
                return
            
            # 連接資料庫
            if not self.db_manager.connect():
                logger.error("資料庫連接失敗，程式終止")
                return
            
            # 取得店家列表
            stores = self.db_manager.get_stores()
            if not stores:
                logger.warning("沒有找到店家資料")
                return
            
            logger.info(f"開始處理 {len(stores)} 家店家")
            
            for store in stores:
                try:
                    self.process_store(store, force_crawl)
                    # 避免API請求過於頻繁
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"處理店家 {store['store_name']} 時發生錯誤: {e}")
                    continue
            
            logger.info("=== 所有店家處理完成 ===")
            
        except Exception as e:
            logger.error(f"系統執行時發生錯誤: {e}")
            import traceback
            logger.error(f"詳細錯誤資訊: {traceback.format_exc()}")
        finally:
            if hasattr(self, 'db_manager'):
                self.db_manager.disconnect()
    
    def process_store(self, store, force_crawl=False):
        """處理單一店家"""
        store_id = store['store_id']
        store_name = store['store_name']
        place_id = store['place_id']
        last_crawl_time = store['last_crawl_time']
        
        logger.info(f"開始處理店家: {store_name} (ID: {store_id})")
        
        # Step 1: 爬取Google評論
        if force_crawl:
            # 強制爬取模式：從365天前開始
            crawl_time = None
            logger.info("強制爬取模式：將從365天前開始抓取評論")
        elif last_crawl_time is None:
            # 首次爬取：從365天前開始
            crawl_time = None
            logger.info("首次爬取該店家：將從365天前開始抓取評論")
        else:
            # 正常模式：從上次爬取時間開始
            crawl_time = last_crawl_time
            logger.info(f"從上次爬取時間開始：{last_crawl_time}")
        
        reviews = self.crawler.crawl_reviews(place_id, crawl_time)
        
        
        if not reviews:
            logger.info(f"店家 {store_name} 沒有符合條件的評論")
            self.db_manager.update_crawl_log(store_id, 0, 'no_matching_reviews')
            
            # 即使沒有新評論，也嘗試分析現有評論
            logger.info(f"嘗試分析店家 {store_name} 的現有評論")
            all_reviews = self.db_manager.get_store_reviews(store_id)
            
            if all_reviews:
                self._analyze_and_translate(store_id, store_name, all_reviews)
            
            return
        
        # Step 2: 儲存評論到資料庫
        saved_count = self.db_manager.save_reviews(store_id, place_id, reviews)
        self.db_manager.update_crawl_log(store_id, saved_count)
        
        # Step 3: 取得所有評論進行分析
        all_reviews = self.db_manager.get_store_reviews(store_id)
        
        if not all_reviews:
            logger.warning(f"店家 {store_name} 沒有評論資料可供分析")
            return
        
        # Step 4-7: 分析和翻譯
        self._analyze_and_translate(store_id, store_name, all_reviews)
        
        logger.info(f"店家 {store_name} 處理完成")
    
    def _analyze_and_translate(self, store_id, store_name, all_reviews):
        """分析評論並翻譯"""
        try:
            # Step 4: 使用Gemini分析評論
            logger.info(f"開始分析店家 {store_name} 的評論")
            review_summary = self.analyzer.analyze_reviews(all_reviews, store_name)
            
            if not review_summary:
                logger.warning(f"店家 {store_name} 評論分析失敗")
                return
            
            # Step 5: 更新stores表的review_summary
            self.db_manager.update_store_summary(store_id, review_summary)
            
            # Step 6: 取得語言列表並進行翻譯
            languages = self.db_manager.get_languages()
            
            if languages:
                logger.info(f"開始翻譯店家 {store_name} 的評論摘要")
                translations = self.translator.batch_translate_and_save(store_id, review_summary)
                
                # Step 7: 更新store_translations表
                for lang_code, translation in translations.items():
                    if translation:
                        self.db_manager.update_store_translation(
                            store_id, lang_code, translation
                        )
            
            logger.info(f"店家 {store_name} 分析和翻譯完成")
            
        except Exception as e:
            logger.error(f"分析和翻譯店家 {store_name} 時發生錯誤: {e}")

def main():
    """主程式入口"""
    try:
        # 檢查是否有強制爬取參數
        force_crawl = '--force' in sys.argv or '-f' in sys.argv
        
        if force_crawl:
            logger.info("啟用強制爬取模式")
        
        # 顯示當前工作目錄和設定檔位置
        logger.info(f"當前工作目錄: {os.getcwd()}")
        config_path = os.path.abspath('config.ini')
        logger.info(f"設定檔路徑: {config_path}")
        logger.info(f"設定檔是否存在: {os.path.exists('config.ini')}")
        
        # 如果設定檔不存在，顯示範例
        if not os.path.exists('config.ini'):
            logger.error("設定檔 config.ini 不存在！")
            logger.info("請建立 config.ini 檔案，內容如下：")
            logger.info("""
[mysql]
host = localhost
database = lingua_order_talk
user = root
password = your_password
port = 3306

[serpapi]
api_key = your_serpapi_key

[gemini]
api_key = your_gemini_key

[google_translate]
api_key = your_google_translate_key
            """)
            return
        
        system = ReviewAnalysisSystem()
        system.run(force_crawl)
        
    except KeyboardInterrupt:
        logger.info("程式被用戶中斷")
    except Exception as e:
        logger.error(f"程式執行失敗: {e}")
        import traceback
        logger.error(f"詳細錯誤資訊: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()

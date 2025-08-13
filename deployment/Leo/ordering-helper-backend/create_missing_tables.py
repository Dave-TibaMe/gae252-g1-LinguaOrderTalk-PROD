#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
創建缺失資料表腳本

功能：
1. 檢查並創建缺失的資料表
2. 修復資料庫結構問題
"""

import os
import sys
from datetime import datetime

# 載入環境變數
try:
    from dotenv import load_dotenv
    load_dotenv('.env')
    print("✓ 已載入 .env 檔案")
except ImportError:
    print("⚠️ python-dotenv 未安裝，使用系統環境變數")
except FileNotFoundError:
    print("⚠️ .env 檔案未找到，使用系統環境變數")

def create_missing_tables():
    """創建缺失的資料表"""
    print("\n=== 創建缺失資料表 ===")
    
    try:
        from app import create_app
        from app.models import db
        from sqlalchemy import inspect, text
        
        app = create_app()
        
        with app.app_context():
            # 檢查現有表
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            print(f"現有資料表: {existing_tables}")
            
            # 檢查並創建必要的表
            required_tables = ['ocr_menus', 'ocr_menu_items', 'ocr_menu_translations', 'order_summaries']
            
            for table_name in required_tables:
                if table_name not in existing_tables:
                    print(f"🔧 創建 {table_name} 表...")
                    
                    if table_name == 'ocr_menus':
                        # 創建 ocr_menus 表
                        create_table_sql = """
                        CREATE TABLE ocr_menus (
                            ocr_menu_id BIGINT NOT NULL AUTO_INCREMENT,
                            user_id BIGINT NOT NULL,
                            store_id INT DEFAULT NULL,
                            store_name VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
                            upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY (ocr_menu_id),
                            FOREIGN KEY (user_id) REFERENCES users (user_id),
                            FOREIGN KEY (store_id) REFERENCES stores (store_id)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='非合作店家用戶OCR菜單主檔'
                        """
                        
                        db.session.execute(text(create_table_sql))
                        db.session.commit()
                        print(f"✅ {table_name} 表創建成功")
                        
                    elif table_name == 'ocr_menu_translations':
                        # 創建 ocr_menu_translations 表
                        create_table_sql = """
                        CREATE TABLE ocr_menu_translations (
                            ocr_menu_translation_id BIGINT NOT NULL AUTO_INCREMENT,
                            ocr_menu_item_id BIGINT NOT NULL,
                            lang_code VARCHAR(10) NOT NULL,
                            translated_name VARCHAR(100) COLLATE utf8mb4_bin NOT NULL,
                            translated_description TEXT COLLATE utf8mb4_bin,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY (ocr_menu_translation_id),
                            FOREIGN KEY (ocr_menu_item_id) REFERENCES ocr_menu_items (ocr_menu_item_id),
                            FOREIGN KEY (lang_code) REFERENCES languages (line_lang_code)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='OCR菜單翻譯表'
                        """
                        
                        db.session.execute(text(create_table_sql))
                        db.session.commit()
                        print(f"✅ {table_name} 表創建成功")
                        
                    elif table_name == 'ocr_menu_items':
                        # 創建 ocr_menu_items 表
                        create_table_sql = """
                        CREATE TABLE ocr_menu_items (
                            ocr_menu_item_id BIGINT NOT NULL AUTO_INCREMENT,
                            ocr_menu_id BIGINT NOT NULL,
                            item_name VARCHAR(100) COLLATE utf8mb4_bin NOT NULL,
                            price_big INT DEFAULT NULL,
                            price_small INT NOT NULL,
                            translated_desc TEXT COLLATE utf8mb4_bin,
                            PRIMARY KEY (ocr_menu_item_id),
                            FOREIGN KEY (ocr_menu_id) REFERENCES ocr_menus (ocr_menu_id)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='OCR菜單品項明細'
                        """
                        
                        db.session.execute(text(create_table_sql))
                        db.session.commit()
                        print(f"✅ {table_name} 表創建成功")
                        
                    elif table_name == 'order_summaries':
                        # 創建 order_summaries 表
                        create_table_sql = """
                        CREATE TABLE order_summaries (
                            summary_id BIGINT NOT NULL AUTO_INCREMENT,
                            order_id BIGINT NOT NULL,
                            ocr_menu_id BIGINT NULL,
                            chinese_summary TEXT NOT NULL,
                            user_language_summary TEXT NOT NULL,
                            user_language VARCHAR(10) NOT NULL,
                            total_amount INT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY (summary_id),
                            FOREIGN KEY (order_id) REFERENCES orders (order_id),
                            FOREIGN KEY (ocr_menu_id) REFERENCES ocr_menus (ocr_menu_id)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='訂單摘要'
                        """
                        
                        db.session.execute(text(create_table_sql))
                        db.session.commit()
                        print(f"✅ {table_name} 表創建成功")
                        
                    else:
                        print(f"❌ 不支援創建 {table_name} 表")
                        return False
                else:
                    print(f"✅ {table_name} 表已存在")
                    
                    # 檢查表結構
                    columns = inspector.get_columns(table_name)
                    column_names = [col['name'] for col in columns]
                    
                    if table_name == 'ocr_menus':
                        expected_columns = ['ocr_menu_id', 'user_id', 'store_name', 'upload_time']
                        
                        missing_columns = [col for col in expected_columns if col not in column_names]
                        
                        if missing_columns:
                            print(f"⚠️  {table_name} 表缺少欄位: {missing_columns}")
                            return False
                        else:
                            print(f"✅ {table_name} 表結構正確")
                            
                    elif table_name == 'ocr_menu_items':
                        expected_columns = ['ocr_menu_item_id', 'ocr_menu_id', 'item_name', 'price_big', 'price_small', 'translated_desc']
                        
                        missing_columns = [col for col in expected_columns if col not in column_names]
                        
                        if missing_columns:
                            print(f"⚠️  {table_name} 表缺少欄位: {missing_columns}")
                            return False
                        else:
                            print(f"✅ {table_name} 表結構正確")
                            
                    elif table_name == 'order_summaries':
                        expected_columns = ['summary_id', 'order_id', 'ocr_menu_id', 'chinese_summary', 'user_language_summary', 'user_language', 'total_amount', 'created_at']
                        
                        missing_columns = [col for col in expected_columns if col not in column_names]
                        
                        if missing_columns:
                            print(f"⚠️  {table_name} 表缺少欄位: {missing_columns}")
                            return False
                        else:
                            print(f"✅ {table_name} 表結構正確")
            
            return True
            
    except Exception as e:
        print(f"❌ 創建資料表失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def verify_tables():
    """驗證資料表"""
    print("\n=== 驗證資料表 ===")
    
    try:
        from app import create_app
        from app.models import db, User, Store, Menu, MenuItem, Order, OrderItem, Language, OCRMenu, OCRMenuItem, OrderSummary
        
        app = create_app()
        
        with app.app_context():
            # 測試所有模型
            models = [
                ('User', User),
                ('Store', Store),
                ('Menu', Menu),
                ('MenuItem', MenuItem),
                ('Order', Order),
                ('OrderItem', OrderItem),
                ('Language', Language),
                ('OCRMenu', OCRMenu),
                ('OCRMenuItem', OCRMenuItem),
                ('OrderSummary', OrderSummary)
            ]
            
            for model_name, model in models:
                try:
                    # 嘗試查詢
                    count = model.query.count()
                    print(f"✅ {model_name}: {count} 筆資料")
                except Exception as e:
                    print(f"❌ {model_name}: {str(e)}")
            
            return True
            
    except Exception as e:
        print(f"❌ 驗證資料表失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函數"""
    print("創建缺失資料表")
    print("=" * 50)
    print(f"執行時間: {datetime.now()}")
    
    # 創建缺失的表
    if not create_missing_tables():
        print("\n❌ 創建資料表失敗")
        return False
    
    # 驗證表
    if not verify_tables():
        print("\n❌ 驗證資料表失敗")
        return False
    
    print("\n🎉 所有資料表創建和驗證成功！")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

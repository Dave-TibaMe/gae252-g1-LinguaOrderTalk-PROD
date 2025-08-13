#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修復資料庫外鍵約束

功能：
1. 修復 order_summaries 表的外鍵約束
2. 添加 CASCADE 刪除
3. 解決 order_id 不能為 NULL 的問題
"""

import os
import sys
from dotenv import load_dotenv

# 載入環境變數
load_dotenv('.env')

def fix_foreign_key_constraints():
    """修復資料庫外鍵約束"""
    print("=== 修復資料庫外鍵約束 ===")
    
    try:
        import pymysql
        
        connection = pymysql.connect(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', '3306')),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_DATABASE'),
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            # 1. 檢查當前的外鍵約束
            print("檢查當前的外鍵約束...")
            cursor.execute("""
                SELECT 
                    CONSTRAINT_NAME,
                    TABLE_NAME,
                    COLUMN_NAME,
                    REFERENCED_TABLE_NAME,
                    REFERENCED_COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'order_summaries'
                AND REFERENCED_TABLE_NAME IS NOT NULL
            """, (os.getenv('DB_DATABASE'),))
            
            constraints = cursor.fetchall()
            print(f"找到 {len(constraints)} 個外鍵約束:")
            for constraint in constraints:
                print(f"  - {constraint[0]}: {constraint[1]}.{constraint[2]} -> {constraint[3]}.{constraint[4]}")
            
            # 2. 刪除現有的外鍵約束
            print("\n刪除現有的外鍵約束...")
            for constraint in constraints:
                constraint_name = constraint[0]
                print(f"刪除約束: {constraint_name}")
                cursor.execute(f"ALTER TABLE order_summaries DROP FOREIGN KEY {constraint_name}")
            
            # 3. 重新添加外鍵約束，包含 CASCADE 刪除
            print("\n重新添加外鍵約束（包含 CASCADE 刪除）...")
            
            # 添加 order_id 外鍵約束
            cursor.execute("""
                ALTER TABLE order_summaries 
                ADD CONSTRAINT order_summaries_ibfk_1 
                FOREIGN KEY (order_id) REFERENCES orders (order_id) 
                ON DELETE CASCADE
            """)
            print("✅ 添加 order_id 外鍵約束成功")
            
            # 添加 ocr_menu_id 外鍵約束
            cursor.execute("""
                ALTER TABLE order_summaries 
                ADD CONSTRAINT order_summaries_ibfk_2 
                FOREIGN KEY (ocr_menu_id) REFERENCES ocr_menus (ocr_menu_id) 
                ON DELETE CASCADE
            """)
            print("✅ 添加 ocr_menu_id 外鍵約束成功")
            
            # 4. 驗證修復結果
            print("\n驗證修復結果...")
            cursor.execute("""
                SELECT 
                    CONSTRAINT_NAME,
                    TABLE_NAME,
                    COLUMN_NAME,
                    REFERENCED_TABLE_NAME,
                    REFERENCED_COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'order_summaries'
                AND REFERENCED_TABLE_NAME IS NOT NULL
            """, (os.getenv('DB_DATABASE'),))
            
            new_constraints = cursor.fetchall()
            print(f"修復後的外鍵約束:")
            for constraint in new_constraints:
                print(f"  - {constraint[0]}: {constraint[1]}.{constraint[2]} -> {constraint[3]}.{constraint[4]}")
            
            # 5. 提交變更
            connection.commit()
            print("\n✅ 外鍵約束修復完成！")
            
            return True
            
    except Exception as e:
        print(f"❌ 修復外鍵約束失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'connection' in locals():
            connection.close()

def main():
    """主函數"""
    print("修復資料庫外鍵約束")
    print("=" * 50)
    
    success = fix_foreign_key_constraints()
    
    if success:
        print("\n🎉 外鍵約束修復成功！")
        print("現在當刪除訂單或OCR菜單時，相關的訂單摘要會自動刪除。")
    else:
        print("\n❌ 外鍵約束修復失敗！")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

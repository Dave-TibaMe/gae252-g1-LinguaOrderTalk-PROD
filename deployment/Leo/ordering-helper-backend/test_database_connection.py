#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試新的 Cloud MySQL 資料庫連線和菜單查詢
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 設定新的資料庫連線參數
DB_CONFIG = {
    'host_test': '35.221.209.220',
    'host_prod': '34.81.245.147',
    'user': 'gae252g1usr',
    'password': 'gae252g1PSWD!',
    'database': 'gae252g1_db',
    'port': '3306'
}

def test_database_connection(host='test'):
    """測試資料庫連線"""
    try:
        # 選擇主機
        if host == 'test':
            db_host = DB_CONFIG['host_test']
        else:
            db_host = DB_CONFIG['host_prod']
        
        # 建立連線字串
        connection_string = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{db_host}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset=utf8mb4"
        
        print(f"正在連線到 {host} 資料庫...")
        print(f"主機: {db_host}")
        print(f"資料庫: {DB_CONFIG['database']}")
        print(f"使用者: {DB_CONFIG['user']}")
        
        # 建立引擎
        engine = create_engine(connection_string, echo=True)
        
        # 測試連線
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✅ 資料庫連線成功！")
            
            # 檢查資料庫版本
            version_result = connection.execute(text("SELECT VERSION()"))
            version = version_result.fetchone()[0]
            print(f"📊 資料庫版本: {version}")
            
            return engine
            
    except Exception as e:
        print(f"❌ 資料庫連線失敗: {str(e)}")
        return None

def test_store_query(engine, store_id=4):
    """測試店家查詢"""
    try:
        with engine.connect() as connection:
            print(f"\n🔍 查詢店家 ID {store_id}...")
            
            # 查詢店家資訊
            store_query = text("SELECT * FROM stores WHERE store_id = :store_id")
            store_result = connection.execute(store_query, {"store_id": store_id})
            store = store_result.fetchone()
            
            if store:
                print(f"✅ 找到店家: {store}")
            else:
                print(f"❌ 找不到店家 ID {store_id}")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ 店家查詢失敗: {str(e)}")
        return False

def test_menu_query(engine, store_id=4):
    """測試菜單查詢"""
    try:
        with engine.connect() as connection:
            print(f"\n🍽️ 查詢店家 ID {store_id} 的菜單...")
            
            # 查詢菜單
            menu_query = text("""
                SELECT m.menu_id, m.store_id, m.version, m.effective_date
                FROM menus m 
                WHERE m.store_id = :store_id
            """)
            menu_result = connection.execute(menu_query, {"store_id": store_id})
            menus = menu_result.fetchall()
            
            if menus:
                print(f"✅ 找到 {len(menus)} 個菜單:")
                for menu in menus:
                    print(f"  - 菜單 ID: {menu[0]}, 版本: {menu[2]}, 生效日期: {menu[3]}")
            else:
                print(f"❌ 找不到店家 ID {store_id} 的菜單")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ 菜單查詢失敗: {str(e)}")
        return False

def test_menu_items_query(engine, store_id=4):
    """測試菜單項目查詢"""
    try:
        with engine.connect() as connection:
            print(f"\n🍜 查詢店家 ID {store_id} 的菜單項目...")
            
            # 查詢菜單項目（透過菜單關聯）
            menu_items_query = text("""
                SELECT mi.menu_item_id, mi.item_name, mi.price_big, mi.price_small, m.store_id
                FROM menu_items mi
                JOIN menus m ON mi.menu_id = m.menu_id
                WHERE m.store_id = :store_id AND mi.price_small > 0
                ORDER BY mi.menu_item_id
            """)
            menu_items_result = connection.execute(menu_items_query, {"store_id": store_id})
            menu_items = menu_items_result.fetchall()
            
            if menu_items:
                print(f"✅ 找到 {len(menu_items)} 個菜單項目:")
                for item in menu_items:
                    print(f"  - {item[1]} (大份: {item[2]}, 小份: {item[3]})")
            else:
                print(f"❌ 找不到店家 ID {store_id} 的菜單項目")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ 菜單項目查詢失敗: {str(e)}")
        return False

def test_database_structure(engine):
    """測試資料庫結構"""
    try:
        with engine.connect() as connection:
            print(f"\n🏗️ 檢查資料庫結構...")
            
            # 檢查表格是否存在
            tables_query = text("SHOW TABLES")
            tables_result = connection.execute(tables_query)
            tables = [row[0] for row in tables_result.fetchall()]
            
            print(f"📋 資料庫中的表格:")
            for table in tables:
                print(f"  - {table}")
            
            # 檢查特定表格的結構
            important_tables = ['stores', 'menus', 'menu_items', 'menu_translations']
            for table in important_tables:
                if table in tables:
                    print(f"\n🔍 表格 {table} 的結構:")
                    structure_query = text(f"DESCRIBE {table}")
                    structure_result = connection.execute(structure_query)
                    columns = structure_result.fetchall()
                    for col in columns:
                        print(f"  - {col[0]} ({col[1]}) {col[2]} {col[3]} {col[4]}")
                else:
                    print(f"❌ 表格 {table} 不存在")
            
    except Exception as e:
        print(f"❌ 資料庫結構檢查失敗: {str(e)}")

def main():
    """主函數"""
    print("🚀 開始測試新的 Cloud MySQL 資料庫連線...")
    print("=" * 60)
    
    # 測試測試環境連線
    print("\n📡 測試環境連線測試")
    print("-" * 40)
    test_engine = test_database_connection('test')
    
    if test_engine:
        # 測試店家查詢
        if test_store_query(test_engine, 4):
            # 測試菜單查詢
            if test_menu_query(test_engine, 4):
                # 測試菜單項目查詢
                test_menu_items_query(test_engine, 4)
        
        # 檢查資料庫結構
        test_database_structure(test_engine)
        
        # 關閉連線
        test_engine.dispose()
    
    print("\n" + "=" * 60)
    print("🏁 測試完成")

if __name__ == "__main__":
    main()

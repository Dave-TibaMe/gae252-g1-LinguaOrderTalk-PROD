#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試修正後的菜單查詢 API
"""

import requests
import json

def test_menu_api():
    """測試菜單查詢 API"""
    
    # 設定環境變數（模擬 .env 檔案）
    import os
    os.environ['DB_HOST'] = '35.221.209.220'
    os.environ['DB_USER'] = 'gae252g1usr'
    os.environ['DB_PASSWORD'] = 'gae252g1PSWD!'
    os.environ['DB_DATABASE'] = 'gae252g1_db'
    os.environ['DB_PORT'] = '3306'
    
    print("🚀 開始測試修正後的菜單查詢 API...")
    print("=" * 60)
    
    # 測試店家 ID 4 的菜單查詢
    store_id = 4
    print(f"\n📋 測試店家 ID {store_id} 的菜單查詢")
    print("-" * 40)
    
    try:
        # 啟動 Flask 應用程式（在背景執行）
        import subprocess
        import time
        
        print("🔄 啟動 Flask 應用程式...")
        process = subprocess.Popen(['python3', 'run.py'], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE)
        
        # 等待應用程式啟動
        time.sleep(5)
        
        # 測試 API 端點
        api_url = f"http://localhost:8080/api/menu/{store_id}"
        print(f"🌐 測試 API: {api_url}")
        
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ API 呼叫成功！")
            print(f"📊 回應資料:")
            print(f"  - 店家 ID: {data.get('store_id')}")
            print(f"  - 使用者語言: {data.get('user_language')}")
            print(f"  - 菜單項目數量: {len(data.get('menu_items', []))}")
            print(f"  - 翻譯統計: {data.get('translation_stats')}")
            
            # 顯示前幾個菜單項目
            menu_items = data.get('menu_items', [])
            if menu_items:
                print(f"\n🍽️ 前 5 個菜單項目:")
                for i, item in enumerate(menu_items[:5]):
                    print(f"  {i+1}. {item.get('item_name')} - 小份: {item.get('price_small')} 元")
            
        else:
            print(f"❌ API 呼叫失敗: {response.status_code}")
            print(f"錯誤訊息: {response.text}")
        
        # 停止應用程式
        process.terminate()
        process.wait()
        
    except requests.exceptions.ConnectionError:
        print("❌ 無法連接到 Flask 應用程式")
        print("請確保應用程式正在執行，或者檢查埠號設定")
    except Exception as e:
        print(f"❌ 測試過程中發生錯誤: {str(e)}")
    
    print("\n" + "=" * 60)
    print("🏁 測試完成")

def test_direct_database_query():
    """直接測試資料庫查詢（不透過 Flask）"""
    
    print("\n🔍 直接測試資料庫查詢...")
    print("-" * 40)
    
    try:
        # 設定環境變數
        import os
        os.environ['DB_HOST'] = '35.221.209.220'
        os.environ['DB_USER'] = 'gae252g1usr'
        os.environ['DB_PASSWORD'] = 'gae252g1PSWD!'
        os.environ['DB_DATABASE'] = 'gae252g1_db'
        os.environ['DB_PORT'] = '3306'
        
        # 建立資料庫連線
        from sqlalchemy import create_engine, text
        
        connection_string = f"mysql+pymysql://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_DATABASE']}?charset=utf8mb4"
        engine = create_engine(connection_string)
        
        with engine.connect() as connection:
            # 測試修正後的查詢邏輯
            store_id = 4
            
            # 1. 查詢店家
            store_query = text("SELECT * FROM stores WHERE store_id = :store_id")
            store_result = connection.execute(store_query, {"store_id": store_id})
            store = store_result.fetchone()
            
            if store:
                print(f"✅ 找到店家: {store[1]} (ID: {store[0]})")
                
                # 2. 查詢菜單
                menu_query = text("SELECT * FROM menus WHERE store_id = :store_id")
                menu_result = connection.execute(menu_query, {"store_id": store_id})
                menus = menu_result.fetchall()
                
                if menus:
                    print(f"✅ 找到 {len(menus)} 個菜單")
                    
                    # 3. 查詢菜單項目
                    menu_ids = [menu[0] for menu in menus]
                    menu_items_query = text("""
                        SELECT mi.* FROM menu_items mi
                        WHERE mi.menu_id IN :menu_ids AND mi.price_small > 0
                        ORDER BY mi.menu_item_id
                    """)
                    menu_items_result = connection.execute(menu_items_query, {"menu_ids": tuple(menu_ids)})
                    menu_items = menu_items_result.fetchall()
                    
                    if menu_items:
                        print(f"✅ 找到 {len(menu_items)} 個菜單項目")
                        print(f"🍽️ 前 5 個菜單項目:")
                        for i, item in enumerate(menu_items[:5]):
                            print(f"  {i+1}. {item[2]} - 小份: {item[4]} 元")
                    else:
                        print("❌ 沒有找到菜單項目")
                else:
                    print("❌ 沒有找到菜單")
            else:
                print(f"❌ 找不到店家 ID {store_id}")
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ 直接資料庫查詢失敗: {str(e)}")

def main():
    """主函數"""
    print("🧪 菜單查詢 API 測試工具")
    print("=" * 60)
    
    # 直接測試資料庫查詢
    test_direct_database_query()
    
    # 測試 API 端點（需要 Flask 應用程式運行）
    # test_menu_api()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
檢查合作店家的菜單資料
"""

import os
import sys

# 設定環境變數
os.environ['DB_USER'] = 'gae252g1usr'
os.environ['DB_PASSWORD'] = 'gae252g1PSWD!'
os.environ['DB_HOST'] = '34.81.245.147'
os.environ['DB_DATABASE'] = 'gae252g1_db'

sys.path.append('.')

from app import create_app
from app.models import db, Store, Menu, MenuItem
from sqlalchemy import text

def check_store_menu():
    """檢查合作店家的菜單資料"""
    app = create_app()
    
    with app.app_context():
        try:
            print("🔧 開始檢查合作店家的菜單資料...")
            
            # 1. 檢查所有店家
            print("\n📋 檢查所有店家:")
            stores = Store.query.all()
            for store in stores:
                print(f"   store_id: {store.store_id}, name: '{store.store_name}', partner_level: {store.partner_level}")
            
            # 2. 檢查合作店家（partner_level > 0）
            print("\n📋 檢查合作店家:")
            partner_stores = Store.query.filter(Store.partner_level > 0).all()
            for store in partner_stores:
                print(f"   store_id: {store.store_id}, name: '{store.store_name}', partner_level: {store.partner_level}")
                
                # 檢查店家的菜單
                menus = Menu.query.filter(Menu.store_id == store.store_id).all()
                print(f"     菜單數量: {len(menus)}")
                
                for menu in menus:
                    print(f"     菜單ID: {menu.menu_id}, 版本: {menu.version}")
                    
                    # 檢查菜單項目
                    menu_items = MenuItem.query.filter(MenuItem.menu_id == menu.menu_id).all()
                    print(f"       菜單項目數量: {len(menu_items)}")
                    
                    for item in menu_items:
                        print(f"         項目ID: {item.menu_item_id}, 名稱: '{item.item_name}', 價格: {item.price_small}")
            
            # 3. 特別檢查食肆鍋（store_id=4）
            print("\n📋 特別檢查食肆鍋 (store_id=4):")
            store_4 = Store.query.get(4)
            if store_4:
                print(f"   店家資訊: store_id={store_4.store_id}, name='{store_4.store_name}', partner_level={store_4.partner_level}")
                
                # 檢查菜單
                menus = Menu.query.filter(Menu.store_id == 4).all()
                print(f"   菜單數量: {len(menus)}")
                
                if menus:
                    for menu in menus:
                        print(f"   菜單ID: {menu.menu_id}, 版本: {menu.version}")
                        
                        # 檢查菜單項目
                        menu_items = MenuItem.query.filter(MenuItem.menu_id == menu.menu_id).all()
                        print(f"     菜單項目數量: {len(menu_items)}")
                        
                        if menu_items:
                            for item in menu_items:
                                print(f"       項目ID: {item.menu_item_id}, 名稱: '{item.item_name}', 價格: {item.price_small}")
                        else:
                            print(f"     ❌ 沒有菜單項目")
                else:
                    print(f"   ❌ 沒有菜單")
            else:
                print(f"   ❌ 找不到 store_id=4 的店家")
            
            # 4. 檢查資料庫表格結構
            print("\n📋 檢查資料庫表格結構:")
            try:
                # 檢查 stores 表格
                result = db.session.execute(text("DESCRIBE stores"))
                print("   stores 表格結構:")
                for row in result:
                    print(f"     {row[0]}: {row[1]} {row[2]} {row[3]} {row[4]} {row[5]}")
                
                # 檢查 menus 表格
                result = db.session.execute(text("DESCRIBE menus"))
                print("   menus 表格結構:")
                for row in result:
                    print(f"     {row[0]}: {row[1]} {row[2]} {row[3]} {row[4]} {row[5]}")
                
                # 檢查 menu_items 表格
                result = db.session.execute(text("DESCRIBE menu_items"))
                print("   menu_items 表格結構:")
                for row in result:
                    print(f"     {row[0]}: {row[1]} {row[2]} {row[3]} {row[4]} {row[5]}")
                    
            except Exception as e:
                print(f"   ❌ 檢查表格結構失敗: {e}")
            
            # 5. 檢查資料數量
            print("\n📋 檢查資料數量:")
            try:
                stores_count = db.session.execute(text("SELECT COUNT(*) FROM stores")).scalar()
                menus_count = db.session.execute(text("SELECT COUNT(*) FROM menus")).scalar()
                menu_items_count = db.session.execute(text("SELECT COUNT(*) FROM menu_items")).scalar()
                
                print(f"   stores 表格記錄數: {stores_count}")
                print(f"   menus 表格記錄數: {menus_count}")
                print(f"   menu_items 表格記錄數: {menu_items_count}")
                
            except Exception as e:
                print(f"   ❌ 檢查資料數量失敗: {e}")
            
            print("\n🎉 檢查完成")
            
        except Exception as e:
            print(f"❌ 檢查失敗: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    check_store_menu()

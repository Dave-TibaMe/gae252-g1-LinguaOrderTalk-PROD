#!/usr/bin/env python3
"""
測試 OCR 菜單增強功能
- OCR 菜單存入 Cloud MySQL 資料庫的 ocr_menu_id 要含 store_id
- 翻譯後（使用者語言設定）的 OCR 菜單存入 Cloud MySQL 資料庫的 ocr-menu-translations
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, OCRMenu, OCRMenuItem, OCRMenuTranslation, Store, User, Language

def test_ocr_enhancements():
    """測試 OCR 菜單增強功能"""
    app = create_app()
    
    with app.app_context():
        print("🧪 開始測試 OCR 菜單增強功能...")
        
        # 1. 檢查資料庫表是否存在
        print("\n1. 檢查資料庫表結構...")
        try:
            # 檢查 ocr_menus 表是否有 store_id 欄位
            result = db.session.execute("DESCRIBE ocr_menus")
            columns = [row[0] for row in result]
            if 'store_id' in columns:
                print("✅ ocr_menus 表已包含 store_id 欄位")
            else:
                print("❌ ocr_menus 表缺少 store_id 欄位")
                return False
            
            # 檢查 ocr_menu_translations 表是否存在
            result = db.session.execute("SHOW TABLES LIKE 'ocr_menu_translations'")
            if result.fetchone():
                print("✅ ocr_menu_translations 表已存在")
            else:
                print("❌ ocr_menu_translations 表不存在")
                return False
                
        except Exception as e:
            print(f"❌ 檢查資料庫表結構失敗: {e}")
            return False
        
        # 2. 測試建立 OCR 菜單記錄
        print("\n2. 測試建立 OCR 菜單記錄...")
        try:
            # 確保有測試用的使用者和店家
            test_user = User.query.filter_by(line_user_id='test_user').first()
            if not test_user:
                test_user = User(line_user_id='test_user', preferred_lang='zh')
                db.session.add(test_user)
                db.session.flush()
            
            test_store = Store.query.filter_by(store_name='測試店家').first()
            if not test_store:
                test_store = Store(store_name='測試店家', partner_level=1)
                db.session.add(test_store)
                db.session.flush()
            
            # 建立 OCR 菜單記錄
            ocr_menu = OCRMenu(
                user_id=test_user.user_id,
                store_id=test_store.store_id,
                store_name='測試店家'
            )
            db.session.add(ocr_menu)
            db.session.flush()
            
            print(f"✅ 成功建立 OCR 菜單記錄: ocr_menu_id={ocr_menu.ocr_menu_id}, store_id={ocr_menu.store_id}")
            
            # 建立 OCR 菜單項目
            ocr_menu_item = OCRMenuItem(
                ocr_menu_id=ocr_menu.ocr_menu_id,
                item_name='測試菜名',
                price_small=100,
                price_big=120,
                translated_desc='Test Dish Name'
            )
            db.session.add(ocr_menu_item)
            db.session.flush()
            
            print(f"✅ 成功建立 OCR 菜單項目: ocr_menu_item_id={ocr_menu_item.ocr_menu_item_id}")
            
            # 建立 OCR 菜單翻譯
            ocr_menu_translation = OCRMenuTranslation(
                ocr_menu_item_id=ocr_menu_item.ocr_menu_item_id,
                lang_code='en',
                translated_name='Test Dish Name',
                translated_description='This is a test dish'
            )
            db.session.add(ocr_menu_translation)
            db.session.commit()
            
            print(f"✅ 成功建立 OCR 菜單翻譯: ocr_menu_translation_id={ocr_menu_translation.ocr_menu_translation_id}")
            
        except Exception as e:
            print(f"❌ 測試建立 OCR 菜單記錄失敗: {e}")
            db.session.rollback()
            return False
        
        # 3. 測試查詢 OCR 菜單翻譯
        print("\n3. 測試查詢 OCR 菜單翻譯...")
        try:
            from app.api.helpers import get_ocr_menu_translation_from_db, translate_ocr_menu_items_with_db_fallback
            
            # 測試單一翻譯查詢
            translation = get_ocr_menu_translation_from_db(ocr_menu_item.ocr_menu_item_id, 'en')
            if translation:
                print(f"✅ 成功查詢到翻譯: {translation.translated_name}")
            else:
                print("❌ 查詢翻譯失敗")
                return False
            
            # 測試批量翻譯
            ocr_menu_items = OCRMenuItem.query.filter_by(ocr_menu_id=ocr_menu.ocr_menu_id).all()
            translated_items = translate_ocr_menu_items_with_db_fallback(ocr_menu_items, 'en')
            
            if translated_items:
                print(f"✅ 成功批量翻譯 {len(translated_items)} 個項目")
                for item in translated_items:
                    print(f"   - {item['original_name']} -> {item['translated_name']} ({item['translation_source']})")
            else:
                print("❌ 批量翻譯失敗")
                return False
                
        except Exception as e:
            print(f"❌ 測試查詢 OCR 菜單翻譯失敗: {e}")
            return False
        
        # 4. 清理測試資料
        print("\n4. 清理測試資料...")
        try:
            db.session.delete(ocr_menu_translation)
            db.session.delete(ocr_menu_item)
            db.session.delete(ocr_menu)
            db.session.commit()
            print("✅ 測試資料清理完成")
        except Exception as e:
            print(f"⚠️ 清理測試資料失敗: {e}")
        
        print("\n🎉 OCR 菜單增強功能測試完成！")
        return True

if __name__ == '__main__':
    success = test_ocr_enhancements()
    sys.exit(0 if success else 1)

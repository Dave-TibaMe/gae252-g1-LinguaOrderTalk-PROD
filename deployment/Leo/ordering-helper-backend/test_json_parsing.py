#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 JSON 解析功能
"""

import os
import sys
import json

sys.path.append('.')

from app import create_app
from app.api.helpers import parse_gemini_json_response

def test_json_parsing():
    """測試 JSON 解析功能"""
    app = create_app()
    
    with app.app_context():
        try:
            print("🔧 開始測試 JSON 解析功能...")
            
            # 測試案例1: 正常的 JSON
            print("\n📋 測試案例1: 正常 JSON")
            normal_json = '''
            {
                "success": true,
                "menu_items": [
                    {
                        "original_name": "招牌金湯酸菜",
                        "translated_name": "Signature Golden Soup Pickled Vegetables",
                        "price": 68
                    }
                ],
                "store_info": {
                    "name": "食肆鍋",
                    "address": null,
                    "phone": null
                }
            }
            '''
            
            try:
                result = parse_gemini_json_response(normal_json)
                print("✅ 正常 JSON 解析成功")
                print(f"   成功狀態: {result.get('success')}")
                print(f"   菜單項目數: {len(result.get('menu_items', []))}")
            except Exception as e:
                print(f"❌ 正常 JSON 解析失敗: {e}")
            
            # 測試案例2: 有尾隨逗號的 JSON
            print("\n📋 測試案例2: 有尾隨逗號的 JSON")
            trailing_comma_json = '''
            {
                "success": true,
                "menu_items": [
                    {
                        "original_name": "招牌金湯酸菜",
                        "translated_name": "Signature Golden Soup Pickled Vegetables",
                        "price": 68,
                    },
                ],
                "store_info": {
                    "name": "食肆鍋",
                    "address": null,
                    "phone": null,
                },
            }
            '''
            
            try:
                result = parse_gemini_json_response(trailing_comma_json)
                print("✅ 尾隨逗號 JSON 解析成功")
                print(f"   成功狀態: {result.get('success')}")
                print(f"   菜單項目數: {len(result.get('menu_items', []))}")
            except Exception as e:
                print(f"❌ 尾隨逗號 JSON 解析失敗: {e}")
            
            # 測試案例3: 有引號問題的 JSON
            print("\n📋 測試案例3: 有引號問題的 JSON")
            quote_issue_json = '''
            {
                "success": true,
                "menu_items": [
                    {
                        "original_name": "招牌金湯酸菜",
                        "translated_name": "Signature Golden Soup Pickled Vegetables",
                        "price": 68
                    }
                ],
                "store_info": {
                    "name": "食肆鍋",
                    "address": null,
                    "phone": null
                }
            }
            '''
            
            try:
                result = parse_gemini_json_response(quote_issue_json)
                print("✅ 引號問題 JSON 解析成功")
                print(f"   成功狀態: {result.get('success')}")
                print(f"   菜單項目數: {len(result.get('menu_items', []))}")
            except Exception as e:
                print(f"❌ 引號問題 JSON 解析失敗: {e}")
            
            # 測試案例4: 模擬 Gemini 長回應（包含額外文字）
            print("\n📋 測試案例4: 模擬 Gemini 長回應")
            long_response = '''
            我已經分析了這張菜單圖片，以下是辨識結果：

            {
                "success": true,
                "menu_items": [
                    {
                        "original_name": "招牌金湯酸菜",
                        "translated_name": "Signature Golden Soup Pickled Vegetables",
                        "price": 68
                    },
                    {
                        "original_name": "白濃雞湯",
                        "translated_name": "White Chicken Soup",
                        "price": 49
                    }
                ],
                "store_info": {
                    "name": "食肆鍋",
                    "address": null,
                    "phone": null
                }
            }

            以上是完整的菜單辨識結果，包含了所有可見的菜單項目。
            '''
            
            try:
                result = parse_gemini_json_response(long_response)
                print("✅ 長回應 JSON 解析成功")
                print(f"   成功狀態: {result.get('success')}")
                print(f"   菜單項目數: {len(result.get('menu_items', []))}")
            except Exception as e:
                print(f"❌ 長回應 JSON 解析失敗: {e}")
            
            # 測試案例5: 格式錯誤的 JSON（模擬實際錯誤）
            print("\n📋 測試案例5: 格式錯誤的 JSON")
            malformed_json = '''
            {
                "success": true,
                "menu_items": [
                    {
                        "original_name": "招牌金湯酸菜",
                        "translated_name": "Signature Golden Soup Pickled Vegetables",
                        "price": 68
                    }
                    {
                        "original_name": "白濃雞湯",
                        "translated_name": "White Chicken Soup",
                        "price": 49
                    }
                ],
                "store_info": {
                    "name": "食肆鍋",
                    "address": null,
                    "phone": null
                }
            }
            '''
            
            try:
                result = parse_gemini_json_response(malformed_json)
                print("✅ 格式錯誤 JSON 解析成功")
                print(f"   成功狀態: {result.get('success')}")
                print(f"   菜單項目數: {len(result.get('menu_items', []))}")
            except Exception as e:
                print(f"❌ 格式錯誤 JSON 解析失敗: {e}")
            
            print("\n🎉 JSON 解析功能測試完成")
            
        except Exception as e:
            print(f"❌ 測試失敗: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_json_parsing()

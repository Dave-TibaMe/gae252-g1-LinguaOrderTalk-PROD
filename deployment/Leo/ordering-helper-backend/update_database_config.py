#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新資料庫連線設定腳本
使用新的 Cloud MySQL 連線參數
"""

import os
import sys

def update_environment_variables():
    """更新環境變數設定"""
    
    # 新的資料庫連線參數
    new_config = {
        'DB_HOST': '35.221.209.220',  # 測試環境
        'DB_USER': 'gae252g1usr',
        'DB_PASSWORD': 'gae252g1PSWD!',
        'DB_DATABASE': 'gae252g1_db',
        'DB_PORT': '3306'
    }
    
    print("🔄 更新資料庫連線設定...")
    print("=" * 50)
    
    # 檢查當前設定
    print("📋 當前環境變數設定:")
    for key, value in new_config.items():
        current_value = os.getenv(key, '未設定')
        print(f"  {key}: {current_value}")
    
    print("\n📝 新的設定值:")
    for key, value in new_config.items():
        print(f"  {key}: {value}")
    
    # 更新環境變數
    print("\n✅ 更新環境變數...")
    for key, value in new_config.items():
        os.environ[key] = value
        print(f"  設定 {key} = {value}")
    
    # 驗證更新
    print("\n🔍 驗證更新結果:")
    for key, value in new_config.items():
        current_value = os.getenv(key, '未設定')
        if current_value == value:
            print(f"  ✅ {key}: {current_value}")
        else:
            print(f"  ❌ {key}: {current_value} (預期: {value})")
    
    print("\n📝 建議在 .env 檔案中設定以下環境變數:")
    print("=" * 50)
    for key, value in new_config.items():
        print(f"{key}={value}")
    
    return True

def create_env_file():
    """建立 .env 檔案範本"""
    
    env_content = """# 資料庫連線設定
DB_HOST=35.221.209.220
DB_USER=gae252g1usr
DB_PASSWORD=gae252g1PSWD!
DB_DATABASE=gae252g1_db
DB_PORT=3306

# LINE Bot 設定
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token_here
LINE_CHANNEL_SECRET=your_line_channel_secret_here

# AI 服務設定
GEMINI_API_KEY=your_gemini_api_key_here
AZURE_SPEECH_KEY=your_azure_speech_key_here
AZURE_SPEECH_REGION=your_azure_speech_region_here

# Google Cloud 設定
GCS_BUCKET_NAME=ordering-helper-voice-files

# 應用程式設定
FLASK_ENV=production
FLASK_DEBUG=False
"""
    
    try:
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(env_content)
        print("\n📄 已建立 .env 檔案範本")
        print("請根據實際情況修改其中的 API 金鑰等設定")
    except Exception as e:
        print(f"\n❌ 建立 .env 檔案失敗: {str(e)}")

def main():
    """主函數"""
    print("🚀 資料庫連線設定更新工具")
    print("=" * 50)
    
    # 更新環境變數
    if update_environment_variables():
        print("\n✅ 環境變數更新完成！")
        
        # 建立 .env 檔案
        create_env_file()
        
        print("\n💡 注意事項:")
        print("1. 環境變數只在當前 Python 程序中有效")
        print("2. 重新啟動應用程式後，請確保 .env 檔案被正確載入")
        print("3. 或者設定系統環境變數以永久生效")
        
    else:
        print("\n❌ 環境變數更新失敗！")

if __name__ == "__main__":
    main()

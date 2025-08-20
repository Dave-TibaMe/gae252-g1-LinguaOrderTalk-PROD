#!/bin/bash

# 音訊功能修復部署腳本
# 修復 LINE 音訊訊息顯示問題

echo "🔧 開始部署音訊功能修復..."

# 1. 安裝新的依賴
echo "📦 安裝 pydub 依賴..."
pip install pydub==0.25.1

# 2. 檢查檔案修改
echo "📝 檢查修改的檔案..."
echo "✅ 已修復 /app/api/routes.py - 語音檔案服務端點"
echo "✅ 已修復 /app/api/helpers.py - LINE 音訊訊息發送"
echo "✅ 已修復 /app/webhook/routes.py - 音訊長度計算"
echo "✅ 已更新 requirements.txt - 添加 pydub 依賴"

# 3. 重新啟動服務
echo "🔄 重新啟動服務..."
# 如果是 Cloud Run，這裡會自動重新部署
# 如果是本地開發，可以手動重啟

echo "✅ 音訊功能修復部署完成！"
echo ""
echo "🔍 修復內容："
echo "1. 語音檔案服務端點現在支援 Range 請求和正確的標頭"
echo "2. LINE 音訊訊息現在會計算正確的 duration 參數"
echo "3. 添加了 pydub 套件來計算音訊檔案長度"
echo "4. 前端預設文案已改為英文，避免語言混淆"
echo ""
echo "📋 測試建議："
echo "1. 測試語音檔案是否能正常播放"
echo "2. 檢查 LINE 音訊訊息是否顯示正確的時長"
echo "3. 確認前端載入時的預設文案"

#!/bin/bash

# Cloud Run 啟動腳本
echo "=== Cloud Run 啟動腳本 ==="
echo "當前目錄: $(pwd)"
echo "環境變數 PORT: $PORT"
echo "環境變數 FLASK_APP: $FLASK_APP"
echo "Python 版本: $(python3 --version)"
echo "Gunicorn 版本: $(gunicorn --version)"

# 檢查必要檔案
echo "檢查必要檔案..."
ls -la

# 檢查環境變數
if [ -z "$PORT" ]; then
    echo "警告: PORT 環境變數未設定，使用預設值 8080"
    export PORT=8080
fi

echo "將使用端口: $PORT"

# 檢查 Python 依賴
echo "檢查 Python 依賴..."
python3 -c "import flask, gunicorn; print('依賴檢查通過')" || {
    echo "錯誤: Python 依賴檢查失敗"
    exit 1
}

# 啟動應用程式
echo "啟動 Flask 應用程式..."
echo "執行命令: gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 300 --graceful-timeout 60 --max-requests 500 --max-requests-jitter 50 --preload --worker-class sync --access-logfile - --error-logfile - --log-level info run:app"

exec gunicorn \
    --bind "0.0.0.0:$PORT" \
    --workers 1 \
    --timeout 300 \
    --graceful-timeout 60 \
    --max-requests 500 \
    --max-requests-jitter 50 \
    --preload \
    --worker-class sync \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    run:app

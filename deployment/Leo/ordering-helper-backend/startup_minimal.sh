#!/bin/bash

# 最小化 Cloud Run 啟動腳本
echo "=== 最小化 Cloud Run 啟動腳本 ==="
echo "當前目錄: $(pwd)"
echo "環境變數 PORT: $PORT"

# 設定預設端口
PORT=${PORT:-8080}
echo "使用端口: $PORT"

# 啟動應用程式
echo "啟動 Flask 應用程式..."
exec gunicorn \
    --bind "0.0.0.0:$PORT" \
    --workers 1 \
    --timeout 300 \
    --graceful-timeout 60 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --preload \
    --worker-class sync \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --capture-output \
    run:app

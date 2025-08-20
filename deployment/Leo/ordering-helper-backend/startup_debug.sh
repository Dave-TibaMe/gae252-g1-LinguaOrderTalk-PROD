#!/bin/bash

# Cloud Run 調試啟動腳本
echo "=== Cloud Run 調試啟動腳本 ==="
echo "當前目錄: $(pwd)"
echo "環境變數 PORT: $PORT"

# 設定預設端口
if [ -z "$PORT" ]; then
    export PORT=8080
    echo "使用預設端口: $PORT"
else
    echo "使用環境變數端口: $PORT"
fi

# 檢查必要檔案
echo "檢查必要檔案..."
if [ ! -f "run.py" ]; then
    echo "錯誤: run.py 不存在"
    exit 1
fi

if [ ! -f "app/__init__.py" ]; then
    echo "錯誤: app/__init__.py 不存在"
    exit 1
fi

echo "✓ 必要檔案檢查通過"

# 檢查 Python 環境
echo "檢查 Python 環境..."
python3 --version
pip3 list | grep -E "(Flask|gunicorn)"

# 檢查環境變數
echo "檢查關鍵環境變數..."
key_vars=("DB_USER" "DB_PASSWORD" "DB_HOST" "DB_DATABASE" "LINE_CHANNEL_ACCESS_TOKEN" "LINE_CHANNEL_SECRET")
for var in "${key_vars[@]}"; do
    if [ -n "${!var}" ]; then
        echo "✓ $var is set"
    else
        echo "⚠️ $var is not set"
    fi
done

# 測試 Python 模組導入
echo "測試 Python 模組導入..."
python3 -c "
import sys
print('Python 路徑:', sys.path)

try:
    print('測試導入 app 模組...')
    from app import create_app
    print('✓ app.create_app 導入成功')
    
    print('測試創建應用程式...')
    app = create_app()
    print('✓ 應用程式創建成功')
    
    print('測試 run.py 中的 app 變數...')
    from run import app as run_app
    print('✓ run.py 中的 app 變數可用')
    
except Exception as e:
    print(f'✗ 導入錯誤: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "Python 模組測試失敗"
    exit 1
fi

echo "✓ Python 模組測試通過"

# 啟動應用程式
echo "啟動 Flask 應用程式在端口 $PORT..."
echo "使用 gunicorn 啟動服務..."

# 使用調試模式啟動，捕獲詳細錯誤
exec gunicorn \
    --bind "0.0.0.0:$PORT" \
    --workers 1 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level debug \
    --preload \
    run:app

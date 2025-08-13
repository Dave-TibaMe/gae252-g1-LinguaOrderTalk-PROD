# =============================================================================
# 檔案名稱：run.py
# 功能描述：Flask 應用程式的入口點，負責啟動整個點餐小幫手後端服務
# 主要職責：
# - 載入環境變數設定
# - 建立 Flask 應用程式實例
# - 啟動開發伺服器
# =============================================================================

from app import create_app
from dotenv import load_dotenv

# =============================================================================
# 環境變數載入區塊
# 功能：在建立 Flask 應用程式之前，先載入 .env 檔案中的環境變數
# 包含：資料庫連線、API 金鑰、LINE Bot 設定等
# =============================================================================
import os

# 嘗試載入環境變數文件，如果不存在則忽略
env_file = 'notebook.env'
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"Loaded environment variables from {env_file}")
else:
    # 在 Cloud Run 環境中，環境變數應該已經設定好了
    print("Environment file not found, using system environment variables")

# 調試：檢查關鍵環境變數是否存在
key_vars = ['DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_DATABASE', 'LINE_CHANNEL_ACCESS_TOKEN', 'LINE_CHANNEL_SECRET']
for var in key_vars:
    if os.getenv(var):
        print(f"✓ {var} is set")
    else:
        print(f"✗ {var} is not set")

# 檢查 PORT 環境變數
port = int(os.environ.get('PORT', 8080))
print(f"Server will listen on port: {port}")

# =============================================================================
# 應用程式建立區塊
# 功能：呼叫 app 套件的 create_app() 函數來建立 Flask 應用程式
# 回傳：設定完整的 Flask 應用程式實例
# =============================================================================
app = create_app()

# =============================================================================
# 應用程式啟動區塊
# 功能：當直接執行此檔案時，啟動 Flask 開發伺服器
# 設定：
# - debug=False：關閉除錯模式，適合生產環境
# - port=PORT：使用環境變數指定的埠號，Cloud Run 預設為 8080
# 注意：正式上線時務必關閉 debug 模式
# =============================================================================
if __name__ == '__main__':
    # Cloud Run 需要監聽 PORT=8080
    print(f"Starting Flask application on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)


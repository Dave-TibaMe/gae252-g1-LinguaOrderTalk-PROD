# =============================================================================
# 檔案名稱：app/__init__.py
# 功能描述：Flask 應用程式初始化
# 主要職責：
# - 建立 Flask 應用程式實例
# - 設定資料庫連線
# - 註冊 Blueprint
# - 設定錯誤處理
# - 設定 CORS 支援
# =============================================================================

from flask import Flask, jsonify
from flask_cors import CORS
from .models import db
from .errors import register_error_handlers
from .admin.routes import admin_bp
from .api.routes import api_bp
from .webhook.routes import webhook_bp
import os
import datetime

def create_app():
    """建立 Flask 應用程式"""
    app = Flask(__name__)
    
    # 設定 CORS
    # 允許來自 Azure 靜態網頁的跨來源請求
    allowed_origins = [
        "https://green-beach-0f9762500.1.azurestaticapps.net",
        "https://liff.line.me",  # LINE LIFF 域名
        "https://liff.line.me:443",  # LINE LIFF 域名 (HTTPS)
        "http://localhost:3000",  # 本地開發
        "http://localhost:8080",  # 本地開發
        "http://127.0.0.1:3000",  # 本地開發
        "http://127.0.0.1:8080"   # 本地開發
    ]
    
    # 更完整的 CORS 設定
    CORS(app, 
         resources={r"/api/*": {"origins": "*"}},
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["*"],  # 允許所有 headers
         supports_credentials=False,
         max_age=3600)
    
    # 設定 PORT 配置 - 確保 Cloud Run 能正確綁定端口
    app.config['PORT'] = int(os.environ.get('PORT', 8080))
    
    # 設定資料庫 - 使用 try-catch 避免啟動失敗
    try:
        # 從個別環境變數構建資料庫 URL
        db_username = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST')
        db_name = os.getenv('DB_DATABASE')
        
        if all([db_username, db_password, db_host, db_name]):
            # 使用 MySQL 連線，添加 SSL 參數
            database_url = f"mysql+pymysql://{db_username}:{db_password}@{db_host}/{db_name}?ssl={{'ssl': {{}}}}&ssl_verify_cert=false"
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url
            print(f"✓ 使用 MySQL 資料庫: {db_host}/{db_name}")
        else:
            # 回退到 SQLite
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
            print("⚠️ 使用 SQLite 資料庫 (開發模式)")
        
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # 初始化資料庫
        db.init_app(app)
        print("✓ 資料庫初始化成功")
        
    except Exception as e:
        print(f"⚠️ 資料庫初始化失敗: {e}")
        print("應用程式將在沒有資料庫的情況下啟動")
        # 設定一個簡單的 SQLite 配置作為後備
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(app)
    
    # 註冊 Blueprint
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(webhook_bp, url_prefix='/webhook')
    
    # 註冊錯誤處理
    register_error_handlers(app)
    
    # 簡單的測試頁面
    @app.route('/test')
    def test_page():
        """測試頁面"""
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>後端 API 測試</title>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .endpoint { background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 5px; }
                .method { color: #007bff; font-weight: bold; }
                .url { color: #28a745; }
            </style>
        </head>
        <body>
            <h1>點餐小幫手後端 API</h1>
            <p>這是一個測試頁面，顯示可用的 API 端點：</p>
            
            <div class="endpoint">
                <span class="method">GET</span> <span class="url">/api/test</span> - API 連線測試
            </div>
            
            <div class="endpoint">
                <span class="method">GET</span> <span class="url">/api/stores/{store_id}</span> - 取得店家資訊
            </div>
            
            <div class="endpoint">
                <span class="method">GET</span> <span class="url">/api/menu/{store_id}</span> - 取得店家菜單
            </div>
            
            <div class="endpoint">
                <span class="method">POST</span> <span class="url">/api/menu/process-ocr</span> - 處理菜單圖片 OCR
            </div>
            
            <div class="endpoint">
                <span class="method">POST</span> <span class="url">/api/orders</span> - 建立訂單
            </div>
            
            <div class="endpoint">
                <span class="method">POST</span> <span class="url">/api/orders/temp</span> - 建立臨時訂單
            </div>
            
            <p><strong>注意：</strong> LIFF 前端獨立部署在 Azure 靜態網頁，請使用對應的 LIFF URL。</p>
        </body>
        </html>
        '''
    
    # 根路徑處理
    @app.route('/')
    def root():
        """根路徑處理"""
        from .api.routes import handle_root_path
        return handle_root_path()
    
    # 健康檢查端點 - Cloud Run 需要這個來確認服務狀態
    @app.route('/health')
    def health_check():
        """健康檢查端點"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'port': app.config.get('PORT', 8080)
        }), 200
    
    return app




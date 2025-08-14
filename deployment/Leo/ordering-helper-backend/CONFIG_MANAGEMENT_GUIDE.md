# 配置管理指南

## 🎯 **問題分析**

你的程式碼中還有以下寫死並分散在各處的環境變數：

### **📋 發現的問題**

#### **1. 資料庫配置分散**
- `config/cloud_mysql_config.py` - 資料庫連線池設定
- `app/__init__.py` - 資料庫基本設定
- `fix_foreign_key_constraints.py` - 資料庫修復腳本

#### **2. API 金鑰分散**
- `app/api/helpers.py` - Gemini API, Azure Speech
- `app/webhook/routes.py` - LINE Bot 配置
- `app/api/routes.py` - 各種 API 金鑰檢查

#### **3. Google Cloud 配置**
- `app/api/helpers.py` - GCS Bucket 名稱

#### **4. 遺漏的 BASE_URL**
- `app/api/helpers.py` 中還有 3 處舊的 BASE_URL 寫法

## 🛠️ **解決方案**

### **1. 建立統一的配置管理系統**

已建立 `app/config/settings.py`，提供：

```python
from app.config import config

# 資料庫配置
db_url = config.get_database_url()

# API 金鑰
gemini_key = config.GEMINI_API_KEY
line_token = config.LINE_CHANNEL_ACCESS_TOKEN

# 環境檢測
if config.is_production():
    print("生產環境")

# 配置驗證
missing = config.validate_required_configs()
```

### **2. 支援的配置類型**

#### **資料庫配置**
```python
# 基本連線
config.DB_USER
config.DB_PASSWORD
config.DB_HOST
config.DB_DATABASE
config.DB_PORT

# SSL 設定
config.DB_SSL_CA
config.DB_SSL_CERT
config.DB_SSL_KEY

# 連線池設定
config.DB_POOL_SIZE
config.DB_MAX_OVERFLOW
config.DB_POOL_TIMEOUT
config.DB_POOL_RECYCLE

# 超時設定
config.DB_CONNECT_TIMEOUT
config.DB_READ_TIMEOUT
config.DB_WRITE_TIMEOUT
```

#### **LINE Bot 配置**
```python
config.LINE_CHANNEL_ACCESS_TOKEN
config.LINE_CHANNEL_SECRET
```

#### **AI 服務配置**
```python
# Google Gemini
config.GEMINI_API_KEY

# Azure Speech
config.AZURE_SPEECH_KEY
config.AZURE_SPEECH_REGION
```

#### **Google Cloud 配置**
```python
config.GCS_BUCKET_NAME
```

#### **應用程式配置**
```python
config.FLASK_ENV
config.FLASK_DEBUG
```

### **3. 配置驗證功能**

```python
# 檢查缺少的配置
missing_configs = config.validate_required_configs()

if missing_configs:
    print("缺少以下配置：")
    for category, configs in missing_configs.items():
        print(f"  {category}: {configs}")
```

### **4. 配置摘要功能**

```python
# 取得配置摘要（用於除錯）
summary = config.get_config_summary()
print(f"環境: {summary['environment']}")
print(f"資料庫: {summary['database']}")
print(f"服務狀態: {summary['services']}")
```

## 📝 **使用範例**

### **原本的寫法（不推薦）**
```python
# 分散在各處
gemini_key = os.getenv('GEMINI_API_KEY')
line_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
bucket_name = os.getenv('GCS_BUCKET_NAME', 'ordering-helper-voice-files')
pool_size = int(os.getenv('DB_POOL_SIZE', '10'))
```

### **新的寫法（推薦）**
```python
from app.config import config

# 統一配置管理
gemini_key = config.GEMINI_API_KEY
line_token = config.LINE_CHANNEL_ACCESS_TOKEN
bucket_name = config.GCS_BUCKET_NAME
pool_size = config.DB_POOL_SIZE
```

## 🔄 **下一步行動**

### **待完成的任務**

1. **更新資料庫配置**
   - 修改 `config/cloud_mysql_config.py` 使用新的配置系統
   - 修改 `app/__init__.py` 使用新的配置系統

2. **更新 API 配置**
   - 修改 `app/api/helpers.py` 使用新的配置系統
   - 修改 `app/webhook/routes.py` 使用新的配置系統
   - 修改 `app/api/routes.py` 使用新的配置系統

3. **清理遺漏的 BASE_URL**
   - 更新 `app/api/helpers.py` 中剩餘的 3 處 BASE_URL

4. **更新修復腳本**
   - 修改 `fix_foreign_key_constraints.py` 使用新的配置系統

## 🎉 **優點**

1. **集中管理** - 所有配置都在一個地方
2. **類型安全** - 提供明確的 API 介面
3. **驗證功能** - 自動檢查缺少的配置
4. **環境支援** - 支援開發/生產環境切換
5. **除錯友好** - 提供配置摘要功能
6. **向後相容** - 不影響現有功能

## 🚀 **建議**

1. **優先更新**：先更新最常用的配置（API 金鑰）
2. **逐步遷移**：一次更新一個模組，避免大規模改動
3. **測試驗證**：每次更新後都要測試功能
4. **文檔更新**：更新相關的部署文檔

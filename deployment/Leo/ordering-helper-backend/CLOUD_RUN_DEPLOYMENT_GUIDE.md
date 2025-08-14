# Cloud Run 部署指南

## 🔍 **問題分析**

根據錯誤日誌分析，Cloud Run 發生了兩個主要問題：

### **問題1：資料庫表不存在**
```
sqlalchemy.exc.ProgrammingError: (pymysql.err.ProgrammingError) (1146, "Table 'gae252g1_db.gemini_processing' doesn't exist")
```

### **問題2：變數未定義**
```
NameError: name 'app' is not defined
```

## 🛠️ **修復方案**

### **1. 修復代碼問題**

#### **修復 app 變數問題**
在 `app/api/routes.py` 中：
```python
# 修改前
from flask import Blueprint, jsonify, request, send_file

# 修改後
from flask import Blueprint, jsonify, request, send_file, current_app

# 修改前
'details': str(e) if app.debug else '請稍後再試'

# 修改後
'details': str(e) if current_app.debug else '請稍後再試'
```

#### **修復資料庫模型**
在 `app/models.py` 中，修改 `StoreTranslation` 模型：
```python
class StoreTranslation(db.Model):
    __tablename__ = 'store_translations'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.store_id'), nullable=False)
    language_code = db.Column(db.String(5), db.ForeignKey('languages.lang_code'), nullable=False)
    description = db.Column(db.Text)  # 翻譯後的店家簡介
    translated_summary = db.Column(db.Text)  # 翻譯後的評論摘要
```

### **2. 資料庫相容性修復**

運行修復腳本：
```bash
python3 tools/fix_database_compatibility.py
```

### **3. Cloud Run 環境變數設定**

確保 Cloud Run 設定以下環境變數：

#### **必要環境變數**
```
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your_mysql_host
DB_DATABASE=gae252g1_db
```

#### **可選環境變數**
```
GEMINI_API_KEY=your_gemini_api_key
LINE_CHANNEL_ACCESS_TOKEN=your_line_token
LINE_CHANNEL_SECRET=your_line_secret
AZURE_SPEECH_KEY=your_azure_speech_key
AZURE_SPEECH_REGION=your_azure_region
```

### **4. 部署步驟**

#### **步驟1：檢查配置**
```bash
python3 tools/check_cloud_run_config.py
```

#### **步驟2：修復資料庫**
```bash
python3 tools/fix_database_compatibility.py
```

#### **步驟3：提交修復**
```bash
git add .
git commit -m "🔧 修復 Cloud Run 部署問題 - 修復 app 變數和資料庫模型相容性"
git push origin main
```

#### **步驟4：部署到 Cloud Run**
```bash
gcloud run deploy ordering-helper-backend \
  --source . \
  --platform managed \
  --region asia-east1 \
  --allow-unauthenticated \
  --set-env-vars DB_USER=your_db_user,DB_PASSWORD=your_db_password,DB_HOST=your_mysql_host,DB_DATABASE=gae252g1_db
```

## 📋 **完整使用者流程支援**

修復後的系統將完整支援 LINE Bot 外國旅客點餐流程：

### **1. 加入與語言設定**
- ✅ 掃描 QR Code 加入 LINE Bot
- ✅ 選擇介面語言（英文、日文、韓文等）

### **2. 店家探索**
- ✅ GPS 定位鄰近店家
- ✅ 顯示翻譯後的店家資訊
- ✅ 合作店家標籤（VIP／合作／非合作）

### **3. 選擇店家 → LIFF 點餐**
- ✅ 合作店家：從資料庫撈取結構化菜單
- ✅ 非合作店家：拍照上傳 → Gemini OCR → 動態生成菜單

### **4. 點餐與確認**
- ✅ LIFF 介面選擇品項數量
- ✅ 購物車功能
- ✅ 訂單明細確認

### **5. 生成中文語音檔**
- ✅ 品項轉回原始中文菜名
- ✅ TTS API 合成中文語音
- ✅ 可調語速版本

### **6. 回傳 LINE Bot**
- ✅ 訂單文字摘要（使用者語言）
- ✅ 中文語音檔及重播/語速控制

### **7. 現場點餐**
- ✅ 櫃檯播放中文語音點餐

## 🔧 **故障排除**

### **如果仍然出現資料庫錯誤**
1. 檢查 Cloud Run 環境變數是否正確設定
2. 確認資料庫連接是否正常
3. 運行 `tools/check_database.py` 檢查資料庫狀態

### **如果出現其他錯誤**
1. 檢查 Cloud Run 日誌：`gcloud logs read --service=ordering-helper-backend`
2. 確認所有依賴套件都已安裝
3. 檢查 API 金鑰是否正確設定

## 📊 **監控與維護**

### **定期檢查項目**
- 資料庫連接狀態
- API 金鑰有效性
- Cloud Run 服務狀態
- 錯誤日誌分析

### **備份策略**
- 定期備份資料庫
- 保存重要配置檔案
- 記錄部署版本

---

**注意：** 部署前請確保所有環境變數都已正確設定，特別是資料庫連接相關的變數。 
#!/bin/bash

# Cloud Run 修復版部署腳本
echo "=== Cloud Run 修復版部署腳本 ==="

# 設定變數
PROJECT_ID="solid-heaven-466011-d1"
SERVICE_NAME="ordering-helper-backend"
REGION="asia-east1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "專案 ID: $PROJECT_ID"
echo "服務名稱: $SERVICE_NAME"
echo "地區: $REGION"
echo "映像名稱: $IMAGE_NAME"

# 檢查 gcloud 是否已登入
echo "檢查 gcloud 登入狀態..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "錯誤: 請先登入 gcloud"
    echo "執行: gcloud auth login"
    exit 1
fi

# 設定專案
echo "設定專案..."
gcloud config set project $PROJECT_ID

# 本地測試
echo "執行本地測試..."
python3 test_startup.py
if [ $? -ne 0 ]; then
    echo "❌ 本地測試失敗，請檢查問題後再部署"
    exit 1
fi
echo "✅ 本地測試通過"

# 建置 Docker 映像
echo "建置 Docker 映像..."
echo "使用 Dockerfile.minimal 進行建置..."

# 建置映像
docker build -f Dockerfile.minimal -t $IMAGE_NAME .

if [ $? -ne 0 ]; then
    echo "❌ Docker 建置失敗"
    exit 1
fi

echo "✅ Docker 映像建置成功"

# 推送映像到 Google Container Registry
echo "推送映像到 GCR..."
docker push $IMAGE_NAME

if [ $? -ne 0 ]; then
    echo "❌ 映像推送失敗"
    exit 1
fi

echo "✅ 映像推送成功"

# 部署到 Cloud Run
echo "部署到 Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --port 8080 \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300 \
    --concurrency 80 \
    --set-env-vars "PORT=8080" \
    --max-instances 10

if [ $? -ne 0 ]; then
    echo "❌ Cloud Run 部署失敗"
    exit 1
fi

echo "✅ Cloud Run 部署成功"

# 獲取服務 URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
echo "服務 URL: $SERVICE_URL"

# 等待服務啟動
echo "等待服務啟動..."
sleep 15

# 測試服務
echo "測試服務..."

echo "測試健康檢查端點..."
for i in {1..5}; do
    if curl -f "$SERVICE_URL/health" > /dev/null 2>&1; then
        echo "✅ 健康檢查端點正常"
        break
    else
        echo "⏳ 等待服務啟動... (嘗試 $i/5)"
        sleep 5
    fi
done

echo "測試 API 端點..."
if curl -f "$SERVICE_URL/api/test" > /dev/null 2>&1; then
    echo "✅ API 測試端點正常"
else
    echo "⚠️ API 測試端點可能需要更多時間啟動"
fi

echo "=== 部署完成 ==="
echo "服務 URL: $SERVICE_URL"
echo "管理控制台: https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME"
echo ""
echo "如果服務仍然無法訪問，請檢查 Cloud Run 日誌："
echo "gcloud logs read --project=$PROJECT_ID --filter='resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME' --limit=50"

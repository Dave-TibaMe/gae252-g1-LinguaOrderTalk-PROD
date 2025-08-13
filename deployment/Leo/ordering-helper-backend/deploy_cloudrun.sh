#!/bin/bash

# Cloud Run 部署腳本
# 使用方法: ./deploy_cloudrun.sh [PROJECT_ID] [REGION]

set -e  # 遇到錯誤時停止執行

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 函數：打印彩色訊息
print_message() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 檢查必要工具
check_requirements() {
    print_message "檢查必要工具..."
    
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI 未安裝，請先安裝 Google Cloud SDK"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安裝，請先安裝 Docker"
        exit 1
    fi
    
    print_success "必要工具檢查通過"
}

# 設定變數
PROJECT_ID=${1:-$(gcloud config get-value project)}
REGION=${2:-"asia-east1"}
SERVICE_NAME="ordering-helper-backend"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

# 檢查專案 ID
if [ -z "$PROJECT_ID" ]; then
    print_error "請提供專案 ID 或設定 gcloud 預設專案"
    echo "使用方法: $0 [PROJECT_ID] [REGION]"
    exit 1
fi

print_message "部署配置:"
echo "  專案 ID: $PROJECT_ID"
echo "  地區: $REGION"
echo "  服務名稱: $SERVICE_NAME"
echo "  映像名稱: $IMAGE_NAME"

# 確認部署
read -p "是否繼續部署？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "部署已取消"
    exit 0
fi

# 主部署流程
main() {
    print_message "開始 Cloud Run 部署流程..."
    
    # 1. 檢查必要工具
    check_requirements
    
    # 2. 設定 gcloud 專案
    print_message "設定 gcloud 專案..."
    gcloud config set project $PROJECT_ID
    
    # 3. 啟用必要 API
    print_message "啟用必要 API..."
    gcloud services enable cloudbuild.googleapis.com
    gcloud services enable run.googleapis.com
    
    # 4. 建置並推送 Docker 映像
    print_message "建置並推送 Docker 映像..."
    gcloud builds submit --tag $IMAGE_NAME
    
    # 5. 部署到 Cloud Run
    print_message "部署到 Cloud Run..."
    gcloud run deploy $SERVICE_NAME \
        --image $IMAGE_NAME \
        --platform managed \
        --region $REGION \
        --allow-unauthenticated \
        --port 8080 \
        --memory 1Gi \
        --cpu 1 \
        --timeout 300 \
        --set-env-vars "PORT=8080" \
        --max-instances 10 \
        --min-instances 0
    
    # 6. 獲取服務 URL
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
    
    print_success "部署完成！"
    echo "服務 URL: $SERVICE_URL"
    echo "健康檢查: $SERVICE_URL/health"
    echo "API 測試: $SERVICE_URL/api/test"
    
    # 7. 測試健康檢查
    print_message "測試健康檢查..."
    sleep 10  # 等待服務完全啟動
    
    if curl -f "$SERVICE_URL/health" > /dev/null 2>&1; then
        print_success "健康檢查通過"
    else
        print_warning "健康檢查失敗，請檢查服務日誌"
    fi
    
    # 8. 顯示後續步驟
    print_message "後續步驟:"
    echo "1. 在 Cloud Run 控制台中設定環境變數:"
    echo "   - DB_USER"
    echo "   - DB_PASSWORD"
    echo "   - DB_HOST"
    echo "   - DB_DATABASE"
    echo "   - LINE_CHANNEL_ACCESS_TOKEN"
    echo "   - LINE_CHANNEL_SECRET"
    echo ""
    echo "2. 查看服務日誌:"
    echo "   gcloud logs tail --service=$SERVICE_NAME --region=$REGION"
    echo ""
    echo "3. 更新服務:"
    echo "   gcloud run deploy $SERVICE_NAME --image $IMAGE_NAME --region=$REGION"
}

# 錯誤處理
trap 'print_error "部署過程中發生錯誤，請檢查日誌"; exit 1' ERR

# 執行主流程
main

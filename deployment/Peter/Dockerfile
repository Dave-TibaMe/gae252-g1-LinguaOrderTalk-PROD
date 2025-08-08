# 使用官方 Python 3.11 slim 映像作為基礎
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 設定環境變數
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 安裝系統依賴
# 需要 gcc 等編譯工具來建置某些 Python 套件
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    pkg-config \
    default-libmysqlclient-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 複製需求檔案
COPY requirements.txt .

# 安裝 Python 依賴套件
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 複製專案檔案
COPY deployment/Peter/app/ ./app/
COPY deployment/Peter/scripts/ ./scripts/

# 複製環境變數檔案 (如果存在)
# 注意：在生產環境中，建議使用環境變數或 secrets 而非 .env 檔案
COPY deployment/Peter/.env* ./

# 建立必要的目錄結構
RUN mkdir -p app/static/data

# 設定適當的檔案權限
RUN chmod -R 755 /app

# 暴露應用程式埠號
EXPOSE 8000

# 健康檢查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 建立非 root 使用者 (安全最佳實踐)
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# 啟動命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
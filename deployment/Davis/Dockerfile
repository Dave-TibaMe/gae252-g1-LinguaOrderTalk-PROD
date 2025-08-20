# 使用 Python 3.9 slim 作為基礎映像
FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 複製 requirements.txt 並安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式代碼
COPY . .

# 創建日誌目錄
RUN mkdir -p logs

# 設定環境變數
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 設定非 root 用戶（安全性考量）
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 設定容器啟動命令
CMD ["python", "main.py"]
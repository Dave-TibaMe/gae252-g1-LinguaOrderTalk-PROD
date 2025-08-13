# 使用 Ubuntu 20.04 作為基礎映像（支援 OpenSSL 1.1.1）
FROM ubuntu:20.04

# 設定環境變數避免互動式安裝
ENV DEBIAN_FRONTEND=noninteractive

# 安裝 Python 3.11 和必要系統庫
RUN apt-get update && \
    apt-get install -y \
        software-properties-common \
        ca-certificates \
        curl \
    && add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get update && \
    apt-get install -y \
        python3.11 \
        python3.11-dev \
        python3.11-distutils \
        python3-pip \
        # Azure Speech SDK 必要依賴
        libssl1.1 \
        libcurl4 \
        libgomp1 \
        libatomic1 \
        libffi-dev \
        libasound2 \
        libogg0 \
        libvorbis0a \
        sox \
        # 其他必要套件
        libpthread-stubs0-dev \
        gunicorn \
    && rm -rf /var/lib/apt/lists/*

# 設定 Python 3.11 為預設版本
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# 使用官方 get-pip.py 重新安裝 pip 以修復 html5lib 問題
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3

# 設定工作目錄
WORKDIR /app

# 複製 requirements.txt
COPY requirements.txt .

# 安裝 Python 依賴套件
RUN pip3 install --no-cache-dir -r requirements.txt

# 複製應用程式程式碼
COPY . .

# 建立語音檔案目錄
RUN mkdir -p /tmp/voices && chmod 755 /tmp/voices

# 設定啟動腳本權限
RUN chmod +x startup.sh startup_simple.sh

# 設定環境變數 - 移除可能衝突的變數
ENV PYTHONPATH=/app
ENV PYTHONWARNINGS=ignore
ENV PORT=8080

# 暴露端口 - 確保 Cloud Run 能正確識別
EXPOSE 8080

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# 使用簡化啟動腳本
CMD ["./startup_simple.sh"] 
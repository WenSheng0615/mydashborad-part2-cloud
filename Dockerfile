# 使用官方 Python 輕量版
FROM python:3.11-slim

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    python3-dev \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# 設定工作目錄
WORKDIR /app

# 複製並安裝 Python 套件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有程式碼
COPY . .

# Render 會自動提供 $PORT 環境變數，我們讓 uvicorn 監聽它
CMD ["python", "serve.py"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/health/ready',timeout=4)"

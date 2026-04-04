# 使用官方 Python 輕量版
FROM python:3.11-slim

# 安裝系統依賴 (ffmpeg 是 yt-dlp 必備)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 設定工作目錄
WORKDIR /app

# 複製並安裝 Python 套件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有程式碼
COPY . .

# Render 會自動提供 $PORT 環境變數，我們讓 uvicorn 監聽它
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]

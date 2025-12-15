# 1. 使用 Python 3.10 輕量版當作基底
FROM python:3.10-slim

# 2. 設定工作目錄
WORKDIR /app

# 3. 安裝系統層級的依賴 (包含最重要的 FFmpeg)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 4. 複製套件清單並安裝 Python 套件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 複製所有程式碼到伺服器
COPY . .

# 6. 設定環境變數 (Render 會自動提供 PORT)
ENV PORT=8000

# 7. 啟動指令
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
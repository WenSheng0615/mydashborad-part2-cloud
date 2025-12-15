import os
import json
from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
import redis
import yt_dlp
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import shutil

router = APIRouter(prefix="/api/music", tags=["music"])

# Redis 連線 (保持不變)
r = redis.Redis(
    host='redis-11812.c326.us-east-1-3.ec2.cloud.redislabs.com',
    port=11812,
    decode_responses=True,
    username="default",
    password="peayWIVDRyeiuuVFDTeBE3T7Ia75H4wT",
    socket_timeout=5
)

# ★★★ 修改：讓程式自動尋找 ffmpeg，不指定 .exe ★★★
# Dockerfile 已經安裝了 ffmpeg，所以 which/shutil.which 找得到
FFMPEG_BIN = shutil.which("ffmpeg") 

if FFMPEG_BIN:
    print(f"✅ [Music] FFmpeg found at: {FFMPEG_BIN}")
else:
    print(f"⚠️ [Music] FFmpeg not found! Streaming will fail.")

# ★★★ 修改：Token 改從 Redis 讀取，不再讀檔案 ★★★
def get_youtube_service():
    token_json = r.get("auth:token_file") # 從 Redis 讀
    if not token_json: return None
    
    try:
        info = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(info)
        
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # 刷新後存回 Redis
            r.set("auth:token_file", creds.to_json())
            
        return build('youtube', 'v3', credentials=creds)
    except: return None

@router.get("/stream")
async def get_audio_stream(video_id: str):
    print(f"🎵 Parsing: {video_id} ...")
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'skip_download': True,
            # ★★★ 關鍵修改：不指定 ffmpeg_location，讓它自己找 ★★★
        }
        
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return JSONResponse({
                "url": info['url'], 
                "title": info['title'], 
                "thumbnail": info.get('thumbnail'),
                "duration": info.get('duration')
            })
    except Exception as e:
        print(f"❌ Error: {e}")
        return JSONResponse({"error": str(e)}, 500)

# 搜尋、歌單、歷史紀錄等功能保持不變 (省略以節省篇幅)
# ... (請保留您原本 music.py 下半部的 search, playlists 等程式碼) ...
# 注意：原本下半部的 get_my_playlists 等函式若有呼叫 get_youtube_service，
# 會自動使用上面新定義的 Redis 版本，所以不用改。
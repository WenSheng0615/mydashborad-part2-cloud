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

# Redis 連線
r = redis.Redis(
    host='redis-11812.c326.us-east-1-3.ec2.cloud.redislabs.com',
    port=11812,
    decode_responses=True,
    username="default",
    password="peayWIVDRyeiuuVFDTeBE3T7Ia75H4wT",
    socket_timeout=5
)

# 自動尋找 FFmpeg (Render 專用)
FFMPEG_BIN = shutil.which("ffmpeg") or "ffmpeg"
print(f"🎵 FFmpeg found at: {FFMPEG_BIN}")

def get_youtube_service():
    # 改從 Redis 讀 Token
    token_json = r.get("auth:google_token")
    if not token_json: return None
    try:
        info = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(info)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            r.set("auth:google_token", creds.to_json())
        return build('youtube', 'v3', credentials=creds)
    except: return None

@router.get("/stream")
async def get_audio_stream(video_id: str):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'skip_download': True,
            # 不指定路徑，讓它自動使用系統環境變數
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
        print(f"❌ 解析失敗: {e}")
        return JSONResponse({"error": str(e)}, 500)

@router.get("/search")
async def search_youtube(query: str):
    cache_key = f"yt:search:{query}"
    try:
        if r.exists(cache_key):
            return JSONResponse({"items": json.loads(r.get(cache_key))})
    except: pass

    try:
        service = get_youtube_service()
        if not service: return JSONResponse({"error": "未登入"}, 401)
        
        req = service.search().list(part="snippet", maxResults=20, q=query, type="video")
        res = req.execute()
        
        items = []
        for i in res.get('items', []):
            try:
                thumbs = i['snippet'].get('thumbnails', {})
                thumb_url = thumbs.get('medium', {}).get('url') or thumbs.get('default', {}).get('url') or ''
                items.append({
                    'id': i['id']['videoId'],
                    'title': i['snippet']['title'],
                    'thumbnail': thumb_url,
                    'channel': i['snippet']['channelTitle']
                })
            except: continue
        
        try: r.set(cache_key, json.dumps(items), ex=86400)
        except: pass

        return JSONResponse({"items": items})
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.get("/playlists")
async def get_my_playlists():
    try:
        service = get_youtube_service()
        if not service: return JSONResponse({"error": "未登入"}, 401)
        
        req = service.playlists().list(part="snippet,contentDetails", mine=True, maxResults=50)
        res = req.execute()
        
        playlists = []
        for i in res.get('items', []):
            try:
                thumbs = i['snippet'].get('thumbnails', {})
                thumb_url = thumbs.get('medium', {}).get('url') or thumbs.get('default', {}).get('url') or ''
                playlists.append({
                    'id': i['id'], 
                    'title': i['snippet']['title'], 
                    'thumbnail': thumb_url, 
                    'count': i['contentDetails']['itemCount']
                })
            except: continue
        return JSONResponse({"playlists": playlists})
    except Exception as e:
        # 若無頻道或其他錯誤，回傳空列表，不報錯
        print(f"Playlist Error: {e}")
        return JSONResponse({"playlists": []})

@router.get("/playlist/items")
async def get_playlist_items(playlist_id: str):
    try:
        service = get_youtube_service()
        req = service.playlistItems().list(part="snippet,id", playlistId=playlist_id, maxResults=50)
        res = req.execute()
        items = []
        for i in res.get('items', []):
            try:
                if 'videoOwnerChannelTitle' in i['snippet']:
                    thumbs = i['snippet'].get('thumbnails', {})
                    thumb_url = thumbs.get('medium', {}).get('url') or thumbs.get('default', {}).get('url') or ''
                    items.append({
                        'id': i['snippet']['resourceId']['videoId'], 
                        'itemId': i['id'], 
                        'title': i['snippet']['title'], 
                        'thumbnail': thumb_url, 
                        'channel': i['snippet']['videoOwnerChannelTitle']
                    })
            except: continue
        return JSONResponse({"items": items})
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.post("/playlist/add_song")
async def add_song_to_playlist(playlist_id: str=Form(...), video_id: str=Form(...)):
    try:
        service = get_youtube_service()
        service.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.post("/playlist/remove_song")
async def remove_song_from_playlist(item_id: str=Form(...)):
    try:
        service = get_youtube_service()
        service.playlistItems().delete(id=item_id).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.get("/user")
async def get_user_info():
    try:
        token_json = r.get("auth:google_token")
        if not token_json: return JSONResponse({"error": "未登入"})
        creds = Credentials.from_authorized_user_info(json.loads(token_json))
        service = build('oauth2', 'v2', credentials=creds)
        info = service.userinfo().get().execute()
        return JSONResponse({"info": info})
    except: return JSONResponse({"error": "Failed"})

@router.get("/history")
async def get_history():
    try:
        data = r.lrange("user:music:history", 0, 49)
        return JSONResponse({"history": [json.loads(h) for h in data]})
    except: return JSONResponse({"history": []})

@router.post("/history/add")
async def add_history(id: str=Form(...), title: str=Form(...), channel: str=Form(...), thumbnail: str=Form(...)):
    try:
        item = json.dumps({"id": id, "title": title, "channel": channel, "thumbnail": thumbnail})
        r.lrem("user:music:history", 0, item)
        r.lpush("user:music:history", item)
        r.ltrim("user:music:history", 0, 49)
        return {"status": "success"}
    except: return {"status": "error"}
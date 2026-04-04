import os
import json
from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse
import yt_dlp
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
import shutil

# ✅ 改用 SQLite
from database import get_session_info, save_session

router = APIRouter(prefix="/api/music", tags=["music"])

def get_youtube_service(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id: return None
    
    # ✅ 從 SQLite 讀取
    session = get_session_info(session_id)
    if not session: return None
    token_json = session.token_json
    
    try:
        info = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(info)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            save_session(session_id, creds.to_json(), session.user_email)
        return build('youtube', 'v3', credentials=creds)
    except: return None

@router.get("/playlists")
async def get_my_playlists(request: Request):
    try:
        service = get_youtube_service(request)
        if not service: return JSONResponse({"error": "未登入"}, 401)
        
        req = service.playlists().list(part="snippet,contentDetails", mine=True, maxResults=50)
        res = req.execute()
        
        playlists = []
        for i in res.get('items', []):
            thumbs = i['snippet'].get('thumbnails', {})
            thumb_url = thumbs.get('medium', {}).get('url') or thumbs.get('default', {}).get('url') or ''
            playlists.append({
                'id': i['id'], 
                'title': i['snippet']['title'], 
                'thumbnail': thumb_url, 
                'count': i['contentDetails']['itemCount']
            })
        return JSONResponse({"playlists": playlists})
    except Exception as e:
        print(f"Music Playlist Error: {e}")
        return JSONResponse({"playlists": []})

@router.get("/playlist/items")
async def get_playlist_items(request: Request, playlist_id: str):
    try:
        service = get_youtube_service(request)
        if not service: return JSONResponse({"error": "未登入"}, 401)
        
        req = service.playlistItems().list(part="snippet", playlistId=playlist_id, maxResults=50)
        res = req.execute()
        
        items = []
        for i in res.get('items', []):
            thumbs = i['snippet'].get('thumbnails', {})
            thumb_url = thumbs.get('medium', {}).get('url') or ''
            items.append({
                'id': i['snippet']['resourceId']['videoId'], 
                'itemId': i['id'], 
                'title': i['snippet']['title'], 
                'thumbnail': thumb_url
            })
        return JSONResponse({"items": items})
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.get("/stream")
async def get_audio_stream(video_id: str):
    try:
        ydl_opts = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'skip_download': True}
        url = f"https://www.youtube.com/watch?v={video_id}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return JSONResponse({
                "url": info['url'], 
                "title": info['title'], 
                "thumbnail": info.get('thumbnail')
            })
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.get("/search")
async def search_youtube(request: Request, query: str):
    try:
        service = get_youtube_service(request)
        if not service: return JSONResponse({"error": "未登入"}, 401)
        
        req = service.search().list(part="snippet", maxResults=20, q=query, type="video")
        res = req.execute()
        
        items = []
        for i in res.get('items', []):
            thumbs = i['snippet'].get('thumbnails', {})
            items.append({
                'id': i['id']['videoId'], 
                'title': i['snippet']['title'], 
                'thumbnail': thumbs.get('medium', {}).get('url'), 
                'channel': i['snippet']['channelTitle']
            })
        return JSONResponse({"items": items})
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

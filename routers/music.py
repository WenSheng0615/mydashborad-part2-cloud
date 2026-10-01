from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse
import yt_dlp

# ✅ 改用 SQLite
from database import get_session_info, get_db, MusicHistory
from services.google_auth_service import build_google_service, auth_error_body

router = APIRouter(prefix="/api/music", tags=["music"])


def _youtube_service(request: Request):
    service, result = build_google_service(request, 'youtube', 'v3')
    if not service:
        body, status = auth_error_body(result)
        return None, JSONResponse(body, status)
    return service, None

@router.get("/playlists")
async def get_my_playlists(request: Request):
    service, err = _youtube_service(request)
    if err: return err
    try:
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
    service, err = _youtube_service(request)
    if err: return err
    try:
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
    except Exception as e: return JSONResponse({"error": "外部服務暫時無法完成操作，請稍後重試"}, 500)

@router.get("/stream")
async def get_audio_stream(request: Request, video_id: str):
    session = get_session_info(request.cookies.get("session_id"))
    if not session: return JSONResponse({"error": "Login Required"}, 401)
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return JSONResponse({"error": "Invalid video ID"}, 422)
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'skip_download': True,
            'js_runtimes': {
                'node': {
                    'path': '/usr/bin/node'
                }
            },
            'remote_components': ['ejs:github']
        }
        url = f"https://www.youtube.com/watch?v={video_id}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return JSONResponse({
                "url": info['url'], 
                "title": info['title'], 
                "thumbnail": info.get('thumbnail')
            })
    except Exception as e: return JSONResponse({"error": "外部服務暫時無法完成操作，請稍後重試"}, 500)

@router.get("/search")
async def search_youtube(request: Request, query: str):
    service, err = _youtube_service(request)
    if err: return err
    try:
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
    except Exception as e: return JSONResponse({"error": "外部服務暫時無法完成操作，請稍後重試"}, 500)

@router.get("/history")
async def get_history(request: Request):
    session_id = request.cookies.get("session_id")
    session = get_session_info(session_id)
    if not session: return JSONResponse({"items": []})
    
    db = get_db()
    history = db.query(MusicHistory).filter(MusicHistory.user_email == session.user_email).order_by(MusicHistory.played_at.desc()).limit(40).all()
    
    seen = set()
    result = []
    for h in history:
        if h.video_id not in seen:
            result.append({"id": h.video_id, "title": h.title, "thumbnail": h.thumbnail})
            seen.add(h.video_id)
            if len(result) >= 20: break
    db.close()
    return JSONResponse({"items": result})

@router.post("/history/add")
async def add_history(request: Request, video_id: str = Form(...), title: str = Form(...), thumbnail: str = Form(...)):
    session_id = request.cookies.get("session_id")
    session = get_session_info(session_id)
    if not session: return {"status": "unauthorized"}
    
    db = get_db()
    new_h = MusicHistory(
        user_email=session.user_email,
        video_id=video_id,
        title=title,
        thumbnail=thumbnail
    )
    db.add(new_h)
    db.commit()
    db.close()
    return {"status": "success"}

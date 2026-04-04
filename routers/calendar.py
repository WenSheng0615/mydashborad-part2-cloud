import os
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

# ✅ 改用 SQLite
from database import get_session_info, save_session

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

def get_calendar_service(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id: return None
    
    session = get_session_info(session_id)
    if not session: return None
    token_json = session.token_json
    
    try:
        info = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(info)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            save_session(session_id, creds.to_json(), session.user_email)
        return build('calendar', 'v3', credentials=creds)
    except: return None

@router.get("/events")
async def get_events(request: Request, year: int, month: int):
    try:
        service = get_calendar_service(request)
        if not service: return JSONResponse({"error": "Login Required"}, 401)
        
        start_date = datetime(year, month, 1)
        if month == 12: end_date = datetime(year + 1, 1, 1)
        else: end_date = datetime(year, month + 1, 1)
        
        events_result = service.events().list(
            calendarId='primary', 
            timeMin=start_date.isoformat() + 'Z', 
            timeMax=end_date.isoformat() + 'Z', 
            singleEvents=True, 
            orderBy='startTime'
        ).execute()
        
        formatted = []
        for e in events_result.get('items', []):
            is_all_day = 'date' in e['start']
            start = e['start'].get('dateTime', e['start'].get('date'))
            end = e['end'].get('dateTime', e['end'].get('date'))
            formatted.append({
                'id': e['id'], 
                'summary': e.get('summary', '(無標題)'), 
                'start': start, 
                'end': end, 
                'is_all_day': is_all_day
            })
        return JSONResponse({"events": formatted})
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.post("/add")
async def add_event(
    request: Request, 
    summary: str = Form(...), 
    description: str = Form(""), 
    start_date: str = Form(...), 
    start_time: str = Form(""), 
    end_date: str = Form(...), 
    end_time: str = Form(""), 
    is_all_day: str = Form("false")
):
    try:
        service = get_calendar_service(request)
        if not service: return JSONResponse({"error": "Login Required"}, 401)
        
        event = {
            'summary': summary,
            'description': description,
            'start': {'date': start_date} if is_all_day == 'true' else {'dateTime': f"{start_date}T{start_time}:00", 'timeZone': 'Asia/Taipei'},
            'end': {'date': end_date} if is_all_day == 'true' else {'dateTime': f"{end_date}T{end_time}:00", 'timeZone': 'Asia/Taipei'}
        }
        service.events().insert(calendarId='primary', body=event).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.post("/delete")
async def delete_event(request: Request, event_id: str = Form(...)):
    try:
        service = get_calendar_service(request)
        if not service: return JSONResponse({"error": "Login Required"}, 401)
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

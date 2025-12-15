import os
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
import redis
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

# Redis
r = redis.Redis(
    host='redis-11812.c326.us-east-1-3.ec2.cloud.redislabs.com',
    port=11812, decode_responses=True, username="default",
    password="peayWIVDRyeiuuVFDTeBE3T7Ia75H4wT", socket_timeout=5
)

def get_calendar_service():
    token_json = r.get("auth:google_token")
    if not token_json: return None
    try:
        info = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(info)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            r.set("auth:google_token", creds.to_json())
        return build('calendar', 'v3', credentials=creds)
    except: return None

@router.get("/events")
async def get_events(year: int, month: int):
    try:
        service = get_calendar_service()
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
                'id': e['id'], 'summary': e.get('summary', '(無標題)'),
                'description': e.get('description', ''),
                'start': start, 'end': end, 'is_all_day': is_all_day,
                'location': e.get('location', ''), 'htmlLink': e.get('htmlLink')
            })
        return JSONResponse({"events": formatted})
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

# 其他 add/update/delete 邏輯不變，略過以省空間 (只改 service 取得部分即可)
# 請保留您原本的 post methods，它們會自動呼叫新的 get_calendar_service
@router.post("/add")
async def add_event(summary: str = Form(...), description: str = Form(""), start_date: str = Form(...), start_time: str = Form(""), end_date: str = Form(...), end_time: str = Form(""), is_all_day: str = Form("false")):
    try:
        service = get_calendar_service()
        event = build_event_body(summary, description, start_date, start_time, end_date, end_time, is_all_day)
        service.events().insert(calendarId='primary', body=event).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.post("/update")
async def update_event(event_id: str = Form(...), summary: str = Form(...), description: str = Form(""), start_date: str = Form(...), start_time: str = Form(""), end_date: str = Form(...), end_time: str = Form(""), is_all_day: str = Form("false")):
    try:
        service = get_calendar_service()
        event = build_event_body(summary, description, start_date, start_time, end_date, end_time, is_all_day)
        service.events().patch(calendarId='primary', eventId=event_id, body=event).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.post("/delete")
async def delete_event(event_id: str = Form(...)):
    try:
        service = get_calendar_service()
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

def build_event_body(summary, desc, s_date, s_time, e_date, e_time, is_all_day):
    body = {'summary': summary, 'description': desc}
    if is_all_day == 'true':
        if s_date == e_date:
            dt = datetime.strptime(e_date, "%Y-%m-%d") + timedelta(days=1)
            e_date = dt.strftime("%Y-%m-%d")
        body['start'] = {'date': s_date, 'dateTime': None}
        body['end'] = {'date': e_date, 'dateTime': None}
    else:
        body['start'] = {'dateTime': f"{s_date}T{s_time}:00", 'timeZone': 'Asia/Taipei', 'date': None}
        body['end'] = {'dateTime': f"{e_date}T{e_time}:00", 'timeZone': 'Asia/Taipei', 'date': None}
    return body
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(BASE_DIR, 'token.json')

def get_calendar_service():
    if not os.path.exists(TOKEN_FILE): return None
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, 'w') as token: token.write(creds.to_json())
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
                'id': e['id'], 
                'summary': e.get('summary', '(無標題)'),
                'description': e.get('description', ''),
                'start': start, 
                'end': end,
                'is_all_day': is_all_day,
                'location': e.get('location', ''), 
                'htmlLink': e.get('htmlLink')
            })
        return JSONResponse({"events": formatted})
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.post("/add")
async def add_event(
    summary: str = Form(...), 
    description: str = Form(""),
    start_date: str = Form(...), 
    start_time: str = Form(""),
    end_date: str = Form(...),
    end_time: str = Form(""),
    is_all_day: str = Form("false")
):
    try:
        service = get_calendar_service()
        event = build_event_body(summary, description, start_date, start_time, end_date, end_time, is_all_day)
        service.events().insert(calendarId='primary', body=event).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.post("/update")
async def update_event(
    event_id: str = Form(...),
    summary: str = Form(...), 
    description: str = Form(""),
    start_date: str = Form(...), 
    start_time: str = Form(""),
    end_date: str = Form(...),
    end_time: str = Form(""),
    is_all_day: str = Form("false")
):
    try:
        service = get_calendar_service()
        # 呼叫 patch 更新，並確保清除衝突的時間格式
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
    body = {
        'summary': summary,
        'description': desc,
    }
    if is_all_day == 'true':
        # ★ 關鍵修正：若為全天，將 dateTime 設為 None，強制清除舊設定 ★
        if s_date == e_date:
            dt = datetime.strptime(e_date, "%Y-%m-%d") + timedelta(days=1)
            e_date = dt.strftime("%Y-%m-%d")
        
        body['start'] = {'date': s_date, 'dateTime': None}
        body['end'] = {'date': e_date, 'dateTime': None}
    else:
        # ★ 關鍵修正：若為時間，將 date 設為 None ★
        start_dt = f"{s_date}T{s_time}:00"
        end_dt = f"{e_date}T{e_time}:00"
        
        body['start'] = {'dateTime': start_dt, 'timeZone': 'Asia/Taipei', 'date': None}
        body['end'] = {'dateTime': end_dt, 'timeZone': 'Asia/Taipei', 'date': None}
        
    return body
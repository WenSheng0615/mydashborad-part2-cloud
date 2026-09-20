from datetime import datetime, date
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import JSONResponse

from services.google_auth_service import build_google_service, auth_error_body

from zoneinfo import ZoneInfo
from config import APP_TIMEZONE

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _calendar_service(request: Request):
    service, result = build_google_service(request, 'calendar', 'v3')
    if not service:
        body, status = auth_error_body(result)
        return None, JSONResponse(body, status)
    return service, None

@router.get("/events")
def get_events(request: Request, year: int, month: int):
    service, err = _calendar_service(request)
    if err: return err
    try:
        start_date = datetime(year, month, 1, tzinfo=ZoneInfo(APP_TIMEZONE))
        if month == 12: end_date = datetime(year + 1, 1, 1, tzinfo=ZoneInfo(APP_TIMEZONE))
        else: end_date = datetime(year, month + 1, 1, tzinfo=ZoneInfo(APP_TIMEZONE))

        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_date.isoformat(),
            timeMax=end_date.isoformat(),
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
                'is_all_day': is_all_day
            })
        return JSONResponse({"events": formatted})
    except Exception as e: return JSONResponse({"error": "外部服務暫時無法完成操作，請稍後重試"}, 500)

def event_body(summary, description, start_date, start_time, end_date, end_time, is_all_day):
    summary = summary.strip()
    if not summary or len(summary) > 500 or len(description) > 10000:
        raise HTTPException(422, "標題需為 1–500 字；描述最多 10000 字")
    try:
        if is_all_day:
            start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
            body = {"start": {"date": start.isoformat()}, "end": {"date": end.isoformat()}}
        else:
            zone = ZoneInfo(APP_TIMEZONE)
            start = datetime.fromisoformat(f"{start_date}T{start_time}").replace(tzinfo=zone)
            end = datetime.fromisoformat(f"{end_date}T{end_time}").replace(tzinfo=zone)
            body = {"start": {"dateTime": start.isoformat(), "timeZone": APP_TIMEZONE},
                    "end": {"dateTime": end.isoformat(), "timeZone": APP_TIMEZONE}}
        if end <= start:
            raise ValueError()
    except ValueError:
        raise HTTPException(422, "請檢查日期時間；結束必須晚於開始，全天結束日不包含在行程內")
    return {"summary": summary, "description": description, **body}


@router.post("/add")
@router.post("/update")
def save_event(request: Request, summary: str = Form(...), description: str = Form(""),
               start_date: str = Form(...), start_time: str = Form(""),
               end_date: str = Form(...), end_time: str = Form(""),
               is_all_day: bool = Form(False), event_id: str = Form("")):
    service, err = _calendar_service(request)
    if err: return err
    updating = request.url.path.endswith("/update")
    if updating and not event_id.strip():
        raise HTTPException(422, "缺少行程 ID")
    body = event_body(summary, description, start_date, start_time, end_date, end_time, is_all_day)
    try:
        if updating:
            # Patch only editable fields, retaining attendees/reminders and provider metadata.
            service.events().patch(calendarId="primary", eventId=event_id, body=body).execute()
        else:
            service.events().insert(calendarId="primary", body=body).execute()
        return {"status": "success"}
    except Exception:
        return JSONResponse({"error": "Google 行程儲存失敗，請稍後再試"}, 502)

@router.post("/delete")
def delete_event(request: Request, event_id: str = Form(...)):
    service, err = _calendar_service(request)
    if err: return err
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": "外部服務暫時無法完成操作，請稍後重試"}, 500)

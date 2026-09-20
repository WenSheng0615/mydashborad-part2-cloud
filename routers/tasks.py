import json
from googleapiclient.errors import HttpError
from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse

from services.google_auth_service import build_google_service, auth_error_body

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# Google Tasks 原生只有 needsAction/completed 兩種狀態，沒有「進行中」欄位，
# 因此用 notes 欄位夾帶一個標記字串來模擬看板的第三欄（doing）。
STAGE_DOING_TAG = "[STAGE:doing]"


def _stage_to_body(stage: str, existing_notes: str):
    clean_notes = (existing_notes or "").replace(STAGE_DOING_TAG, "").strip()
    if stage == "done":
        return {"status": "completed", "notes": clean_notes}
    if stage == "doing":
        return {"status": "needsAction", "notes": (clean_notes + "\n" + STAGE_DOING_TAG).strip()}
    return {"status": "needsAction", "notes": clean_notes}


def _tasks_service(request: Request):
    service, result = build_google_service(request, 'tasks', 'v1')
    if not service:
        body, status = auth_error_body(result)
        return None, JSONResponse(body, status)
    return service, None

@router.get("/")
async def get_tasks(request: Request):
    service, err = _tasks_service(request)
    if err: return err
    try:
        try:
            lists_res = service.tasklists().list().execute()
            tasklists = lists_res.get('items', [])
            if not tasklists:
                return JSONResponse({"todo": [], "doing": [], "done": []})

            list_id = tasklists[0]['id']
            tasks_res = service.tasks().list(tasklist=list_id, showCompleted=True).execute()

            todo, doing, done = [], [], []
            for t in tasks_res.get('items', []):
                notes = t.get('notes') or ''
                task_data = {
                    "id": t['id'],
                    "content": t['title'],
                    "due_date": t.get('due', ''),
                    "list_id": list_id
                }
                if t['status'] == 'completed':
                    done.append(task_data)
                elif STAGE_DOING_TAG in notes:
                    doing.append(task_data)
                else:
                    todo.append(task_data)

            return JSONResponse({"todo": todo, "doing": doing, "done": done, "list_id": list_id})
        except HttpError as api_e:
            try:
                payload = json.loads(api_e.content).get('error', {})
                reasons = {item.get('reason') for item in payload.get('errors', [])}
            except (ValueError, TypeError, AttributeError):
                reasons = set()
            if 'accessNotConfigured' in reasons:
                return JSONResponse({"error": "此 Google Cloud 專案尚未啟用 Google Tasks API。請在 OAuth 憑證所屬專案啟用 API 後重試。", "code": "google_tasks_api_disabled"}, 503)
            return JSONResponse({"error": "Google Tasks 請求遭拒，請確認授權與服務狀態", "code": "google_tasks_provider_error"}, 502)
        except Exception:
            return JSONResponse({"error": "Google Tasks 讀取失敗，請稍後再試"}, 502)

    except Exception as e:
        print(f"Tasks Router Error: {e}")
        return JSONResponse({"error": "外部服務暫時無法完成操作，請稍後重試"}, 500)

@router.post("/add")
async def add_task(request: Request, content: str = Form(...), due_date: str = Form(""), list_id: str = Form("@default")):
    service, err = _tasks_service(request)
    if err: return err
    try:
        task_body = {'title': content}
        if due_date: task_body['due'] = f"{due_date}T00:00:00Z"

        service.tasks().insert(tasklist=list_id, body=task_body).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": "外部服務暫時無法完成操作，請稍後重試"}, 500)

@router.post("/delete")
async def delete_task(request: Request, task_id: str = Form(...), list_id: str = Form("@default")):
    service, err = _tasks_service(request)
    if err: return err
    try:
        service.tasks().delete(tasklist=list_id, task=task_id).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": "外部服務暫時無法完成操作，請稍後重試"}, 500)

@router.post("/move")
async def move_task(request: Request, task_id: str = Form(...), from_stage: str = Form(""), to_stage: str = Form(...), list_id: str = Form("@default")):
    service, err = _tasks_service(request)
    if err: return err
    try:
        task = service.tasks().get(tasklist=list_id, task=task_id).execute()
        body = _stage_to_body(to_stage, task.get('notes'))
        service.tasks().patch(tasklist=list_id, task=task_id, body=body).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": "外部服務暫時無法完成操作，請稍後重試"}, 500)

@router.post("/update")
async def update_task(request: Request, task_id: str = Form(...), content: str = Form(...), stage: str = Form(""), due_date: str = Form(""), list_id: str = Form("@default")):
    service, err = _tasks_service(request)
    if err: return err
    try:
        task = service.tasks().get(tasklist=list_id, task=task_id).execute()
        body = _stage_to_body(stage, task.get('notes'))
        body['title'] = content
        body['due'] = f"{due_date.split(' ')[0]}T00:00:00Z" if due_date else None
        service.tasks().patch(tasklist=list_id, task=task_id, body=body).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": "外部服務暫時無法完成操作，請稍後重試"}, 500)

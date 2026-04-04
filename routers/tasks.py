import os
import json
from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

# ✅ 改用 SQLite
from database import get_session_info, save_session

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

def get_tasks_service(request: Request):
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
        return build('tasks', 'v1', credentials=creds)
    except: return None

@router.get("/")
async def get_tasks(request: Request):
    try:
        service = get_tasks_service(request)
        if not service: return JSONResponse({"error": "Login Required"}, 401)
        
        lists_res = service.tasklists().list().execute()
        tasklists = lists_res.get('items', [])
        if not tasklists: return JSONResponse({"todo": [], "doing": [], "done": []})
        
        list_id = tasklists[0]['id']
        tasks_res = service.tasks().list(tasklist=list_id, showCompleted=True).execute()
        
        todo, done = [], []
        for t in tasks_res.get('items', []):
            task_data = {
                "id": t['id'], 
                "content": t['title'], 
                "due_date": t.get('due', ''), 
                "list_id": list_id
            }
            if t['status'] == 'completed': done.append(task_data)
            else: todo.append(task_data)
                
        return JSONResponse({"todo": todo, "doing": [], "done": done, "list_id": list_id})
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.post("/add")
async def add_task(request: Request, content: str = Form(...), due_date: str = Form(""), list_id: str = Form("@default")):
    try:
        service = get_tasks_service(request)
        if not service: return JSONResponse({"error": "Login Required"}, 401)
        
        task_body = {'title': content}
        if due_date: task_body['due'] = f"{due_date}T00:00:00Z"
        
        service.tasks().insert(tasklist=list_id, body=task_body).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@router.post("/delete")
async def delete_task(request: Request, task_id: str = Form(...), list_id: str = Form("@default")):
    try:
        service = get_tasks_service(request)
        if not service: return JSONResponse({"error": "Login Required"}, 401)
        service.tasks().delete(tasklist=list_id, task=task_id).execute()
        return {"status": "success"}
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

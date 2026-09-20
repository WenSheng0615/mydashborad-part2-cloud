import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse
from database import get_db, Transaction, Category, get_session_info
from services.money_service import get_money_summary

router = APIRouter(prefix="/api/money", tags=["money"])

@router.get("/")
async def get_money(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id: return JSONResponse({"transactions": [], "categories": []})
    
    session = get_session_info(session_id)
    if not session: return JSONResponse({"transactions": [], "categories": []})
    
    db = get_db()
    data = get_money_summary(db, session.user_email)
    db.close()
    return JSONResponse(data)

@router.post("/add")
async def add_tx(request: Request, item: str = Form(...), amount: float = Form(...), date: str = Form(...), type: str = Form(...), category: str = Form(...), note: str = Form("")):
    session_id = request.cookies.get("session_id")
    session = get_session_info(session_id)
    if not session: return JSONResponse({"error": "unauthorized"}, 401)
    
    db = get_db()
    new_tx = Transaction(
        id=str(uuid.uuid4()), user_email=session.user_email,
        item=item, amount=amount, date=date, type=type, category=category, note=note
    )
    db.add(new_tx)
    db.commit()
    db.close()
    return {"status": "success"}

@router.post("/category/add")
async def add_cat(request: Request, name: str = Form(...), budget: float = Form(0), type: str = Form("expense")):
    session_id = request.cookies.get("session_id")
    session = get_session_info(session_id)
    if not session: return JSONResponse({"error": "unauthorized"}, 401)

    db = get_db()
    new_cat = Category(user_email=session.user_email, name=name, budget=budget, type=type)
    db.add(new_cat)
    db.commit()
    db.close()
    return {"status": "success"}

@router.post("/category/delete")
async def delete_cat(request: Request, name: str = Form(...)):
    session_id = request.cookies.get("session_id")
    session = get_session_info(session_id)
    if not session: return JSONResponse({"error": "unauthorized"}, 401)

    db = get_db()
    db.query(Category).filter(Category.name == name, Category.user_email == session.user_email).delete()
    db.commit()
    db.close()
    return {"status": "success"}

@router.post("/category/update")
async def update_cat(request: Request, old_name: str = Form(...), new_name: str = Form(...), budget: float = Form(0), type: str = Form("expense")):
    session_id = request.cookies.get("session_id")
    session = get_session_info(session_id)
    if not session: return JSONResponse({"error": "unauthorized"}, 401)

    db = get_db()
    cat = db.query(Category).filter(Category.name == old_name, Category.user_email == session.user_email).first()
    if not cat:
        db.close()
        return JSONResponse({"error": "not_found"}, 404)
    cat.name = new_name
    cat.budget = budget
    cat.type = type
    # 類別改名要一併更新既有交易紀錄，不然舊交易的分類會對不上
    if old_name != new_name:
        db.query(Transaction).filter(
            Transaction.category == old_name, Transaction.user_email == session.user_email
        ).update({Transaction.category: new_name})
    db.commit()
    db.close()
    return {"status": "success"}

@router.post("/delete")
async def delete_tx(request: Request, id: str = Form(...)):
    session_id = request.cookies.get("session_id")
    session = get_session_info(session_id)
    if not session: return JSONResponse({"error": "unauthorized"}, 401)

    db = get_db()
    tx = db.query(Transaction).filter(Transaction.id == id, Transaction.user_email == session.user_email).first()
    if tx:
        db.delete(tx)
        db.commit()
    db.close()
    return {"status": "success"}

@router.post("/reset")
async def reset_money(request: Request):
    session_id = request.cookies.get("session_id")
    session = get_session_info(session_id)
    if not session: return JSONResponse({"error": "unauthorized"}, 401)

    db = get_db()
    db.query(Transaction).filter(Transaction.user_email == session.user_email).delete()
    db.commit()
    db.close()
    return {"status": "success"}

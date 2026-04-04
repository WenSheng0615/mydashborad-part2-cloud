import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse
from database import get_db, Transaction, Category, get_session_info

router = APIRouter(prefix="/api/money", tags=["money"])

@router.get("/")
async def get_money(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id: return JSONResponse({"transactions": [], "categories": []})
    
    session = get_session_info(session_id)
    if not session: return JSONResponse({"transactions": [], "categories": []})
    
    db = get_db()
    user_email = session.user_email
    
    txs = db.query(Transaction).filter(Transaction.user_email == user_email).order_by(Transaction.date.desc()).all()
    cats = db.query(Category).filter(Category.user_email == user_email).all()
    
    income = 0
    expense = 0
    cat_spent = {c.name: 0 for c in cats}
    
    formatted_txs = []
    for t in txs:
        formatted_txs.append({
            "id": t.id, "item": t.item, "amount": t.amount, 
            "date": t.date, "type": t.type, "category": t.category, "note": t.note
        })
        if t.type == 'income': income += t.amount
        else: expense += t.amount
        
        if t.category in cat_spent:
            cat_spent[t.category] += t.amount

    formatted_cats = []
    for c in cats:
        status = "normal"
        if c.type == 'expense' and cat_spent[c.name] > c.budget: status = "over"
        
        formatted_cats.append({
            "name": c.name, "budget": c.budget, "spent": cat_spent[c.name], 
            "status": status, "type": c.type
        })
        
    db.close()
    return JSONResponse({
        "transactions": formatted_txs,
        "total_income": income, "total_expense": expense, "balance": income - expense,
        "categories": formatted_cats
    })

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

@router.post("/delete")
async def delete_tx(request: Request, id: str = Form(...)):
    db = get_db()
    tx = db.query(Transaction).filter(Transaction.id == id).first()
    if tx:
        db.delete(tx)
        db.commit()
    db.close()
    return {"status": "success"}

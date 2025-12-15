from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
import redis
import json
import uuid
import datetime

router = APIRouter(prefix="/api/money", tags=["money"])
# 使用您的雲端 Redis
r = redis.Redis(
    host='redis-11812.c326.us-east-1-3.ec2.cloud.redislabs.com',
    port=11812,
    decode_responses=True,
    username="default",
    password="peayWIVDRyeiuuVFDTeBE3T7Ia75H4wT",
)

# 預設類別 Key
CAT_KEY = "user:money:categories" # Hash: { "飲食": "9000", "交通": "1000" }

# get_data 也要修改讀取邏輯
@router.get("/")
async def get_data():
    try:
        raw_tx = r.lrange("money:transactions", 0, -1)
        transactions = [json.loads(x) for x in raw_tx]
        raw_cats = r.hgetall(CAT_KEY)
        
        categories = []
        cat_stats = {} # { "飲食": { spent: 100, budget: 1000, type: 'expense' } }

        # 解析類別設定
        for name, data_str in raw_cats.items():
            try:
                data = json.loads(data_str) # 嘗試解析 JSON
                cat_stats[name] = {"spent": 0, "budget": int(data['budget']), "type": data.get('type', 'expense')}
            except:
                # 相容舊資料 (純數字)
                cat_stats[name] = {"spent": 0, "budget": int(data_str), "type": 'expense'}

        income = 0
        expense = 0
        
        for tx in transactions:
            amt = int(tx['amount'])
            if tx['type'] == 'income': income += amt
            else: expense += amt
            
            if tx['category'] in cat_stats:
                cat_stats[tx['category']]['spent'] += amt

        for name, data in cat_stats.items():
            status = "normal"
            if data['type'] == 'expense' and data['spent'] > data['budget']: status = "over"
            
            categories.append({
                "name": name, "budget": data['budget'], "spent": data['spent'], 
                "status": status, "type": data['type']
            })
            
        return JSONResponse({
            "transactions": transactions,
            "total_income": income, "total_expense": expense, "balance": income - expense,
            "categories": categories
        })
    except Exception as e: return JSONResponse({"transactions": [], "categories": []})

@router.post("/category/add")
async def add_category(name: str = Form(...), budget: int = Form(...), type: str = Form("expense")):
    # 儲存結構改為 JSON 以包含類型
    data = json.dumps({"budget": budget, "type": type})
    r.hset(CAT_KEY, name, data)
    return {"status": "success"}

@router.post("/category/delete")
async def delete_category(name: str = Form(...)):
    r.hdel(CAT_KEY, name)
    return {"status": "success"}

@router.post("/add")
async def add_transaction(item: str = Form(...), amount: int = Form(...), date: str = Form(...), type: str = Form(...), category: str = Form(...), note: str = Form("")):
    tx = {
        "id": str(uuid.uuid4()), "item": item, "amount": amount, "date": date,
        "type": type, "category": category, "note": note
    }
    r.lpush("money:transactions", json.dumps(tx))
    return {"status": "success"}

@router.post("/delete")
async def delete_transaction(id: str = Form(...)):
    raw_tx = r.lrange("money:transactions", 0, -1)
    for item in raw_tx:
        if json.loads(item)['id'] == id:
            r.lrem("money:transactions", 1, item)
            break
    return {"status": "success"}

@router.post("/reset")
async def reset_money():
    r.delete("money:transactions")
    # 不刪除類別設定，只刪除交易
    return {"status": "success"}
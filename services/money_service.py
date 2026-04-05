from database import Transaction, Category

def get_money_summary(db, user_email):
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
        if t.type == 'income': 
            income += t.amount
        else: 
            expense += t.amount
        
        if t.category in cat_spent:
            cat_spent[t.category] += t.amount

    formatted_cats = []
    for c in cats:
        status = "normal"
        if c.type == 'expense' and c.budget > 0 and cat_spent[c.name] > c.budget: 
            status = "over"
        
        formatted_cats.append({
            "name": c.name, "budget": c.budget, "spent": cat_spent[c.name], 
            "status": status, "type": c.type
        })
        
    return {
        "transactions": formatted_txs,
        "total_income": income, 
        "total_expense": expense, 
        "balance": income - expense,
        "categories": formatted_cats
    }

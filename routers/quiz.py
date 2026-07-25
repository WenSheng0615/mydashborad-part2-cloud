import uuid
import json
import random
from datetime import datetime
from fastapi import APIRouter, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse, Response
from database import get_db, get_session_info, QuizBank, QuizQuestion, QuizOption, ExamSession, ExamAnswer

router = APIRouter(prefix="/api/quiz", tags=["quiz"])

def _require_user(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    return get_session_info(session_id)


# ── 題庫 CRUD ──────────────────────────────────────────

@router.get("/banks")
async def list_banks(request: Request):
    session = _require_user(request)
    if not session:
        return JSONResponse({"banks": []})
    db = get_db()
    banks = db.query(QuizBank).filter(QuizBank.user_email == session.user_email).order_by(QuizBank.created_at.desc()).all()
    result = []
    for b in banks:
        count = db.query(QuizQuestion).filter(QuizQuestion.bank_id == b.id).count()
        result.append({"id": b.id, "name": b.name, "description": b.description, "count": count, "created_at": b.created_at})
    db.close()
    return JSONResponse({"banks": result})

@router.post("/banks/add")
async def add_bank(request: Request, name: str = Form(...), description: str = Form("")):
    session = _require_user(request)
    if not session:
        return JSONResponse({"status": "unauthorized"}, 401)
    db = get_db()
    bank = QuizBank(
        id=str(uuid.uuid4()),
        user_email=session.user_email,
        name=name,
        description=description,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    db.add(bank)
    db.commit()
    result = {"id": bank.id, "name": bank.name, "description": bank.description, "count": 0, "created_at": bank.created_at}
    db.close()
    return JSONResponse({"status": "success", "bank": result})

@router.post("/banks/edit")
async def edit_bank(request: Request, bank_id: str = Form(...), name: str = Form(...), description: str = Form("")):
    session = _require_user(request)
    if not session:
        return JSONResponse({"status": "unauthorized"}, 401)
    db = get_db()
    bank = db.query(QuizBank).filter(QuizBank.id == bank_id, QuizBank.user_email == session.user_email).first()
    if not bank:
        db.close()
        return JSONResponse({"status": "not_found"}, 404)
    bank.name = name
    bank.description = description
    db.commit()
    result = {"id": bank.id, "name": bank.name, "description": bank.description}
    db.close()
    return JSONResponse({"status": "success", "bank": result})

@router.post("/banks/delete")
async def delete_bank(request: Request, bank_id: str = Form(...)):
    session = _require_user(request)
    if not session:
        return JSONResponse({"status": "unauthorized"}, 401)
    db = get_db()
    # 刪除底下的選項與題目
    questions = db.query(QuizQuestion).filter(QuizQuestion.bank_id == bank_id).all()
    for q in questions:
        db.query(QuizOption).filter(QuizOption.question_id == q.id).delete()
    db.query(QuizQuestion).filter(QuizQuestion.bank_id == bank_id).delete()
    db.query(QuizBank).filter(QuizBank.id == bank_id, QuizBank.user_email == session.user_email).delete()
    db.commit()
    db.close()
    return JSONResponse({"status": "success"})


# ── 題目 CRUD ──────────────────────────────────────────

@router.get("/questions")
async def list_questions(request: Request, bank_id: str):
    session = _require_user(request)
    if not session:
        return JSONResponse({"questions": []})
    db = get_db()
    questions = db.query(QuizQuestion).filter(QuizQuestion.bank_id == bank_id).order_by(QuizQuestion.created_at.asc()).all()
    result = []
    for q in questions:
        options = db.query(QuizOption).filter(QuizOption.question_id == q.id).all()
        result.append({
            "id": q.id,
            "content": q.content,
            "type": q.type,
            "tag": q.tag,
            "options": [{"id": o.id, "text": o.text, "is_correct": o.is_correct} for o in options]
        })
    db.close()
    return JSONResponse({"questions": result})

@router.post("/questions/add")
async def add_question(request: Request):
    session = _require_user(request)
    if not session:
        return JSONResponse({"status": "unauthorized"}, 401)
    body = await request.json()
    bank_id = body.get("bank_id")
    content = body.get("content", "").strip()
    q_type = body.get("type", "single")  # single / multiple
    tag = body.get("tag", "").strip()
    options = body.get("options", [])  # [{text, is_correct}]

    if not content or not bank_id or len(options) < 2:
        return JSONResponse({"status": "invalid"}, 400)

    db = get_db()
    q = QuizQuestion(
        id=str(uuid.uuid4()),
        bank_id=bank_id,
        content=content,
        type=q_type,
        tag=tag,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    db.add(q)
    opt_list = []
    for o in options:
        opt = QuizOption(id=str(uuid.uuid4()), question_id=q.id, text=o["text"], is_correct=o.get("is_correct", False))
        db.add(opt)
        opt_list.append({"id": opt.id, "text": opt.text, "is_correct": opt.is_correct})
    db.commit()
    result = {"id": q.id, "content": q.content, "type": q.type, "tag": q.tag, "options": opt_list}
    db.close()
    return JSONResponse({"status": "success", "question": result})

@router.post("/questions/edit")
async def edit_question(request: Request):
    session = _require_user(request)
    if not session:
        return JSONResponse({"status": "unauthorized"}, 401)
    body = await request.json()
    question_id = body.get("question_id")
    content = body.get("content", "").strip()
    q_type = body.get("type", "single")
    tag = body.get("tag", "").strip()
    options = body.get("options", [])

    if not content or not question_id or len(options) < 2:
        return JSONResponse({"status": "invalid"}, 400)

    db = get_db()
    q = db.query(QuizQuestion).filter(QuizQuestion.id == question_id).first()
    if not q:
        db.close()
        return JSONResponse({"status": "not_found"}, 404)

    q.content = content
    q.type = q_type
    q.tag = tag

    db.query(QuizOption).filter(QuizOption.question_id == question_id).delete()
    opt_list = []
    for o in options:
        opt = QuizOption(id=str(uuid.uuid4()), question_id=question_id, text=o["text"], is_correct=o.get("is_correct", False))
        db.add(opt)
        opt_list.append({"id": opt.id, "text": opt.text, "is_correct": opt.is_correct})
    db.commit()
    result = {"id": q.id, "content": q.content, "type": q.type, "tag": q.tag, "options": opt_list}
    db.close()
    return JSONResponse({"status": "success", "question": result})

@router.post("/questions/delete")
async def delete_question(request: Request, question_id: str = Form(...)):
    session = _require_user(request)
    if not session:
        return JSONResponse({"status": "unauthorized"}, 401)
    db = get_db()
    db.query(QuizOption).filter(QuizOption.question_id == question_id).delete()
    db.query(QuizQuestion).filter(QuizQuestion.id == question_id).delete()
    db.commit()
    db.close()
    return JSONResponse({"status": "success"})


# ── 標籤 ──────────────────────────────────────────

@router.get("/tags")
async def list_tags(request: Request, bank_id: str):
    session = _require_user(request)
    if not session:
        return JSONResponse({"tags": []})
    db = get_db()
    questions = db.query(QuizQuestion).filter(QuizQuestion.bank_id == bank_id).all()
    counts = {}
    for q in questions:
        key = q.tag or "未分類"
        counts[key] = counts.get(key, 0) + 1
    db.close()
    result = [{"tag": k, "count": v} for k, v in counts.items()]
    return JSONResponse({"tags": result, "total": len(questions)})


# ── 練習模式 ──────────────────────────────────────────

@router.get("/practice")
async def get_practice(request: Request, bank_id: str, tags: str = None):
    session = _require_user(request)
    if not session:
        return JSONResponse({"questions": []})
    db = get_db()
    questions = db.query(QuizQuestion).filter(QuizQuestion.bank_id == bank_id).all()
    if tags:
        tag_list = set(tags.split(","))
        questions = [q for q in questions if (q.tag or "未分類") in tag_list]
    result = []
    for q in questions:
        options = db.query(QuizOption).filter(QuizOption.question_id == q.id).all()
        opts = [{"id": o.id, "text": o.text, "is_correct": o.is_correct} for o in options]
        random.shuffle(opts)
        result.append({"id": q.id, "content": q.content, "type": q.type, "options": opts})
    random.shuffle(result)
    db.close()
    return JSONResponse({"questions": result})


# ── JSON 匯入 ──────────────────────────────────────────

@router.post("/import")
async def import_questions(request: Request, bank_id: str = Form(...), file: UploadFile = File(...)):
    session = _require_user(request)
    if not session:
        return JSONResponse({"status": "unauthorized"}, 401)

    try:
        raw = await file.read()
        items = json.loads(raw.decode("utf-8-sig"))
    except Exception:
        return JSONResponse({"status": "invalid_json"}, 400)

    if not isinstance(items, list):
        return JSONResponse({"status": "invalid_json"}, 400)

    db = get_db()
    added = 0
    updated = 0
    skipped = 0

    existing = {
        q.content: q
        for q in db.query(QuizQuestion).filter(QuizQuestion.bank_id == bank_id).all()
    }

    for item in items:
        if not item.get("isEnabled", True):
            skipped += 1
            continue

        content = (item.get("name") or "").strip()
        if not content:
            skipped += 1
            continue

        raw_type = item.get("type", "單選題")
        if raw_type in ("多選題", "複選題"):
            q_type = "multiple"
        else:
            q_type = "single"

        # 解析選項
        raw_opts = item.get("options")
        if isinstance(raw_opts, dict):
            # 單選題格式：{"A": "...", "B": "..."}
            answer_key = str(item.get("answer", "")).strip().upper()
            opt_list = []
            for k in sorted(raw_opts.keys()):
                opt_list.append({
                    "text": raw_opts[k],
                    "is_correct": (k.upper() == answer_key)
                })
        elif isinstance(raw_opts, list):
            # 複選題格式：["選項1", "選項2", ...]
            correct_texts = set(item.get("answers", []))
            opt_list = [
                {"text": o, "is_correct": (o in correct_texts)}
                for o in raw_opts
            ]
        else:
            skipped += 1
            continue

        if len(opt_list) < 2:
            skipped += 1
            continue

        tag = (item.get("tag") or "").strip()

        if content in existing:
            # 題目已存在：補上/更新分類標籤與類型，不重複新增
            q = existing[content]
            q.tag = tag
            q.type = q_type
            updated += 1
            continue

        q = QuizQuestion(
            id=str(uuid.uuid4()),
            bank_id=bank_id,
            content=content,
            type=q_type,
            tag=tag,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        db.add(q)
        for o in opt_list:
            db.add(QuizOption(
                id=str(uuid.uuid4()),
                question_id=q.id,
                text=o["text"],
                is_correct=o["is_correct"]
            ))
        added += 1

    db.commit()
    db.close()
    return JSONResponse({"status": "success", "added": added, "updated": updated, "skipped": skipped})


# ── 範例 JSON 下載 ──────────────────────────────────────────

@router.get("/sample")
async def download_sample():
    sample = [
        {
            "type": "單選題",
            "name": "（範例）以下哪個關鍵字用來定義 Python 函式？",
            "options": {
                "A": "function",
                "B": "def",
                "C": "fun",
                "D": "define"
            },
            "answer": "B",
            "isEnabled": True,
            "tag": "單選題",
            "remark": "第1題"
        },
        {
            "type": "單選題",
            "name": "（範例）HTTP 狀態碼 404 代表什麼？",
            "options": {
                "A": "伺服器錯誤",
                "B": "請求成功",
                "C": "找不到資源",
                "D": "未授權"
            },
            "answer": "C",
            "isEnabled": True,
            "tag": "單選題",
            "remark": "第2題"
        },
        {
            "type": "多選題",
            "name": "（範例）下列哪些是物件導向程式設計的核心概念？",
            "options": [
                "封裝（Encapsulation）",
                "繼承（Inheritance）",
                "編譯（Compilation）",
                "多型（Polymorphism）"
            ],
            "answers": [
                "封裝（Encapsulation）",
                "繼承（Inheritance）",
                "多型（Polymorphism）"
            ],
            "isEnabled": True,
            "tag": "複選題",
            "remark": "第3題"
        },
        {
            "type": "多選題",
            "name": "（範例）下列哪些是關聯式資料庫的特性？",
            "options": [
                "以表格（Table）儲存資料",
                "支援 SQL 查詢語言",
                "資料以鍵值對（Key-Value）儲存",
                "透過主鍵（Primary Key）唯一識別每筆資料"
            ],
            "answers": [
                "以表格（Table）儲存資料",
                "支援 SQL 查詢語言",
                "透過主鍵（Primary Key）唯一識別每筆資料"
            ],
            "isEnabled": True,
            "tag": "複選題",
            "remark": "第4題"
        }
    ]
    content = json.dumps(sample, ensure_ascii=False, indent=2)
    return Response(
        content=content.encode("utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename*=UTF-8''quiz_sample.json"}
    )


# ── 測驗模式 ──────────────────────────────────────────

@router.get("/exam/questions")
async def get_exam_questions(request: Request, bank_id: str, count: int = 10, tags: str = None):
    session = _require_user(request)
    if not session:
        return JSONResponse({"questions": []})
    db = get_db()
    questions = db.query(QuizQuestion).filter(QuizQuestion.bank_id == bank_id).all()
    if tags:
        tag_list = set(tags.split(","))
        questions = [q for q in questions if (q.tag or "未分類") in tag_list]
    random.shuffle(questions)
    questions = questions[:count]
    result = []
    for q in questions:
        options = db.query(QuizOption).filter(QuizOption.question_id == q.id).all()
        opts = [{"id": o.id, "text": o.text, "is_correct": o.is_correct} for o in options]
        random.shuffle(opts)
        result.append({"id": q.id, "content": q.content, "type": q.type, "options": opts})
    db.close()
    return JSONResponse({"questions": result})

@router.post("/exam/submit")
async def submit_exam(request: Request):
    session = _require_user(request)
    if not session:
        return JSONResponse({"status": "unauthorized"}, 401)
    body = await request.json()
    bank_id = body.get("bank_id")
    answers = body.get("answers", [])  # [{question_id, content, type, options, selected}]

    db = get_db()
    bank = db.query(QuizBank).filter(QuizBank.id == bank_id).first()
    bank_name = bank.name if bank else "未知題庫"

    total = len(answers)
    correct_count = 0
    exam_id = str(uuid.uuid4())

    for a in answers:
        q_type = a.get("type", "single")
        options = a.get("options", [])          # [{text, is_correct}]
        selected = set(a.get("selected", []))   # [text, ...]
        correct_set = {o["text"] for o in options if o["is_correct"]}

        if q_type == "single":
            is_correct = (selected == correct_set)
        else:
            is_correct = (selected == correct_set)

        if is_correct:
            correct_count += 1

        db.add(ExamAnswer(
            id=str(uuid.uuid4()),
            session_id=exam_id,
            question_content=a.get("content", ""),
            question_type=q_type,
            options_json=json.dumps(options, ensure_ascii=False),
            selected_json=json.dumps(list(selected), ensure_ascii=False),
            is_correct=is_correct
        ))

    score = round(correct_count / total * 100, 1) if total > 0 else 0
    exam_session = ExamSession(
        id=exam_id,
        user_email=session.user_email,
        bank_id=bank_id,
        bank_name=bank_name,
        total=total,
        correct=correct_count,
        score=score,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    db.add(exam_session)
    db.commit()
    db.close()
    return JSONResponse({"status": "success", "session_id": exam_id, "score": score,
                         "correct": correct_count, "total": total})


# ── 歷史紀錄 ──────────────────────────────────────────

@router.get("/history")
async def get_history(request: Request, bank_id: str = None):
    session = _require_user(request)
    if not session:
        return JSONResponse({"sessions": []})
    db = get_db()
    q = db.query(ExamSession).filter(ExamSession.user_email == session.user_email)
    if bank_id:
        q = q.filter(ExamSession.bank_id == bank_id)
    sessions = q.order_by(ExamSession.created_at.desc()).limit(50).all()
    result = [{"id": s.id, "bank_name": s.bank_name, "total": s.total,
               "correct": s.correct, "score": s.score, "created_at": s.created_at}
              for s in sessions]
    db.close()
    return JSONResponse({"sessions": result})

@router.get("/history/{session_id}")
async def get_history_detail(request: Request, session_id: str):
    session = _require_user(request)
    if not session:
        return JSONResponse({"status": "unauthorized"}, 401)
    db = get_db()
    exam = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.user_email == session.user_email
    ).first()
    if not exam:
        db.close()
        return JSONResponse({"status": "not_found"}, 404)
    answers = db.query(ExamAnswer).filter(ExamAnswer.session_id == session_id).all()
    result_answers = []
    for a in answers:
        result_answers.append({
            "question_content": a.question_content,
            "question_type": a.question_type,
            "options": json.loads(a.options_json),
            "selected": json.loads(a.selected_json),
            "is_correct": a.is_correct
        })
    db.close()
    return JSONResponse({
        "id": exam.id, "bank_name": exam.bank_name,
        "total": exam.total, "correct": exam.correct,
        "score": exam.score, "created_at": exam.created_at,
        "answers": result_answers
    })

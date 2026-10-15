"""Trusted built-in catalog. This is not a third-party code/plugin loader."""
from sqlalchemy.dialects.sqlite import insert
from models import ModulePreference

CATALOG = (
    dict(id="workspace", name="工作空間", core=True, description="Workspace、Project、本機任務與專案筆記", integrations=[]),
    dict(id="settings", name="設定與模組管理", core=True, description="帳號、偏好與模組管理入口", integrations=[]),
    dict(id="notes", name="筆記", core=False, description="獨立筆記 App；專案筆記仍由 Core 管理", integrations=["選用 Firebase 附件"]),
    dict(id="tasks", name="Google 待辦", core=False, description="Google Tasks；與本機專案任務分開", integrations=["Google Tasks"]),
    dict(id="calendar", name="行事曆", core=False, description="合併查看 Google 與選用 iCloud 行事曆", integrations=["Google Calendar", "選用 iCloud CalDAV"]),
    dict(id="drive", name="雲端檔案", core=False, description="瀏覽及管理 Google Drive 檔案", integrations=["Google Drive"]),
    dict(id="music", name="音樂", core=False, description="搜尋與播放音樂", integrations=["YouTube"]),
    dict(id="money", name="記帳", core=False, description="收入、支出與分類", integrations=[]),
    dict(id="chat", name="Keep 隨手記", core=False, description="傳給自己的文字、連結與選用附件", integrations=["選用 Firebase 附件"]),
    dict(id="quiz", name="學習測驗", core=False, description="題庫與練習紀錄", integrations=[]),
)
BY_ID = {module["id"]: module for module in CATALOG}


def enabled(db, owner, module_id):
    preference = db.get(ModulePreference, (owner, module_id))
    return preference is None or preference.enabled


def catalog(db, owner):
    preferences = {p.module_id: p.enabled for p in db.query(ModulePreference).filter_by(user_email=owner)}
    return [dict(module, enabled=module["core"] or preferences.get(module["id"], True)) for module in CATALOG]


def set_enabled(db, owner, module_id, value):
    statement = insert(ModulePreference).values(user_email=owner, module_id=module_id, enabled=value)
    db.execute(statement.on_conflict_do_update(index_elements=["user_email", "module_id"], set_={"enabled": value}))

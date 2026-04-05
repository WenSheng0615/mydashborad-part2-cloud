import sqlite3
import os

db_path = os.path.join(os.getcwd(), "focusflow.db")
print(f"正在更新資料庫: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # 嘗試增加欄位
    cursor.execute("ALTER TABLE notes ADD COLUMN image_url TEXT")
    conn.commit()
    print("✅ 成功補上 image_url 欄位！")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("ℹ️ image_url 欄位已經存在，無需更新。")
    else:
        print(f"❌ 發生錯誤: {e}")
except Exception as e:
    print(f"❌ 發生未知錯誤: {e}")
finally:
    if 'conn' in locals():
        conn.close()

import os
import firebase_admin
from firebase_admin import credentials, storage
from datetime import datetime, timedelta

# 初始化 Firebase
def init_firebase():
    # 檢查是否已經初始化過，避免 uvicorn reload 報錯
    try:
        firebase_admin.get_app()
        print("ℹ️ Firebase 已經初始化過，跳過。")
        return
    except ValueError:
        pass # 尚未初始化，繼續執行

    key_path = os.getenv("FIREBASE_KEY_FILE")
    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
    
    if key_path and os.path.exists(key_path):
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred, {
            'storageBucket': bucket_name
        })
        print(f"🔥 Firebase 成功初始化，儲存桶：{bucket_name}")
    else:
        print("⚠️ 找不到 Firebase 金鑰檔案，略過初始化。")

def upload_file(file_path, destination_blob_name):
    """將本地檔案上傳到 Firebase Storage"""
    bucket = storage.bucket()
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(file_path)
    # 產生一個有效期限為 10 年的下載連結
    url = blob.generate_signed_url(expiration=timedelta(days=3650))
    return url

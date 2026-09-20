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
    
    if not key_path or not bucket_name or not os.path.isfile(key_path):
        return False
    try:
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred, {'storageBucket': bucket_name})
        return True  # Configuration loaded, not a remote availability check.
    except Exception:
        import logging
        logging.getLogger(__name__).warning("Optional attachment storage unavailable; Core remains enabled")
        return False

def file_reference(destination_blob_name):
    from urllib.parse import quote
    return "/api/files/download?object=" + quote(destination_blob_name, safe="")

def upload_file(file_path, destination_blob_name):
    bucket = storage.bucket()
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(file_path)
    return file_reference(destination_blob_name)

def signed_download(destination_blob_name):
    blob = storage.bucket().blob(destination_blob_name)
    return blob.generate_signed_url(version="v4", expiration=timedelta(minutes=15),
                                    response_disposition="attachment")

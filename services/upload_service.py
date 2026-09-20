"""Bounded uploads with random temporary paths and verified image content."""
import tempfile
import warnings
from pathlib import Path, PureWindowsPath
from contextlib import asynccontextmanager
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError
from config import BASE_DIR

CHUNK_SIZE = 64 * 1024
IMAGE_LIMIT = 10 * 1024 * 1024
FILE_LIMIT = 20 * 1024 * 1024

def verify_image(path):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.width * image.height > 25_000_000 or image.format not in {"PNG", "JPEG", "WEBP", "GIF"}:
                    raise ValueError()
                suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "GIF": ".gif"}[image.format]
                image.verify()
                return suffix
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(415, "請上傳有效的 PNG、JPEG、WebP 或 GIF 圖片（最多 2500 萬像素）")

@asynccontextmanager
async def bounded_upload(upload, *, image_only=False):
    directory = BASE_DIR / "temp"
    directory.mkdir(exist_ok=True)
    path = None
    limit = IMAGE_LIMIT if image_only else FILE_LIMIT
    try:
        size = 0
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
            path = Path(stream.name)
            while chunk := await upload.read(CHUNK_SIZE):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"檔案不得超過 {limit // (1024 * 1024)} MB")
                stream.write(chunk)
        if not size:
            raise HTTPException(422, "檔案不可為空")
        suffix = await run_in_threadpool(verify_image, path) if image_only else ""
        name = PureWindowsPath(upload.filename or "file").name.replace("\x00", "")[:200] or "file"
        yield path, size, name, suffix
    finally:
        if path:
            path.unlink(missing_ok=True)
        await upload.close()

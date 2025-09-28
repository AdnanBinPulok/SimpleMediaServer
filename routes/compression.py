from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi import APIRouter, Form, UploadFile, File
from fastapi.exceptions import HTTPException
import os
import datetime
import asyncio
import mimetypes
import traceback
import aiofiles

from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/api",tags=["File"])

from services.logging import logger

from modules.rate_limiter import RateLimiter
rate_limiter = RateLimiter(times=20, seconds=5)

from settings.config import ApiConfig
from services.database import files_db

from modules.functions import fetch_date
from modules.functions import authorize_admin

import asyncio
from io import BytesIO
from PIL import Image, ExifTags


def _fix_orientation(img: Image.Image) -> Image.Image:
    """Auto-rotate image according to EXIF data (from phones)."""
    try:
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == 'Orientation':
                break
        exif = img._getexif()
        if exif is None:
            return img
        o = exif.get(orientation, None)
        if o == 3:
            img = img.rotate(180, expand=True)
        elif o == 6:
            img = img.rotate(270, expand=True)
        elif o == 8:
            img = img.rotate(90, expand=True)
    except Exception:
        pass
    return img


def _compress_bytes_sync(
    input_bytes: bytes,
    quality: int = 75,
    max_width: int | None = None,
    to_webp: bool = False,
    lossless: bool = False
) -> bytes:
    """Synchronous compression from bytes → bytes."""
    img = Image.open(BytesIO(input_bytes))
    img = _fix_orientation(img)

    # Resize if needed
    if max_width and img.width > max_width:
        ratio = max_width / float(img.width)
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # Output buffer
    out_buffer = BytesIO()

    # Decide format
    if to_webp:
        img.save(out_buffer, "WEBP", quality=quality, method=6, lossless=lossless)
    else:
        if img.format and img.format.upper() in ["JPEG", "JPG"]:
            img = img.convert("RGB")
            img.save(out_buffer, "JPEG", quality=quality, optimize=True, progressive=True)

        elif img.format and img.format.upper() == "PNG":
            img.save(out_buffer, "PNG", optimize=True)

        else:
            # fallback → WebP
            img.save(out_buffer, "WEBP", quality=quality, method=6)

    return out_buffer.getvalue()


async def compress_image_bytes(
    input_bytes: bytes,
    quality: int = 75,
    max_width: int | None = None,
    to_webp: bool = False,
    lossless: bool = False
) -> bytes:
    """Async wrapper: compress image (bytes → bytes)."""
    return await asyncio.to_thread(
        _compress_bytes_sync,
        input_bytes,
        quality,
        max_width,
        to_webp,
        lossless
    )

async def replace_file(storage_path: str, new_bytes: bytes) -> None:
    """Replace the contents of a file with new bytes."""
    try:
        async with aiofiles.open(storage_path, "wb") as f:
            await f.write(new_bytes)
            return True
    except Exception as e:
        logger.error(f"Error replacing file {storage_path}: {e}")
        return False

async def create_image_compression_task(
    storage_path: str,
    quality: int = 75,
    max_width: int | None = None,
    to_webp: bool = False,
    lossless: bool = False
):
    try:
        async with aiofiles.open(storage_path, "rb") as f:
            input_bytes = await f.read()
            compressed_bytes = await compress_image_bytes(
                input_bytes,
                quality=quality,
                max_width=max_width,
                to_webp=to_webp,
                lossless=lossless
            )
            success = await replace_file(storage_path, compressed_bytes)
            if not success:
                logger.error(f"Failed to replace file {storage_path}")
                return
            logger.success(f"Successfully compressed image {storage_path}")
    except Exception as e:
        logger.error(f"Error compressing image {storage_path}: {e}")

@router.post("/compress/{file_path}", dependencies=[Depends(rate_limiter), Depends(authorize_admin)])
async def compress_file(request: Request, file_path: str):
    try:
        file_data = await files_db.get_file(file_path=file_path)
        if not file_data:
            raise HTTPException(status_code=404, detail="File not found")
        
        if file_data.get("expires_at") and fetch_date(file_data.get("expires_at")) < datetime.datetime.now(datetime.timezone.utc):
            raise HTTPException(status_code=410, detail="File has expired")

        body = await request.json()

        try:
            quality = int(body.get("quality", 75)) if body.get("quality", 75) else 75
            max_width = int(body.get("max_width", None)) if body.get("max_width", None) else None
            to_webp = bool(body.get("to_webp", False)) if body.get("to_webp", False) else False
            lossless = bool(body.get("lossless", False)) if body.get("lossless", False) else False
        except ValueError:
            return JSONResponse(status_code=400, content={"message": "Invalid query parameters"})

        storage_path = file_data.get("storage_path")

        try:
            await asyncio.create_task(create_image_compression_task(
                storage_path,
                quality=quality,
                max_width=max_width,
                to_webp=to_webp,
                lossless=lossless
            ))
        except Exception as e:
            logger.error(f"Error creating compression task for {storage_path}: {e}")
            raise HTTPException(status_code=500, detail="Error creating compression task")

        return JSONResponse(content={"message": "File compressed successfully"})
    except Exception as e:
        logger.error(f"Error compressing file {file_path}: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"message": "Error compressing file"})
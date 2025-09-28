from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi import APIRouter, Form, UploadFile, File
from fastapi.exceptions import HTTPException
import os
import datetime
import asyncio
import mimetypes

from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/file",tags=["File"])

from services.logging import logger

from modules.rate_limiter import RateLimiter
rate_limiter = RateLimiter(times=200, seconds=5)

from settings.config import ApiConfig
from services.database import files_db

from modules.functions import fetch_date


templates = Jinja2Templates(directory="static")

def set_cors_headers(response: Response):
    response.headers["Access-Control-Allow-Origin"] = "*"  # allow any origin
    response.headers["X-Content-Type-Options"] = "nosniff" # prevent MIME sniffing
    return response


async def serve_file(request: Request, file_path: str, as_download: bool = False):
    """
    Serve a file from storage for either viewing or downloading.
    
    Args:
        request: The request object
        file_path: The path to the file
        as_download: Whether to serve the file as a download or for viewing
    """
    file_data = await files_db.get_file(file_path=file_path)
    if not file_data:
        raise HTTPException(status_code=404, detail="File not found")
    
    print(file_data.get("expires_at"))
    print(type(file_data.get("expires_at")))
    if file_data.get("expires_at") and fetch_date(file_data.get("expires_at")) < datetime.datetime.now(datetime.timezone.utc):
        raise HTTPException(status_code=410, detail="File has expired")

    storage_path = file_data.get("storage_path")

    if not storage_path or not os.path.exists(storage_path):
        raise HTTPException(status_code=404, detail="File not found in storage")
    
    # Get the content type, falling back to guessing from file extension if needed
    content_type = file_data.get("file_type")
    if not content_type or content_type == "application/octet-stream":
        guessed_type, _ = mimetypes.guess_type(file_data.get("file_name", ""))
        content_type = guessed_type or "application/octet-stream"
    
    # Update access count and last accessed time
    try:
        asyncio.create_task(files_db.update_file_access(file_path))
    except Exception as e:
        logger.warning(f"Error updating file access: {e}")
    
    # For view mode, prepare specialized responses for different file types
    if not as_download:
        # Create a streaming response for videos and audio files
        if content_type.startswith('video/') or content_type.startswith('audio/'):
            def file_iterator():
                with open(storage_path, 'rb') as f:
                    while chunk := f.read(8192):  # 8KB chunks
                        yield chunk
            
            response = StreamingResponse(
                file_iterator(), 
                media_type=content_type
            )
            response.headers["Content-Disposition"] = f"inline; filename={file_data.get('file_name')}"
            response = set_cors_headers(response)
            return response
            
        # For PDFs, ensure they open in the browser
        elif content_type == 'application/pdf':
            response = FileResponse(
                storage_path, 
                media_type=content_type
            )
            response.headers["Content-Disposition"] = f"inline; filename={file_data.get('file_name')}"
            response = set_cors_headers(response)
            return response
            
        # For images, ensure they display directly
        elif content_type.startswith('image/'):
            response = FileResponse(
                storage_path, 
                media_type=content_type
            )
            response = set_cors_headers(response)
            return response

    # Default FileResponse for downloads or any other file types
    response = FileResponse(
        storage_path, 
        media_type=content_type, 
        filename=file_data.get("file_name")
    )

    response = set_cors_headers(response)

    # Set appropriate content disposition based on the action
    disposition = "attachment" if as_download else "inline"
    response.headers["Content-Disposition"] = f"{disposition}; filename={file_data.get('file_name')}"
    
    return response


@router.get("/view/{file_path}", response_class=Response, dependencies=[Depends(rate_limiter)])
async def view_file(request: Request, file_path: str):
    """
    Serve a file from the static directory for viewing in the browser.
    Media files like videos, audio, PDFs, and images will be displayed inline.
    """
    return await serve_file(request, file_path, as_download=False)


@router.get("/download/{file_path}", response_class=FileResponse, dependencies=[Depends(rate_limiter)])
async def download_file(request: Request, file_path: str):
    """
    Force download a file from the storage directory.
    """
    return await serve_file(request, file_path, as_download=True)

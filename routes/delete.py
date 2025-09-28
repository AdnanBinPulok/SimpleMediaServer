from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi import APIRouter, Form, UploadFile, File
from fastapi.exceptions import HTTPException
import os
import datetime
import asyncio

from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/api", tags=["API"])

from services.logging import logger

from modules.rate_limiter import RateLimiter
rate_limiter = RateLimiter(times=20, seconds=5)

from settings.config import ApiConfig
from services.database import files_db

from modules.functions import fetch_date,authorize_admin


    

@router.delete("/delete/{file_path}", dependencies=[Depends(rate_limiter), Depends(authorize_admin)])
async def delete_file(request: Request, file_path: str):
    """
    Delete a file from the server.
    
    Args:
        request: The request object
        file_path: The path to the file to be deleted
    """

    file_data = await files_db.get_file(file_path=file_path)
    if not file_data:
        raise HTTPException(status_code=404, detail="File not found")
    
    if file_data.get("expires_at") and fetch_date(file_data.get("expires_at")) < datetime.datetime.now(datetime.timezone.utc):
        raise HTTPException(status_code=410, detail="File has expired")

    storage_path = file_data.get("storage_path")

    if not storage_path or not os.path.exists(storage_path):
        raise HTTPException(status_code=404, detail="File not found in storage")
    
    try:
        os.remove(storage_path)
        await files_db.delete_file(file_path=file_path)
        return JSONResponse(content={"message": "File deleted successfully"}, status_code=200)
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(status_code=500, detail="Error deleting file")
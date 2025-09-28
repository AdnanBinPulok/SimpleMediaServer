from fastapi import APIRouter, Depends, Request, Response, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import os
import uuid
import datetime
import mimetypes
import shutil
import asyncio
from typing import Optional


from services.logging import logger
from settings.config import ApiConfig
from services.database import files_db
from modules.rate_limiter import RateLimiter

from modules.functions import fetch_date

# Configure rate limiter for uploads - slightly more restrictive
rate_limiter = RateLimiter(times=10, seconds=10)

# Create router with prefix
router = APIRouter(prefix="/api", tags=["API"])

# Ensure storage directory exists
STORAGE_DIR = "storage"
os.makedirs(STORAGE_DIR, exist_ok=True)

from modules.functions import authorize_admin

def get_safe_filename(filename: str) -> str:
    """
    Generate a safe filename by combining a UUID with the original extension
    """
    if not filename:
        return f"{uuid.uuid4()}.bin"
    
    print(f"Original filename: {filename}")
    
    _, ext = os.path.splitext(filename)
    # Default to .bin if no extension
    ext = ext if ext else ".bin"
    return f"{uuid.uuid4()}{ext}"

def get_unique_path(preferred_path: str) -> str:
    """
    Get a unique file path by appending a number if needed
    """
    if not os.path.exists(preferred_path):
        return preferred_path
    
    base, ext = os.path.splitext(preferred_path)
    counter = 1
    while os.path.exists(f"{base}_{counter}{ext}"):
        counter += 1
    
    return f"{base}_{counter}{ext}"

@router.post("/upload", dependencies=[Depends(rate_limiter), Depends(authorize_admin)])
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    expiry_days: Optional[int] = Form(None),
    description: Optional[str] = Form(None)
):
    """
    Upload a file to the server
    
    Args:
        request: The request object
        file: The file to upload
        expiry_days: Number of days until the file expires (optional)
        description: File description (optional)
    """
    try:
        # Check file size - example limit of 5GB
        file_size_limit = 5 * 1024 * 1024 * 1024  # 5GB
        
        # Save file with a safe name
        print(f"Uploading file: {file}")

        safe_filename = get_safe_filename(file.filename)
        original_filename = file.filename or safe_filename
        
        # Determine storage path
        storage_path = os.path.join(STORAGE_DIR, safe_filename)
        storage_path = get_unique_path(storage_path)
        
        # Stream file to disk
        file_size = 0
        with open(storage_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)  # Read 1MB at a time
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > file_size_limit:
                    # Clean up and abort if file too large
                    buffer.close()
                    os.remove(storage_path)
                    raise HTTPException(
                        status_code=413, 
                        detail=f"File too large, max size is {file_size_limit/(1024*1024)}MB"
                    )
                buffer.write(chunk)
        
        # Detect MIME type
        content_type = file.content_type
        if not content_type or content_type == "application/octet-stream":
            guessed_type, _ = mimetypes.guess_type(original_filename)
            content_type = guessed_type or "application/octet-stream"
        
        # Calculate expiry date if provided
        expires_at = None
        if expiry_days:
            expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=expiry_days)
        
        # Generate URL-friendly file path
        url_path = safe_filename
        
        # Store in database
        file_data_id = await files_db.add_new_file(
            file_path=url_path,
            storage_path=storage_path,
            file_name=original_filename,
            file_type=content_type,
            file_size=file_size,
            expires_at=expires_at
        )
        
        # Return file information
        file_url = f"{ApiConfig.BASE_URL}/file/view/{url_path}"
        download_url = f"{ApiConfig.BASE_URL}/file/download/{url_path}"
        
        logger.info(f"File uploaded: {original_filename}, size: {file_size/1024:.2f}KB, path: {url_path}")
        
        try:
            if expires_at:
                # Schedule deletion of the file after expiry
                logger.info(f"Scheduling deletion for file: {original_filename} at {expires_at}")
                # Use asyncio to schedule the deletion task
                asyncio.create_task(auto_delete_expired_file_task(data_id=file_data_id))
        except Exception as e:
            logger.warning(f"Error scheduling file deletion: {str(e)}")

        return JSONResponse({
            "success": True,
            "file_name": original_filename,
            "file_size": file_size,
            "content_type": content_type,
            "file_url": file_url,
            "download_url": download_url,
            "expires_at": expires_at.isoformat() if expires_at else None
        })
        
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


# on startup, create a task to delete expired files
@router.on_event("startup")
async def startup_event():
    """
    Startup event to delete expired files
    """
    try:
        # Fetch all files from the database
        all_files = await files_db.get_file_they_have_expired_at_not_null()
        
        # Schedule deletion of expired files
        for file_data in all_files:
            asyncio.create_task(auto_delete_expired_file_task(file_data))
    except Exception as e:
        logger.error(f"Error during startup event: {str(e)}")



async def auto_delete_expired_file_task(file_data: dict=None,data_id: int=None):
    """
    Automatically delete expired files
    """
    if not file_data and not data_id:
        logger.error("No file data or ID provided for deletion task")
        return
    if data_id:
        file_data = await files_db.get_file_by_id(data_id)
        if not file_data:
            logger.error(f"File with ID {data_id} not found for deletion task")
            return
    logger.info(f"Scheduled deletion for file: {file_data.get('file_name')}")
    if file_data.get("expires_at"):
        expires_at = fetch_date(file_data.get("expires_at"))
        print(f"Expires at: {expires_at}")
        print(f"Deleting in: {(expires_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds()} seconds")
        await asyncio.sleep((expires_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds())
        try:
            # Delete the file from storage
            os.remove(file_data.get("storage_path"))
            logger.info(f"Expired file deleted: {file_data['file_name']}")
        except Exception as e:
            logger.error(f"Error deleting expired file: {str(e)}")

@router.post("/upload/multiple", dependencies=[Depends(rate_limiter)])
async def upload_multiple_files(
    request: Request,
    files: list[UploadFile] = File(...),
    expiry_days: Optional[int] = Form(None),
    description: Optional[str] = Form(None)
):
    """
    Upload multiple files to the server
    
    Args:
        request: The request object
        files: List of files to upload
        expiry_days: Number of days until the files expire (optional)
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    results = []
    for file in files:
        try:
            # Re-use the upload_file logic for each file
            file_result = await upload_file(
                request=request,
                file=file,
                expiry_days=expiry_days,
                description=description
            )
            results.append(file_result)
        except HTTPException as e:
            results.append({"error": e.detail, "file_name": file.filename})
    
    return JSONResponse({
        "success": True,
        "uploaded_count": len([r for r in results if "error" not in r]),
        "failed_count": len([r for r in results if "error" in r]),
        "files": results
    })

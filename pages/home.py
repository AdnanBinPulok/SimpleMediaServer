from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi import APIRouter, Form, UploadFile, File
from fastapi.exceptions import HTTPException
import os
import datetime
import asyncio

from fastapi.templating import Jinja2Templates

router = APIRouter()

from services.logging import logger

from modules.rate_limiter import RateLimiter
rate_limiter = RateLimiter(times=20, seconds=5)

from settings.config import ApiConfig
from services.database import files_db

from modules.functions import fetch_date


templates = Jinja2Templates(directory="static")


@router.get("/", response_class=HTMLResponse, dependencies=[Depends(rate_limiter)])
async def home(request: Request):
    try:
        return templates.TemplateResponse("pages/home.html", {
            "request": request
        })
    except Exception as e:
        logger.error(f"Error rendering template: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
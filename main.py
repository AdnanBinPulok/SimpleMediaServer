import fastapi
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse

from fastapi.staticfiles import StaticFiles
from fastapi import APIRouter, Form, UploadFile, File
from fastapi.templating import Jinja2Templates
import uvicorn

import asyncio
import os
import traceback

from settings.config import ApiConfig
from services.logging import logger
from services.database import initDatabase



app = FastAPI(
    title=ApiConfig.NAME,
    version=ApiConfig.VERSION,
    description=ApiConfig.DESCRIPTION
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="static")

async def initialize_routes():
    # Add all routers here from ./routes folder
    for file in os.listdir("./routes"):
        if file.endswith(".py"):
            module = file[:-3]
            if module != "__init__":
                module_router = __import__(f"routes.{module}", fromlist=["router"])
                app.include_router(module_router.router)
                logger.info(f"Router {module} included ✅")

async def initialize_pages():
    # Add all routers here from ./pages folder
    for file in os.listdir("./pages"):
        if file.endswith(".py"):
            module = file[:-3]
            if module != "__init__":
                module_router = __import__(f"pages.{module}", fromlist=["router"])
                app.include_router(module_router.router)
                logger.info(f"Router {module} included ✅")

# Custom 404 handler for route not found
@app.exception_handler(404)
async def route_not_found_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api"):
        return JSONResponse(content={"error": "Route not found"}, status_code=404)
    return templates.TemplateResponse("/errors/404.html", {"request": request, "message": "Route not found"}, status_code=404)

@app.exception_handler(429)
async def rate_limit_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api"):
        return JSONResponse(content={"error": "Too many requests"}, status_code=429)
    return templates.TemplateResponse("/errors/429.html", {"request": request, "message": "Too many requests"}, status_code=429)

# General HTTP exception handler
@app.exception_handler(500)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api"):
        return JSONResponse(content={"error": exc.detail}, status_code=exc.status_code)
    return templates.TemplateResponse("/errors/500.html", {"request": request, "message": exc.detail}, status_code=exc.status_code)

@app.exception_handler(410)
async def file_expired_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api"):
        return JSONResponse(content={"error": "File has expired"}, status_code=410)
    return templates.TemplateResponse("/errors/410.html", {"request": request, "message": "File has expired"}, status_code=410)




async def main():
    try:
        # Initialize routes
        await initDatabase()
        await initialize_pages()
        await initialize_routes()

        async def run_api():
            api_config = uvicorn.Config(
                app,
                host=ApiConfig.HOST,
                port=ApiConfig.PORT,
                reload=True
            )
            server = uvicorn.Server(api_config)
            await server.serve()
        tasks = [
            asyncio.create_task(run_api())
        ]
        await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"Error starting server: {traceback.format_exc()}")


if __name__ == "__main__":
    try:
        # Run the main function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
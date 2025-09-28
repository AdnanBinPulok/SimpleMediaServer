
import aiohttp
from services.logging import logger
from settings.config import StorageConfig

from aiohttp import FormData


import datetime
import traceback



async def upload_file(bytes: bytes, filename: str = "uploaded_file", expires_at: datetime.timedelta = None):
    try:
        async with aiohttp.ClientSession() as session:
            logger.debug(f"Uploading file to {StorageConfig.IMAGE_UPLOAD_SERVER_URL}/api/upload")
            
            form = FormData()
            form.add_field(
                name="file",
                value=bytes,
                filename=filename,
                content_type="application/octet-stream"
            )
            if expires_at:
                form.add_field("expiry_days", str(expires_at.days))

            async with session.post(
                f"{StorageConfig.IMAGE_UPLOAD_SERVER_URL}/api/upload",
                headers={"Authorization": f"Bearer {StorageConfig.IMAGE_UPLOAD_SERVER_KEY}"},
                data=form,
                timeout=StorageConfig.TIMEOUT
            ) as response:
                if response.status != 200:
                    return {"success": False, "message": f"Failed to upload image: {response.status} {await response.text()}"}
                
                data = await response.json()
                logger.debug(f"Image upload response: {data}")
                return {
                    "success": True,
                    "file_url": data.get("file_url"),
                    "download_url": data.get("download_url")
                }
    except Exception as e:
        logger.error(f"Error uploading file: {traceback.format_exc()}")
        return {"success": False, "message": str(e)}


async def delete_image(image_url:str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                image_url,
                headers={"Authorization": f"Bearer {StorageConfig.IMAGE_UPLOAD_SERVER_KEY}"},
            ) as response:
                if response.status != 200:
                    return {"success": False, "message": "Failed to delete image"}
                data = await response.json()
                logger.debug(f"Image delete response: {data}")
                return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "message": str(e)}

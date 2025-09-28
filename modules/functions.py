import datetime
from fastapi import Request, HTTPException

from settings.config import ApiConfig



def fetch_date(date_str):
    """
    Convert a date string to a datetime object.
    """
    # 2025-05-11 12:56:56.785356+00:00
    try:
        return datetime.datetime.fromisoformat(date_str).astimezone(datetime.timezone.utc)
    except ValueError:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").astimezone(datetime.timezone.utc)
    except Exception as e:
        print(f"Error parsing date: {e}")
        return None
    
async def authorize_admin(request: Request):
    """
    Check if the user is an admin.
    """
    if not request.headers.get("Authorization"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    authorization = request.headers.get("Authorization")

    if "Bearer" in authorization:
        token = authorization.split(" ")[1]
    else:
        token = authorization

    if token != ApiConfig.MASTER_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    return True
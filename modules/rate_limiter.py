import time
from collections import defaultdict, deque
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="static")


class RateLimiter:
    def __init__(self, times: int, seconds: int):
        self.times = times
        self.seconds = seconds
        self.requests = defaultdict(lambda: deque(maxlen=times))

    async def __call__(self, request: Request):
        client_ip = request.client.host
        current_time = time.time()
        request_times = self.requests[client_ip]

        # Remove timestamps older than the time window
        while request_times and request_times[0] <= current_time - self.seconds:
            request_times.popleft()

        if len(request_times) >= self.times:
            raise HTTPException(status_code=429, detail="Too many requests")

        request_times.append(current_time)
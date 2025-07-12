"""
Rate limiting middleware to prevent abuse.
Implements a simple per-IP rate limit for uploads.
"""
import time
from collections import defaultdict, deque
from typing import Callable, Dict, Deque, Tuple

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to implement per-IP rate limiting.
    Limits upload requests to a configurable number per minute.
    """
    
    def __init__(
        self, 
        app, 
        max_requests: int = 10,
        window_seconds: int = 60,
        upload_path: str = "/api/v1/upload"
    ):
        """
        Initialize the rate limiter.
        
        Args:
            app: The FastAPI application
            max_requests: Maximum number of requests allowed per window
            window_seconds: Time window in seconds
            upload_path: Path to apply rate limiting to
        """
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.upload_path = upload_path
        # Store request timestamps per IP
        self.requests: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=max_requests))
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process each request through the rate limiter.
        
        Args:
            request: The incoming request
            call_next: Function to call the next middleware or endpoint
            
        Returns:
            The response
        """
        # Only apply rate limiting to upload endpoint
        if request.url.path == self.upload_path:
            client_ip = request.client.host
            
            # Check if rate limit is exceeded
            if self._is_rate_limited(client_ip):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded. Please try again later."}
                )
            
            # Record this request
            self._record_request(client_ip)
        
        # Process the request normally
        return await call_next(request)
    
    def _is_rate_limited(self, client_ip: str) -> bool:
        """
        Check if the client IP has exceeded the rate limit.
        
        Args:
            client_ip: The client's IP address
            
        Returns:
            True if rate limited, False otherwise
        """
        # If we have max_requests timestamps and the oldest is within the window
        if (len(self.requests[client_ip]) == self.max_requests and 
            time.time() - self.requests[client_ip][0] < self.window_seconds):
            return True
        return False
    
    def _record_request(self, client_ip: str) -> None:
        """
        Record a request timestamp for the client IP.
        
        Args:
            client_ip: The client's IP address
        """
        # Clean up old timestamps outside the window
        current_time = time.time()
        while (self.requests[client_ip] and 
               current_time - self.requests[client_ip][0] > self.window_seconds):
            self.requests[client_ip].popleft()
        
        # Add the current timestamp
        self.requests[client_ip].append(current_time)

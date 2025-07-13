# # In file: Backend/app/main.py

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# # Import the routers
# from app.api.v1.routes_upload import router as http_upload_router, ws_router
# from app.api.v1 import routes_auth, routes_download

# # --- Create a SINGLE FastAPI application instance ---
# app = FastAPI(title="File Transfer Service")

# origins = [
#     "http://localhost:4200",
#     "https://teletransfer.vercel.app"
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # --- MODIFIED: Mount the WebSocket router directly onto the main app ---
# # This is a more robust way to handle complex path parameters in WebSocket URLs.
# app.include_router(ws_router, prefix="/ws_api", tags=["WebSocket Upload"])

# # Include the standard HTTP routers
# app.include_router(routes_auth.router, prefix="/api/v1/auth", tags=["Authentication"])
# app.include_router(http_upload_router, prefix="/api/v1", tags=["Upload"])
# app.include_router(routes_download.router, prefix="/api/v1", tags=["Download"])

# @app.get("/")
# def read_root():
#     return {"message": "Welcome to the File Transfer API"}

# # --- REMOVED: The separate ws_app is no longer necessary ---
# # ws_app = FastAPI(title="File Transfer Service - WebSockets")
# # ws_app.include_router(ws_router)
# # app.mount("/ws_api", ws_app)



# In file: Backend/app/main.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

# Import routers
from app.api.v1.routes_upload import router as upload_router
from app.api.v1 import routes_auth, routes_download
from app.api.v1.routes_logs import router as logs_router

# Import middleware
from app.middleware.rate_limiter import RateLimitMiddleware

# Import settings
from app.core.config import settings

# Create FastAPI application instance
app = FastAPI(
    title="DirectDrive File Service",
    description="File sharing service using Hetzner Storage-Box",
    version="1.0.0"
)

# Configure CORS
# Parse comma-separated origins from environment variable
origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware (10 uploads per minute)
app.add_middleware(
    RateLimitMiddleware,
    max_requests=10,
    window_seconds=60,
    upload_path="/api/v1/upload"
)

# Include the standard HTTP routers
# Auth router is disabled but kept for future use
app.include_router(routes_auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(upload_router, prefix="/api/v1", tags=["Upload"])
app.include_router(routes_download.router, prefix="/api/v1", tags=["Download"])
app.include_router(logs_router, prefix="/api/v1", tags=["Logging"])

# Health check endpoint
@app.get("/healthz")
def health_check():
    return {"status": "ok"}

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to DirectDrive File Service"}
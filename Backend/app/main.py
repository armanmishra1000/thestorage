from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Import the two new routers we just configured
from app.api.v1.routes_upload import router as http_upload_router, ws_router
from app.api.v1 import routes_auth
from app.api.v1 import routes_download

# --- Create the MAIN application for HTTP requests ---
app = FastAPI(title="File Transfer Service - HTTP")

# This is the list of origins that are allowed to make requests.
origins = [
    "http://localhost:4200",
    "https://mitali-frontend.vercel.app",
]

# Add the CORS middleware ONLY to the main HTTP app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the standard HTTP routers
app.include_router(routes_auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(http_upload_router, prefix="/api/v1", tags=["Upload"])
app.include_router(routes_download.router, prefix="/api/v1", tags=["Download"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the File Transfer API"}


# --- Create a SEPARATE sub-application for WebSockets ---
ws_app = FastAPI(title="File Transfer Service - WebSockets")
ws_app.include_router(ws_router)
app.mount("/ws_api", ws_app)
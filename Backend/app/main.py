from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Import the two new routers we just configured
from app.api.v1.routes_upload import router as http_router, ws_router
from app.api.v1 import routes_auth

# --- Create the MAIN application for HTTP requests ---
app = FastAPI(title="File Transfer Service - HTTP")

# This is the list of origins that are allowed to make requests.
origins = [
    "http://localhost:4200",
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
app.include_router(http_router, prefix="/api/v1", tags=["Files"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the File Transfer API"}


# --- Create a SEPARATE sub-application for WebSockets ---
# This app will have NO middleware, avoiding any conflicts.
ws_app = FastAPI(title="File Transfer Service - WebSockets")

# Include ONLY the WebSocket router in this sub-app
ws_app.include_router(ws_router)


# --- Mount the WebSocket sub-app onto the main app ---
# This makes the WebSocket endpoints available under the main application's server process
app.mount("/ws_api", ws_app)
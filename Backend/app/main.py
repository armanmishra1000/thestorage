from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import routes_upload, routes_auth

app = FastAPI(title="File Transfer Service")

# This is the list of origins that are allowed to make requests.
# Your Angular app is running on http://localhost:4200
origins = [
    "http://localhost:4200",
]

# This middleware will apply to both HTTP and WebSocket requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Crucially, we specify the allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(routes_upload.router, prefix="/api/v1", tags=["Files"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the File Transfer API"}
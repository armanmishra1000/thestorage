from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import routes_upload, routes_auth

app = FastAPI(title="File Transfer Service")

# CORS (Cross-Origin Resource Sharing)
# This allows your Angular frontend (running on http://localhost:4200)
# to communicate with your backend (running on http://localhost:8000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # The origin of your frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(routes_upload.router, prefix="/api/v1", tags=["Files"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the File Transfer API"}
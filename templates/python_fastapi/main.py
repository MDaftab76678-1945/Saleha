from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="{{PROJECT_NAME}}", version="1.0.0")

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

@app.get("/health", response_model=HealthResponse)
def health_check():
    return {"status": "healthy", "service": "{{PROJECT_SLUG}}", "version": "1.0.0"}

@app.get("/")
def read_root():
    return {"message": "Welcome to {{PROJECT_NAME}}"}


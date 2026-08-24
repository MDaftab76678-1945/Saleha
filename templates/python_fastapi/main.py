from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

app = FastAPI(title="Saleha Enterprise FastAPI Service", version="1.0.0")

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

@app.get("/health", response_model=HealthResponse)
def health_check():
    return {"status": "healthy", "service": "fastapi-service", "version": "1.0.0"}

@app.get("/")
def read_root():
    return {"message": "Welcome to Saleha AI Microservice"}


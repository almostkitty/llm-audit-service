from fastapi import FastAPI
from app.api.routes import audit


app = FastAPI()
app.include_router(audit.router)

@app.get("/")
def root():
    return {"message": "LLM Audit Service is running"}
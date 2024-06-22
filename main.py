from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi import FastAPI,  File, UploadFile, Form, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from authentication import Authenticator
from dotenv import load_dotenv
import os


load_dotenv()
mongodb_url = os.environ.get("MongoDB_CONNECT")
client = AsyncIOMotorClient(mongodb_url)
db = client.your_database_name

app = FastAPI()

@app.get("/t")
def hello_world():
    return {"status":"active"}

auth = Authenticator(db)

async def login(request: Request):
    try:
        response = await auth.Verify_user(request)
        if isinstance(response, JSONResponse):
            return response
        
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")
    

class URLModel(BaseModel):
    url: List[str]

class ValidateAnswerModel(BaseModel):
    question: str
    userAns: str
    answer: str

class ValidateURLModel(BaseModel):
    url: str

async def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header is missing")
    try:
        payload = await auth.Authorize(authorization)
        return payload
    except HTTPException as e:
        raise e

@app.get("/getQnA")
async def get_qna(user: dict = Depends(verify_token)):
    # Implement your logic here
    return {"message": "QnA data retrieved successfully", "user": user}

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    date: str = Form(...),
    urls: str = Form(...),
    description: str = Form(...),
    user: dict = Depends(verify_token)
):
    
    try:
        datetime.strptime(date, "%d-%m-%Y")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use DD-MM-YYYY")

    
    try:
        url_model = URLModel.parse_raw(urls)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid URL format")

    #
    return {"message": "File uploaded successfully", "user": user}

@app.post("/validateAnswer")
async def validate_answer(data: ValidateAnswerModel, user: dict = Depends(verify_token)):
    return {"message": "Answer validated successfully", "user": user}

@app.post("/validateURL")
async def validate_url(data: ValidateURLModel, user: dict = Depends(verify_token)):
    return {"message": "URL validated successfully", "user": user}


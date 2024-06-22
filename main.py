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
import json
from GeminiWrapper import LLM_PDF_Backend

load_dotenv()
mongodb_url = os.environ.get("MongoDB_CONNECT")
client = AsyncIOMotorClient(mongodb_url)
db = client.Waffle

app = FastAPI()

@app.get("/t")
def hello_world():
    return {"status":"active"}

auth = Authenticator(db)



class URLModel(BaseModel):
    urls: List[str]

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
        print(authorization)
        payload = await auth.Authorize(authorization)
        print("hello:", type(payload))
        return payload
    except HTTPException as e:
        raise e
    
@app.get("/login")
async def login(request: Request):
    try:
        # print(await request.json())
        response = await auth.Verify_user(request)
        if isinstance(response, JSONResponse):
            return response
        
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.get("/getQnA")
async def get_qna(user: dict = Depends(verify_token)):
    # Implement your logic here
    return {"message": "QnA data retrieved successfully", "user": user}

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    date: str = Form(...),
    urls: str = Form(...),
    user: dict = Depends(verify_token)
):
    userCollection = db["data"]
    try:
        parsed_date = datetime.strptime(date, "%d-%m-%Y")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use DD-MM-YYYY")
    try:
        urls_dict = json.loads(urls)
        print(urls_dict)
        url_model = URLModel(**urls_dict)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid URL format")
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(file.file.read())
    data = {
        "user_id": user["sub"],
        "filename": file.filename,
        "file_path": file_location,
        "upload_date": datetime.now(),
        "specified_date": parsed_date,
        "urls": url_model.urls
    }
    fileExists = await userCollection.find_one({"$or": [{ "file_location": file_location},{"user_id": user["sub"]}]})
    if fileExists:
        raise HTTPException(status_code=500, detail="File already exists")
    result = await userCollection.insert_one(data)
    if result.inserted_id:
        return {"message": "File uploaded successfully", "user": user, "file_id": str(result.inserted_id)}
    else:
        raise HTTPException(status_code=500, detail="Failed to upload file")

@app.get("/data")
async def get_data(user: dict = Depends(verify_token)):
    userCollection = db["data"]
    data = await userCollection.find({"user_id": user["sub"]}).to_list(length=100)

    if data:
        return {"data": data}
    else:
        return {"message": "No data found"}

@app.put("/data")
async def update_data(
    file: UploadFile = File(None),
    date: str = Form(None),
    urls: str = Form(None),
    user: dict = Depends(verify_token)
):
    userCollection = db["data"]
    update_data = {}

    if file:
        file_location = f"uploads/{file.filename}"
        with open(file_location, "wb+") as file_object:
            file_object.write(file.file.read())
        update_data["filename"] = file.filename
        update_data["file_path"] = file_location

    if date:
        try:
            parsed_date = datetime.strptime(date, "%d-%m-%Y")
            update_data["specified_date"] = parsed_date
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use DD-MM-YYYY")

    if urls:
        try:
            urls_dict = json.loads(urls)
            url_model = URLModel(**urls_dict)
            update_data["urls"] = url_model.urls
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid URL format")

    if not update_data:
        raise HTTPException(status_code=400, detail="No valid data provided for update")

    result = await userCollection.update_one(
        {"user_id": user["sub"]},
        {"$set": update_data}
    )

    if result.modified_count == 1:
        return {"message": "Data updated successfully"}
    else:
        raise HTTPException(status_code=404, detail="Data not found or no update made")

@app.delete("/data")
async def delete_data(
    user: dict = Depends(verify_token)
):
    userCollection = db["data"]
    result = await userCollection.delete_one(
        {"user_id": user["sub"]}
    )
    if result.deleted_count == 1:
        return {"message": "Data deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Data not found")

@app.post("/validateAnswer")
async def validate_answer(data: ValidateAnswerModel, user: dict = Depends(verify_token)):
    
    return {"message": "Answer validated successfully", "user": user}

@app.post("/validateURL")
async def validate_url(data: ValidateURLModel, user: dict = Depends(verify_token)):
    return {"message": "URL validated successfully", "user": user}


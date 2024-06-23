from fastapi import FastAPI, File, UploadFile, Form, Header, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from authentication import Authenticator
from dotenv import load_dotenv
import os
import json
from GeminiWrapper import LLM_PDF_Backend
import ast
import bson

def convert_mongodb_doc_to_dict(doc):
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
    return doc

load_dotenv()
mongodb_url = os.environ.get("MongoDB_CONNECT")
client = AsyncIOMotorClient(mongodb_url)
db = client.Waffle

app = FastAPI()

@app.get("/t")
def hello_world():
    return {"status": "active"}

auth = Authenticator(db)
generativeAI = None  # Initialize generativeAI to None

async def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header is missing")
    try:
        payload = await auth.Authorize(authorization)
        return payload
    except HTTPException as e:
        raise e

@app.post("/login")
async def login(request: Request):
    try:
        response = await auth.Verify_user(request)
        if isinstance(response, JSONResponse):
            return response
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.get("/getQnA")
async def get_qna(user: dict = Depends(verify_token)):
    global generativeAI
    if not generativeAI:
        raise HTTPException(status_code=500, detail="No file has been uploaded to initialize the generative AI.")
    try:
        question_answer_pairs = ast.literal_eval(generativeAI.getFlashCards())
        return {"message": "QnA data retrieved successfully", "Response": question_answer_pairs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing Error from LLM: {str(e)}")

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    date: str = Form(...),
    urls: str = Form(...),
    authorization: Optional[str] = Header(None)
):
    global generativeAI
    user = await verify_token(authorization)  # Verify token manually in this route
    userCollection = db["data"]

    try:
        parsed_date = datetime.strptime(date, "%d-%m-%Y")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use DD-MM-YYYY")

    try:
        urls_dict = json.loads(urls)
        urls_list = urls_dict.get("urls", [])
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
        "urls": urls_list
    }

    fileExists = await userCollection.find_one({"$or": [{"file_path": file_location}, {"user_id": user["sub"]}]})
    if fileExists:
        raise HTTPException(status_code=500, detail="File already exists")

    result = await userCollection.insert_one(data)
    generativeAI = LLM_PDF_Backend(file_location)
    if result.inserted_id:
        return {"message": "File uploaded successfully", "user": user, "file_id": str(result.inserted_id)}
    else:
        raise HTTPException(status_code=500, detail="Failed to upload file")

@app.get("/data")
async def get_data(authorization: Optional[str] = Header(None)):
    user = await verify_token(authorization)  # Verify token manually in this route
    userCollection = db["data"]
    data = await userCollection.find({"user_id": user["sub"]}).to_list(length=100)
    serialized_data = [convert_mongodb_doc_to_dict(doc) for doc in data]
    if serialized_data:
        return {"data": serialized_data}
    else:
        return {"message": "No data found"}

@app.put("/data")
async def update_data(
    file: UploadFile = File(None),
    date: str = Form(None),
    urls: str = Form(None),
    authorization: Optional[str] = Header(None)
):
    global generativeAI
    user = await verify_token(authorization)  # Verify token manually in this route
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
            urls_list = urls_dict.get("urls", [])
            update_data["urls"] = urls_list
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid URL format")

    if not update_data:
        raise HTTPException(status_code=400, detail="No valid data provided for update")

    result = await userCollection.update_one(
        {"user_id": user["sub"]},
        {"$set": update_data}
    )
    if result.modified_count == 1:
        generativeAI = LLM_PDF_Backend(file_location)
        return {"message": "Data updated successfully"}
    else:
        raise HTTPException(status_code=404, detail="Data not found or no update made")

@app.delete("/data")
async def delete_data(authorization: Optional[str] = Header(None)):
    user = await verify_token(authorization)  # Verify token manually in this route
    userCollection = db["data"]
    result = await userCollection.delete_one({"user_id": user["sub"]})
    if result.deleted_count == 1:
        return {"message": "Data deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Data not found")

@app.post("/validateAnswer")
async def validate_answer(
    question: str = Form(...),
    userAns: str = Form(...),
    answer: str = Form(...),
    authorization: Optional[str] = Header(None)
):
    global generativeAI
    if not generativeAI:
        raise HTTPException(status_code=500, detail="No file has been uploaded to initialize the generative AI.")
    user = await verify_token(authorization)  # Verify token manually in this route
    return {"message": "Answer validated successfully", "Response": generativeAI.validate(question, userAns)}

@app.post("/validateURL")
async def validate_url(
    url: str = Form(...),
    authorization: Optional[str] = Header(None)
):
    user = await verify_token(authorization)  # Verify token manually in this route

    userCollection = db["data"]
    document = userCollection.find_one({"user_id": user["sub"]})
    if document:
        urls = document.get('urls', [])
        url_to_check = "http://example.com"
        
        if url_to_check in urls:
            responseMsg = f"URL '{url_to_check}' exists in the 'urls' array."
        else:
            responseMsg = f"URL '{url_to_check}' does not exist in the 'urls' array."
    else:
        responseMsg = f"Document not found."
    return {"message": "URL validated successfully", "Response": responseMsg}

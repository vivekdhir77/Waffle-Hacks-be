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
from pydantic import BaseModel
from typing import List
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
from starlette.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR


class URLModel(BaseModel):
    urls: List[str]

def convert_mongodb_doc_to_dict(doc):
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
    return doc

load_dotenv()
mongodb_url = os.environ.get("MongoDB_CONNECT")
client = AsyncIOMotorClient(mongodb_url)
db = client.Waffle

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

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

@app.get("/get-qna")
async def get_qna(user: dict = Depends(verify_token)):

    global generativeAI
    userCollection = db["data"]
    data = await userCollection.find({"user_id": user["sub"]}).to_list(length=100)
    serialized_data = [convert_mongodb_doc_to_dict(doc) for doc in data]
    serialized_data[0]["specified_date"] = serialized_data[0]["specified_date"].strftime("%d-%m-%Y")
    if not generativeAI:
        generativeAI = LLM_PDF_Backend(f"uploads/{serialized_data[0]['filename']}")
        # generativeAI = LLM_PDF_Backend(f"uploads/cloudsek.pdf")
        
    print("filepath:", f"uploads/{serialized_data[0]['filename']}")

    if not generativeAI:
        print("No file has been uploaded to initialize the generative AI.")
        raise HTTPException(status_code=500, detail="No file has been uploaded to initialize the generative AI.")
    try:
        question_answer_pairs = generativeAI.getFlashCards()
        x = json.loads(question_answer_pairs)
        y = json.dumps(x)
        print(type(y))
        z = eval(y)
        print(type(z), type(z[0]))
        print("question_answer_pairs:", z)
        return {"message": "QnA data retrieved successfully", "response": z}
    except Exception as e:
        print(f"Parsing Error from LLM: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Parsing Error from LLM: {str(e)}")

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(None),  # Make file optional
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

    update_data = {
        "specified_date": parsed_date,
        "urls": url_model.urls
    }

    if file:
        file_location = f"uploads/{file.filename}"
        with open(file_location, "wb+") as file_object:
            file_object.write(file.file.read())
        update_data["filename"] = file.filename
        update_data["file_path"] = file_location
        update_data["upload_date"] = datetime.now()

    # Check if data exists for this user
    existing_data = await userCollection.find_one({"user_id": user["sub"]})

    if existing_data:
        # Update existing data
        result = await userCollection.update_one(
            {"user_id": user["sub"]},
            {"$set": update_data}
        )
        # generativeAI = LLM_PDF_Backend(file_location)
        if result.modified_count == 1:
            return {"message": "Data updated successfully", "user": user}
        else:
            raise HTTPException(status_code=400, detail="you have made no changes to the data")
    else:
        # Insert new data
        update_data["user_id"] = user["sub"]
        result = await userCollection.insert_one(update_data)
        # generativeAI = LLM_PDF_Backend(file_location)
        if result.inserted_id:
            return {"message": "File uploaded successfully", "user": user, "file_id": str(result.inserted_id)}
        else:
            raise HTTPException(status_code=500, detail="Failed to upload file")

@app.get("/get-data")
async def get_data(authorization: Optional[str] = Header(None)):
    global generativeAI
    user = await verify_token(authorization)  # Verify token manually in this route
    userCollection = db["data"]
    data = await userCollection.find({"user_id": user["sub"]}).to_list(length=100)
    serialized_data = [convert_mongodb_doc_to_dict(doc) for doc in data]
    serialized_data[0]["specified_date"] = serialized_data[0]["specified_date"].strftime("%d-%m-%Y")
    # if not generativeAI:
    #     generativeAI = LLM_PDF_Backend(f"uploads/{serialized_data[0]['filename']}")
    if serialized_data:
        return {"data": serialized_data}
    else:
        return {"message": "No data found"}

@app.delete("/delete-data")
async def delete_data(authorization: Optional[str] = Header(None)):
    user = await verify_token(authorization)  # Verify token manually in this route
    userCollection = db["data"]
    result = await userCollection.delete_one({"user_id": user["sub"]})
    if result.deleted_count == 1:
        return {"message": "Data deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Data not found")

# not using this at the moment except for youtube videos because we're checking the urls in frontend itself.
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
        if url in urls:
            responseMsg = False
        else:
            responseMsg = generativeAI.getCheckWebsite(url)
    else:
        responseMsg = generativeAI.getCheckWebsite(url)
    return {"message": "URL validated successfully", "Response": responseMsg}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)

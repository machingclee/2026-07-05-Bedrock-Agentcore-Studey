import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from src.project_1 import generate_code_using_bedrock, language_meta, save_code_to_s3_bucket

load_dotenv()

app = FastAPI()

# Configure CORS — list every origin allowed to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3030",          # TODO: your frontend origin(s)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", summary="Health check")
async def root():
    return {"message": f"Hello from {os.getenv('APP_NAME', 'FastAPI on Lambda')}"}


@app.post("/project_1", summary="Generate code using Bedrock")
async def generate_code(message: str, language: str):
    print(message, language)

    generated_code = generate_code_using_bedrock(message, language)

    if generated_code:
        current_time = datetime.now().strftime("%H%M%S")
        ext, content_type = language_meta(language)
        s3_key = f"code-output/{current_time}.{ext}"
        s3_bucket = os.getenv("S3_BUCKET_FOR_BERROCK")
        print("code generated: ", generated_code)
        save_code_to_s3_bucket(generated_code, s3_bucket, s3_key, content_type)
    else:
        print("No code was generated")

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Code generation completed and saved to S3.", "s3_bucket": s3_bucket, "s3_key": s3_key}),
    }

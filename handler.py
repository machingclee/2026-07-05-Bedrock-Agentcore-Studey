from mangum import Mangum
from app import app

# AWS Lambda entry point. Mangum adapts the FastAPI ASGI app to Lambda's
# event/response format. serverless.yml `handler.handler` points here.
handler = Mangum(app)

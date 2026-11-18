"""AWS Lambda entry point: the same FastAPI app, behind a Lambda function URL."""

from mangum import Mangum

from app.main import app

handler = Mangum(app, lifespan="off")

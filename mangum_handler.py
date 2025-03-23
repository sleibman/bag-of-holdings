# mangum_handler.py
from mangum import Mangum
from app import app

# Handler for AWS Lambda
handler = Mangum(app)


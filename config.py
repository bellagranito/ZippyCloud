import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "zippy-cloud-dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///zippy_cloud.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")

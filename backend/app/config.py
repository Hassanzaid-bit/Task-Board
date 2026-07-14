import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://taskboard:taskboard_dev_password@localhost:5432/taskboard",
)
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-real-deployments")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MINUTES = int(os.environ.get("JWT_EXPIRES_MINUTES", "480"))

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    PORT: int = 8000
    NODE_ENV: str = "development"
    BACKEND_URL: str = "http://localhost:8000"

    MONGODB_URI: str = "mongodb://localhost:27017/uets_db"

    JWT_SECRET: str = "change_me_in_production"
    JWT_EXPIRES_IN: str = "8h"

    CORS_ORIGINS: str = "http://localhost:4200,http://localhost:4201"

    SEED_ADMIN_USERNAME: str = "admin"
    SEED_ADMIN_PASSWORD: str = "Admin1234!"
    SEED_ADMIN_EMAIL: str = "admin@uets.edu.ec"

    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_WINDOW_SECONDS: int = 900

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_development(self) -> bool:
        return self.NODE_ENV == "development"

    @property
    def jwt_expire_seconds(self) -> int:
        val = self.JWT_EXPIRES_IN
        if val.endswith("h"):
            return int(val[:-1]) * 3600
        if val.endswith("d"):
            return int(val[:-1]) * 86400
        if val.endswith("m"):
            return int(val[:-1]) * 60
        return int(val)


settings = Settings()

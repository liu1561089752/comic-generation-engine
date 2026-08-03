from pydantic_settings import BaseSettings
from pydantic import model_validator
import os
import secrets


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = ""
    APP_DEBUG: bool = True
    APP_LOG_LEVEL: str = "INFO"

    # 数据库 - PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/webtoon_factory"

    # 存储
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_PATH: str = "./data/storage"

    # LLM
    LLM_API_BASE: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.7

    # 生图模型 (GRS AI 中转站)
    IMAGE_API_BASE: str = ""
    IMAGE_API_KEY: str = ""
    IMAGE_MODEL: str = "nano-banana-2-lite"
    IMAGE_DEFAULT_WIDTH: int = 1920
    IMAGE_DEFAULT_HEIGHT: int = 1080
    IMAGE_DEFAULT_STEPS: int = 30
    IMAGE_DEFAULT_CFG_SCALE: float = 7.5
    IMAGE_MAX_CONCURRENT: int = 2

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # 管理员初始密码（生产环境必须在 .env 中设置）
    ADMIN_INITIAL_PASSWORD: str = ""

    # 导出
    EXPORT_TEMP_DIR: str = "./data/exports"
    EXPORT_MAX_FILE_SIZE_MB: int = 500
    EXPORT_TARGET_DIR: str = "./data/exports"

    # 分页限制：True 表示只处理前 100 页（P1-P100）
    PAGE_LIMIT_ENABLED: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @model_validator(mode="after")
    def _ensure_secret_key(self):
        # 必须在实例上读 APP_ENV：该值由 pydantic-settings 从 .env 解析，
        # 不一定存在于进程环境变量中
        if not self.APP_SECRET_KEY:
            if self.APP_ENV == "production":
                raise ValueError("APP_SECRET_KEY 必须在 .env 中设置（生产环境不允许为空）")
            self.APP_SECRET_KEY = secrets.token_urlsafe(32)
        return self

    def model_post_init(self, __context) -> None:
        """初始化后自动将相对路径解析为绝对路径"""
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if not os.path.isabs(self.STORAGE_LOCAL_PATH):
            self.STORAGE_LOCAL_PATH = os.path.normpath(
                os.path.join(backend_dir, self.STORAGE_LOCAL_PATH)
            )
        if not os.path.isabs(self.EXPORT_TEMP_DIR):
            self.EXPORT_TEMP_DIR = os.path.normpath(
                os.path.join(backend_dir, self.EXPORT_TEMP_DIR)
            )


settings = Settings()

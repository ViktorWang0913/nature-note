from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: str = 'production'
    database_url: str = 'postgresql+psycopg://nature:nature@db:5432/nature'
    secret_key: str = ''
    enable_dev_auth: bool = False
    storage_backend: str = 'cos'
    storage_dir: str = './data/files'
    public_base_url: str = 'http://127.0.0.1:8000'
    queue_backend: str = 'celery'
    redis_url: str = 'redis://redis:6379/0'
    wechat_app_id: str = ''
    wechat_app_secret: str = ''
    wechat_moderation_enabled: bool = False
    wechat_callback_token: str = ''
    wechat_callback_aes_key: str = ''
    cos_region: str = 'ap-shanghai'
    cos_bucket: str = ''
    cos_secret_id: str = ''
    cos_secret_key: str = ''
    admin_user_ids: str = ''
    max_upload_bytes: int = 20 * 1024 * 1024
    ai_mode: str = 'remote'
    image_api_base_url: str = ''
    image_api_model: str = ''
    image_api_key: str = ''
    multimodal_api_base_url: str = ''
    multimodal_api_model: str = ''
    multimodal_api_key: str = ''
    qwen_input_cny_per_million: float | None = Field(default=None, ge=0)
    qwen_output_cny_per_million: float | None = Field(default=None, ge=0)
    qwen_tier_threshold: int = Field(default=128000, ge=1)
    qwen_high_input_cny_per_million: float | None = Field(default=None, ge=0)
    qwen_high_output_cny_per_million: float | None = Field(default=None, ge=0)
    image_cny_per_call: float | None = Field(default=None, ge=0)
    qwen_context_max: int = 16000
    archive_retention_days: int = Field(default=30, ge=1, le=365)
    route_font_path: str = ''
    tencent_map_web_key: str = ''

    def validate_runtime(self):
        if len(self.secret_key) < 32:
            raise RuntimeError('SECRET_KEY must contain at least 32 characters')
        if self.ai_mode not in {'remote', 'mock'}:
            raise RuntimeError('Unknown AI adapter mode')
        if self.app_env != 'development':
            if self.enable_dev_auth or self.queue_backend != 'celery' or self.database_url.startswith('sqlite'):
                raise RuntimeError('Production requires PostgreSQL, Celery and disabled development login')
            if self.storage_backend == 'cos' and not all([self.cos_bucket, self.cos_secret_id, self.cos_secret_key]):
                raise RuntimeError('COS storage requires its credentials')
        if self.storage_backend not in {'cos', 'local'} or self.queue_backend not in {'celery', 'inline'}:
            raise RuntimeError('Unknown storage or queue backend')


@lru_cache
def settings():
    return Settings()

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

from .config import settings


def get_storage_uri() -> str:
    return settings.REDIS_URL or settings.RATE_LIMIT_STORAGE_URI


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=get_storage_uri(),
    headers_enabled=True,
)

__all__ = ["limiter", "_rate_limit_exceeded_handler"]

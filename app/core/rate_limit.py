import os

from slowapi import Limiter
from slowapi.util import get_remote_address


# En despliegues con varias réplicas, configurar RATE_LIMIT_STORAGE_URI con Redis.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("RATE_LIMIT_STORAGE_URI", "memory://"),
)

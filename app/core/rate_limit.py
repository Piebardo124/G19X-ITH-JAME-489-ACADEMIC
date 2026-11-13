import os

from slowapi import Limiter
from slowapi.util import get_remote_address


LOGIN_RATE_LIMIT = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
FEEDBACK_RATE_LIMIT = os.getenv("RATE_LIMIT_FEEDBACK", "5/minute")
CSV_UPLOAD_RATE_LIMIT = os.getenv("RATE_LIMIT_CSV_UPLOAD", "3/minute")

# Límites de solicitudes.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("RATE_LIMIT_STORAGE_URI", "memory://"),
)

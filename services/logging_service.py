import logging
from urllib.parse import urlsplit

class RedactAuthPaths(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            args = list(record.args)
            path = str(args[2])
            if path.startswith("/api/auth/callback"):
                args[2] = "/api/auth/callback?[redacted]"
            elif path.startswith("/api/auth/device-link/"):
                args[2] = "/api/auth/device-link/[redacted]"
            record.args = tuple(args)
        return True

def configure_access_log():
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, RedactAuthPaths) for f in logger.filters):
        logger.addFilter(RedactAuthPaths())

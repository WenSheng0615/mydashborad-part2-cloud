"""Restore deployment JSON without destroying valid local credentials."""
import json
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

def restore_json_environment(name, destination, oauth=False):
    content = os.getenv(name)
    if not content:
        return False
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("Expected object")
        if oauth:
            section = data.get("web") or data.get("installed")
            if not isinstance(section, dict) or not all(section.get(k) for k in ("client_id", "client_secret", "auth_uri", "token_uri")):
                raise ValueError("Invalid OAuth structure")
    except (ValueError, TypeError):
        logger.warning("%s is not valid credential JSON; existing file preserved", name)
        return False
    destination = Path(destination)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True

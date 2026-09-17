"""ASGI entry point; legacy exports remain for existing integrations and tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.compat import *  # noqa: F403 — retain legacy main.* patch points
from app.application import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

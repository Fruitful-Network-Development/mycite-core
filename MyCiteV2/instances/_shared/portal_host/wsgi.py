"""Gunicorn entrypoint for the env-validated V2 portal host."""

from .app import create_app

app = create_app()

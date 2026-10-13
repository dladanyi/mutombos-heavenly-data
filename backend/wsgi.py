"""WSGI entrypoint for Vercel (service entrypoint "wsgi:app")."""
from app import create_app

app = create_app()

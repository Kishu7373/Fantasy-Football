# conftest.py
import os
import pytest

# Ensure the environment variable for the API key is set
# This is necessary for the app to function correctly during tests.
os.environ.setdefault("X_RAPIDAPI_KEY", "test-key")

# Import create_app from the app module
from app import create_app

# Utilized ChatGPT to understand how to get the app instance for testing
@pytest.fixture(scope="session")
def app():
    app = create_app()
    app.config.update(TESTING=True)
    return app

@pytest.fixture()
def client(app):
    return app.test_client()

"""Test fixtures for FileBrowser MCP."""

import pytest
import os


@pytest.fixture(autouse=True)
def set_env():
    """Set test environment variables."""
    os.environ.setdefault("FB_URL", "https://localhost:8080")
    os.environ.setdefault("FB_USER", "test-user")
    os.environ.setdefault("FB_PASSWORD", "test-password")
    yield
    # Clean up
    os.environ.pop("FB_URL", None)
    os.environ.pop("FB_USER", None)
    os.environ.pop("FB_PASSWORD", None)

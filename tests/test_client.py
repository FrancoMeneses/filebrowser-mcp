"""Tests for FileBrowser API client."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.filebrowser.client import (
    FileBrowserClient,
    AuthenticationError,
    RateLimitError,
    NotFoundError,
    PermissionError,
    FileBrowserError,
)


class TestFileBrowserClient:
    """Test client initialization and auth."""

    def test_client_init(self):
        client = FileBrowserClient(
            url="https://localhost:8080",
            username="test",
            password="pass123"
        )
        assert client.url == "https://localhost:8080"
        assert client.username == "test"
        assert client._token is None

    def test_client_strips_trailing_slash(self):
        client = FileBrowserClient(
            url="https://localhost:8080/",
            username="test",
            password="pass123"
        )
        assert client.url == "https://localhost:8080"


class TestErrorHandling:
    """Test exception hierarchy."""

    def test_filebrowser_error(self):
        with pytest.raises(FileBrowserError):
            raise FileBrowserError("test error")

    def test_authentication_error(self):
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("auth failed")

    def test_rate_limit_error(self):
        with pytest.raises(RateLimitError):
            raise RateLimitError("rate limited")

    def test_not_found_error(self):
        with pytest.raises(NotFoundError):
            raise NotFoundError("not found")

    def test_permission_error(self):
        with pytest.raises(PermissionError):
            raise PermissionError("no permission")

    def test_error_inheritance(self):
        """All errors inherit from FileBrowserError."""
        assert issubclass(AuthenticationError, FileBrowserError)
        assert issubclass(RateLimitError, FileBrowserError)
        assert issubclass(NotFoundError, FileBrowserError)
        assert issubclass(PermissionError, FileBrowserError)

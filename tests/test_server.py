"""Tests for MCP server tool functions."""

import pytest
from unittest.mock import patch, MagicMock


class TestToolImports:
    """Verify all tools can be imported."""

    def test_import_server(self):
        from src.filebrowser.server import mcp
        assert mcp is not None

    def test_import_client(self):
        from src.filebrowser.client import FileBrowserClient
        assert FileBrowserClient is not None

    def test_import_models(self):
        from src.filebrowser.models import CreateuserRequest, UserPermissions
        assert CreateuserRequest is not None
        assert UserPermissions is not None

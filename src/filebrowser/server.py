"""
FileBrowser MCP Server

Provides tools for managing files and users on FileBrowser Quantum.
Authentication is handled automatically via environment variables.

Environment Variables:
    FB_URL: FileBrowser server URL (e.g., https://your-filebrowser-host)
    FB_USER: Username for authentication
    FB_PASSWORD: Password for authentication
"""

import os
import logging
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from filebrowser.client import (
    FileBrowserClient,
    FileBrowserError,
    AuthenticationError,
    RateLimitError,
    NotFoundError,
    PermissionError,
)

# ============================================================
# Configuration
# ============================================================

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "filebrowser-mcp.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

FB_URL = os.environ.get("FB_URL", "https://your-filebrowser-host")
FB_USER = os.environ.get("FB_USER", "")
FB_PASSWORD = os.environ.get("FB_PASSWORD", "")

if not FB_USER or not FB_PASSWORD:
    logger.warning("FB_USER and FB_PASSWORD not set")

# ============================================================
# MCP Server
# ============================================================

mcp = FastMCP(
    "FileBrowser",
    instructions="""FileBrowser Quantum file management tools.

    Provides access to a self-hosted FileBrowser instance for:
    - Listing, reading, uploading, and deleting files
    - Creating folders
    - Managing users (admin only)

    Permissions (8 individual flags):
    - admin: Access to admin panel and user management
    - api: Access to REST API
    - modify: Edit existing files
    - create: Create new files and folders
    - delete: Delete files and folders
    - download: Download files
    - share: Create public shares
    - realtime: WebSocket connections

    Scopes define WHAT a user can access (e.g., "/" or "/laserbox").
    """
)


def _get_client() -> FileBrowserClient:
    return FileBrowserClient(url=FB_URL, username=FB_USER, password=FB_PASSWORD)


def _handle_error(e: Exception) -> dict:
    if isinstance(e, AuthenticationError):
        return {"error": "Authentication failed", "details": str(e)}
    elif isinstance(e, RateLimitError):
        return {"error": "Rate limited", "details": str(e)}
    elif isinstance(e, NotFoundError):
        return {"error": "Not found", "details": str(e)}
    elif isinstance(e, PermissionError):
        return {"error": "Permission denied", "details": str(e)}
    elif isinstance(e, FileBrowserError):
        return {"error": "FileBrowser error", "details": str(e)}
    return {"error": "Unexpected error", "details": str(e)}


# ============================================================
# File Operations
# ============================================================

@mcp.tool()
def list_files(path: str = "/") -> list[dict]:
    """
    List files and folders in a directory.

    Args:
        path: Directory path (default: root "/")

    Returns:
        List of files/folders with metadata (name, size, type, modTime)
    """
    logger.info("Listing files: %s", path)
    client = _get_client()
    try:
        return client.list_files(path)
    except Exception as e:
        return _handle_error(e)
    finally:
        client.close()


@mcp.tool()
def get_file_info(path: str) -> dict:
    """
    Get metadata for a file or folder.

    Args:
        path: File or folder path

    Returns:
        File metadata (name, size, modTime, type, path, etc.)
    """
    logger.info("Getting file info: %s", path)
    client = _get_client()
    try:
        return client.get_file_info(path)
    except Exception as e:
        return _handle_error(e)
    finally:
        client.close()


@mcp.tool()
def read_file(path: str) -> str:
    """
    Read file contents.

    Args:
        path: File path to read

    Returns:
        File content as string
    """
    logger.info("Reading file: %s", path)
    client = _get_client()
    try:
        return client.read_file(path)
    except Exception as e:
        return str(_handle_error(e))
    finally:
        client.close()


@mcp.tool()
def upload_file(path: str, content: str, content_type: str = "text/plain") -> dict:
    """
    Create or update a file.

    Args:
        path: File path (e.g., "/documents/note.txt")
        content: File content
        content_type: MIME type (default: text/plain)

    Returns:
        Upload confirmation
    """
    logger.info("Uploading file: %s", path)
    client = _get_client()
    try:
        return client.upload_file(path, content, content_type)
    except Exception as e:
        return _handle_error(e)
    finally:
        client.close()


@mcp.tool()
def create_folder(path: str) -> dict:
    """
    Create a new directory.

    Args:
        path: Directory path (e.g., "/documents/new-folder")

    Returns:
        Creation confirmation
    """
    logger.info("Creating folder: %s", path)
    client = _get_client()
    try:
        return client.create_folder(path)
    except Exception as e:
        return _handle_error(e)
    finally:
        client.close()


@mcp.tool()
def delete_item(path: str) -> dict:
    """
    Delete a file or folder. WARNING: Irreversible.

    Args:
        path: Path to delete

    Returns:
        Deletion confirmation
    """
    logger.info("Deleting: %s", path)
    client = _get_client()
    try:
        return client.delete_item(path)
    except Exception as e:
        return _handle_error(e)
    finally:
        client.close()


@mcp.tool()
def download_file(path: str) -> str:
    """
    Download a file and return its content.

    Args:
        path: File path to download

    Returns:
        File content (text or base64 for binary)
    """
    logger.info("Downloading: %s", path)
    client = _get_client()
    try:
        content = client.download_file(path)
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            import base64
            return f"[Binary — base64]: {base64.b64encode(content).decode()}"
    except Exception as e:
        return str(_handle_error(e))
    finally:
        client.close()


# ============================================================
# User Management (Admin Only)
# ============================================================

@mcp.tool()
def list_users() -> list[dict]:
    """
    List all users with their permissions and scopes.

    Returns:
        List of users: {id, username, permissions{}, scopes[]}
    """
    logger.info("Listing users")
    client = _get_client()
    try:
        return client.list_users()
    except Exception as e:
        return _handle_error(e)
    finally:
        client.close()


@mcp.tool()
def create_user(
    username: str,
    password: str,
    scope: str = "/",
    admin: bool = False,
    api: bool = True,
    modify: bool = True,
    create: bool = True,
    delete: bool = True,
    download: bool = True,
    share: bool = False,
    realtime: bool = False,
) -> dict:
    """
    Create a new user with granular permissions.

    Requires admin privileges.

    Args:
        username: New username (min 1 char)
        password: User password (min 5 chars)
        scope: Filesystem scope — what folders user can access (default: "/" = all)
        admin: Access to admin panel and user management
        api: Access to REST API
        modify: Edit existing files
        create: Create new files and folders
        delete: Delete files and folders
        download: Download files
        share: Create public shares
        realtime: WebSocket connections

    Returns:
        Created user object
    """
    logger.info("Creating user: %s (scope: %s)", username, scope)
    client = _get_client()
    try:
        permissions = {
            "admin": admin,
            "api": api,
            "modify": modify,
            "create": create,
            "delete": delete,
            "download": download,
            "share": share,
            "realtime": realtime,
        }
        return client.create_user(username, password, scope, permissions)
    except Exception as e:
        return _handle_error(e)
    finally:
        client.close()


@mcp.tool()
def update_user(
    user_id: int,
    username: Optional[str] = None,
    scope: Optional[str] = None,
    admin: Optional[bool] = None,
    api: Optional[bool] = None,
    modify: Optional[bool] = None,
    create: Optional[bool] = None,
    delete: Optional[bool] = None,
    download: Optional[bool] = None,
    share: Optional[bool] = None,
    realtime: Optional[bool] = None,
) -> dict:
    """
    Update an existing user. Only provided fields are updated.

    Requires admin privileges.

    Args:
        user_id: User ID to update (get from list_users)
        username: New username (optional)
        scope: New filesystem scope (optional)
        admin, api, modify, create, delete, download, share, realtime:
            Permission flags to update (optional, only changed ones)

    Returns:
        Updated user confirmation
    """
    logger.info("Updating user %s", user_id)
    client = _get_client()
    try:
        permissions = {}
        for flag, value in [
            ("admin", admin), ("api", api), ("modify", modify),
            ("create", create), ("delete", delete), ("download", download),
            ("share", share), ("realtime", realtime),
        ]:
            if value is not None:
                permissions[flag] = value

        return client.update_user(
            user_id,
            username=username,
            scope=scope,
            permissions=permissions if permissions else None,
        )
    except Exception as e:
        return _handle_error(e)
    finally:
        client.close()


@mcp.tool()
def delete_user(user_id: int) -> dict:
    """
    Delete a user. WARNING: Irreversible.

    Requires admin privileges.

    Args:
        user_id: User ID to delete (get from list_users)

    Returns:
        Deletion confirmation
    """
    logger.info("Deleting user %s", user_id)
    client = _get_client()
    try:
        return client.delete_user(user_id)
    except Exception as e:
        return _handle_error(e)
    finally:
        client.close()


# ============================================================
# System
# ============================================================

@mcp.tool()
def health_check() -> dict:
    """
    Check FileBrowser server status.

    Returns:
        Health status with server URL
    """
    logger.info("Health check")
    client = _get_client()
    try:
        return client.health_check()
    except Exception as e:
        return _handle_error(e)
    finally:
        client.close()


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    logger.info("Starting FileBrowser MCP Server...")
    logger.info("Server: %s", FB_URL)
    logger.info("User: %s", FB_USER)
    mcp.run()

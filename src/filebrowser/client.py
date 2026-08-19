"""
FileBrowser Quantum API Client.

Handles authentication, token management, and all API operations.
Tested with FileBrowser Quantum v1.5.x.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


class FileBrowserError(Exception):
    """Base exception for FileBrowser API errors."""

    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(FileBrowserError):
    """Raised when authentication fails."""
    pass


class RateLimitError(FileBrowserError):
    """Raised when rate limit is hit (too many failed attempts)."""
    pass


class NotFoundError(FileBrowserError):
    """Raised when a resource is not found."""
    pass


class PermissionError(FileBrowserError):
    """Raised when user lacks required permissions."""
    pass


class FileBrowserClient:
    """
    Client for FileBrowser Quantum REST API.

    Handles authentication automatically. Token is obtained on first
    request and refreshed when expired.

    Usage:
        client = FileBrowserClient(
            url="https://localhost:8080",
            username="admin",
            password="***"
        )
        files = client.list_files("/documents")
    """

    def __init__(self, url: str, username: str, password: str):
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self._token: Optional[str] = None
        self._http = httpx.Client(timeout=30.0, verify=False)

    def _login(self) -> str:
        """
        Authenticate and obtain JWT token.

        FileBrowser Quantum uses X-Password header for login,
        NOT JSON body. This is a common pitfall.
        """
        login_url = f"{self.url}/api/auth/login?username={quote(self.username)}"

        try:
            response = self._http.post(
                login_url,
                headers={"X-Password": self.password}
            )

            if response.status_code == 429:
                raise RateLimitError(
                    "Rate limit hit: too many failed login attempts. "
                    "Account locked for 15 minutes."
                )

            if response.status_code == 401:
                raise AuthenticationError(
                    "Invalid username or password"
                )

            if response.status_code != 200:
                raise FileBrowserError(
                    f"Login failed: {response.status_code}",
                    status_code=response.status_code
                )

            # Response body IS the token (not wrapped in JSON)
            token = response.text.strip().strip('"')
            self._token = token
            logger.info("Authenticated as %s", self.username)
            return token

        except httpx.RequestError as e:
            raise FileBrowserError(f"Connection failed: {e}")

    def _get_token(self) -> str:
        """Get valid token, authenticating if needed."""
        if self._token is None:
            return self._login()
        return self._token

    def _request(
        self,
        method: str,
        path: str,
        params: dict = None,
        json_data: dict = None,
        content: bytes = None,
        content_type: str = None,
        require_admin: bool = False,
    ) -> httpx.Response:
        """
        Make an authenticated API request.

        Automatically handles token refresh on 401 responses.
        """
        token = self._get_token()

        headers = {"Authorization": f"Bearer {token}"}
        if content_type:
            headers["Content-Type"] = content_type

        url = f"{self.url}{path}"

        try:
            response = self._http.request(
                method,
                url,
                params=params,
                json=json_data,
                content=content,
                headers=headers,
            )

            # Token expired or invalid — try re-login once
            if response.status_code == 401:
                logger.info("Token expired, re-authenticating...")
                self._token = None
                token = self._login()
                headers["Authorization"] = f"Bearer {token}"
                response = self._http.request(
                    method,
                    url,
                    params=params,
                    json=json_data,
                    content=content,
                    headers=headers,
                )

            if response.status_code == 404:
                raise NotFoundError(f"Resource not found: {path}")

            if response.status_code == 403:
                raise PermissionError(
                    f"Permission denied. Admin access required for this operation."
                    if require_admin
                    else f"Permission denied: {path}"
                )

            if response.status_code == 429:
                raise RateLimitError(
                    "Rate limit hit. Account may be temporarily locked."
                )

            if response.status_code >= 400:
                raise FileBrowserError(
                    f"API error: {response.status_code} — {response.text[:200]}",
                    status_code=response.status_code,
                )

            return response

        except httpx.RequestError as e:
            raise FileBrowserError(f"Connection failed: {e}")

    # ============================================================
    # File Operations
    # ============================================================

    def list_files(self, path: str = "/") -> list[dict]:
        """
        List files and folders in a directory.

        Args:
            path: Directory path (default: root)

        Returns:
            List of file/folder metadata
        """
        response = self._request(
            "GET",
            "/api/resources",
            params={"path": path, "source": "Principal"}
        )
        data = response.json()

        # Response is a single item (the directory) with 'items' inside
        if isinstance(data, dict) and "items" in data:
            return data["items"]
        elif isinstance(data, list):
            return data
        return []

    def get_file_info(self, path: str) -> dict:
        """
        Get metadata for a file or folder.

        Args:
            path: File or folder path

        Returns:
            File metadata (name, size, modTime, type, etc.)
        """
        response = self._request(
            "GET",
            "/api/resources",
            params={"path": path, "source": "Principal"}
        )
        return response.json()

    def read_file(self, path: str) -> str:
        """
        Read file contents.

        Args:
            path: File path

        Returns:
            File content as string
        """
        response = self._request(
            "GET",
            "/api/resources",
            params={"path": path, "source": "Principal"}
        )

        data = response.json()
        # If it's a directory, raise error
        if isinstance(data, dict) and data.get("isDir"):
            raise FileBrowserError(f"Cannot read directory: {path}")

        return data.get("content", response.text)

    def upload_file(
        self,
        path: str,
        content: str,
        content_type: str = "text/plain"
    ) -> dict:
        """
        Create or update a file.

        Uses POST for new files, PUT for updates.
        FileBrowser Quantum accepts both for creation.

        Args:
            path: File path (e.g., "/documents/note.txt")
            content: File content
            content_type: MIME type (default: text/plain)

        Returns:
            Upload response with file info
        """
        response = self._request(
            "POST",
            "/api/resources",
            params={"path": path, "source": "Principal"},
            content=content.encode("utf-8"),
            content_type=content_type,
        )

        try:
            return response.json()
        except Exception:
            return {"message": "File uploaded successfully"}

    def create_folder(self, path: str) -> dict:
        """
        Create a new directory.

        IMPORTANT: isDir must be in query string, NOT in JSON body.
        Putting {"isDir": true} in body creates a file with that content.

        Args:
            path: Directory path (e.g., "/documents/new-folder")

        Returns:
            Creation response
        """
        response = self._request(
            "POST",
            "/api/resources",
            params={"path": path, "source": "Principal", "isDir": "true"},
        )

        try:
            return response.json()
        except Exception:
            return {"message": f"Folder '{path}' created successfully"}

    def delete_item(self, path: str) -> dict:
        """
        Delete a file or folder.

        Args:
            path: Path to delete

        Returns:
            Deletion confirmation
        """
        self._request(
            "DELETE",
            "/api/resources",
            params={"path": path, "source": "Principal"}
        )
        return {"message": f"Deleted: {path}"}

    def download_file(self, path: str) -> bytes:
        """
        Download a file.

        Args:
            path: File path to download

        Returns:
            File content as bytes
        """
        response = self._request(
            "GET",
            "/api/resources/download",
            params={"path": path, "source": "Principal"}
        )
        return response.content

    # ============================================================
    # User Management (Admin Only)
    # ============================================================

    def list_users(self) -> list[dict]:
        """
        List all users.

        Requires admin privileges.

        Returns:
            List of user objects
        """
        response = self._request(
            "GET",
            "/api/users",
            require_admin=True
        )
        return response.json()

    def get_current_user(self) -> dict:
        """
        Get current user information.

        Returns:
            Current user object
        """
        response = self._request("GET", "/api/users/me")
        return response.json()

    def create_user(
        self,
        username: str,
        password: str,
        scope: str = "/",
        admin: bool = False,
        permissions: dict = None,
    ) -> dict:
        """
        Create a new user.

        Requires admin privileges.

        Args:
            username: New username
            password: User password
            scope: Filesystem scope (default: root "/")
            admin: Grant admin access (default: False)
            permissions: Custom permissions dict (optional)

        Returns:
            Created user object
        """
        if permissions is None:
            permissions = {
                "admin": admin,
                "api": True,
                "share": False,
                "realtime": False,
                "modify": True,
                "create": True,
                "delete": True,
                "download": True,
            }
        else:
            permissions["admin"] = admin
            permissions["api"] = True

        user_data = {
            "which": [],
            "data": {
                "username": username,
                "password": password,
                "loginMethod": "password",
                "lockPassword": True,
                "permissions": permissions,
                "scopes": [{"name": "Principal", "scope": scope}],
            }
        }

        # FileBrowser needs admin password in X-Password header for user creation
        response = self._request(
            "POST",
            "/api/users",
            json_data=user_data,
            require_admin=True,
        )

        # Add X-Password header for user creation
        # Re-do with admin password
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Password": self.password,
        }

        response = self._http.post(
            f"{self.url}/api/users",
            json=user_data,
            headers=headers,
        )

        if response.status_code in (200, 201):
            try:
                return response.json()
            except Exception:
                return {"message": f"User '{username}' created successfully"}
        else:
            raise FileBrowserError(
                f"Failed to create user: {response.status_code} — {response.text[:200]}"
            )

    def update_user(
        self,
        user_id: int,
        username: str = None,
        scope: str = None,
        admin: bool = None,
        permissions: dict = None,
    ) -> dict:
        """
        Update an existing user.

        Requires admin privileges.

        Args:
            user_id: User ID to update
            username: New username (optional)
            scope: New scope (optional)
            admin: New admin status (optional)
            permissions: New permissions dict (optional)

        Returns:
            Updated user object
        """
        update_data = {"which": ["all"], "data": {}}

        if username is not None:
            update_data["data"]["username"] = username
        if scope is not None:
            update_data["data"]["scopes"] = [{"name": "Principal", "scope": scope}]
        if admin is not None:
            if permissions is None:
                permissions = {}
            permissions["admin"] = admin
            permissions["api"] = True
        if permissions is not None:
            update_data["data"]["permissions"] = permissions

        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Password": self.password,
        }

        response = self._http.put(
            f"{self.url}/api/users?id={user_id}",
            json=update_data,
            headers=headers,
        )

        if response.status_code == 200:
            try:
                return response.json()
            except Exception:
                return {"message": f"User {user_id} updated successfully"}
        else:
            raise FileBrowserError(
                f"Failed to update user: {response.status_code} — {response.text[:200]}"
            )

    def delete_user(self, user_id: int) -> dict:
        """
        Delete a user.

        Requires admin privileges.

        Args:
            user_id: User ID to delete

        Returns:
            Deletion confirmation
        """
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Password": self.password,
        }

        response = self._http.delete(
            f"{self.url}/api/users?id={user_id}",
            headers=headers,
        )

        if response.status_code in (200, 204):
            return {"message": f"User {user_id} deleted successfully"}
        else:
            raise FileBrowserError(
                f"Failed to delete user: {response.status_code}"
            )

    # ============================================================
    # System
    # ============================================================

    def health_check(self) -> dict:
        """
        Check FileBrowser server status.

        Returns:
            Health status
        """
        try:
            response = self._http.get(f"{self.url}/health")
            if response.status_code == 200:
                return {"status": "healthy", "url": self.url}
            else:
                return {"status": "unhealthy", "code": response.status_code}
        except httpx.RequestError as e:
            return {"status": "unreachable", "error": str(e)}

    def close(self):
        """Close the HTTP client."""
        self._http.close()

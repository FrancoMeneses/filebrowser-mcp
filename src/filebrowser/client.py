"""
FileBrowser Quantum API Client.

Handles authentication, token management, and all API operations.
Tested with FileBrowser Quantum v1.5.x.

API Structure (verified):
- Login: POST /api/auth/login?username=X, Header: X-Password
- Users: GET/POST/PUT/DELETE /api/users
- Files: GET/POST/PUT/DELETE /api/resources
- User fields: id, username, permissions{}, scopes[{name, scope}]
- Permissions: admin, api, modify, create, delete, download, share, realtime
- Scopes: [{name: "Principal", scope: "/path"}]
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
            url="https://your-host",
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
                raise AuthenticationError("Invalid username or password")

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
        admin_password: bool = False,
    ) -> httpx.Response:
        """
        Make an authenticated API request.

        Args:
            admin_password: If True, include X-Password header (for user management)
        """
        token = self._get_token()

        headers = {"Authorization": f"Bearer {token}"}
        if content_type:
            headers["Content-Type"] = content_type
        if admin_password:
            headers["X-Password"] = self.password

        url = f"{self.url}{path}"

        try:
            response = self._http.request(
                method, url, params=params, json=json_data,
                content=content, headers=headers,
            )

            # Token expired — try re-login once
            if response.status_code == 401:
                logger.info("Token expired, re-authenticating...")
                self._token = None
                token = self._login()
                headers["Authorization"] = f"Bearer {token}"
                response = self._http.request(
                    method, url, params=params, json=json_data,
                    content=content, headers=headers,
                )

            if response.status_code == 404:
                raise NotFoundError(f"Resource not found: {path}")
            if response.status_code == 403:
                raise PermissionError(f"Permission denied: {path}")
            if response.status_code == 429:
                raise RateLimitError("Rate limit hit. Account temporarily locked.")
            if response.status_code >= 400:
                try:
                    err = response.json()
                    msg = err.get("message", response.text[:200])
                except Exception:
                    msg = response.text[:200]
                raise FileBrowserError(
                    f"API error {response.status_code}: {msg}",
                    status_code=response.status_code,
                )

            return response

        except httpx.RequestError as e:
            raise FileBrowserError(f"Connection failed: {e}")

    # ============================================================
    # File Operations
    # ============================================================

    def list_files(self, path: str = "/") -> list[dict]:
        """List files and folders in a directory."""
        response = self._request(
            "GET", "/api/resources",
            params={"path": path, "source": "Principal"}
        )
        data = response.json()
        if isinstance(data, dict) and "items" in data:
            return data["items"]
        elif isinstance(data, list):
            return data
        return []

    def get_file_info(self, path: str) -> dict:
        """Get metadata for a file or folder."""
        response = self._request(
            "GET", "/api/resources",
            params={"path": path, "source": "Principal"}
        )
        return response.json()

    def read_file(self, path: str) -> str:
        """Read file contents."""
        info = self.get_file_info(path)
        if isinstance(info, dict) and info.get("isDir"):
            raise FileBrowserError(f"Cannot read directory: {path}")
        return info.get("content", "")

    def upload_file(self, path: str, content: str, content_type: str = "text/plain") -> dict:
        """Create or update a file."""
        response = self._request(
            "POST", "/api/resources",
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

        IMPORTANT: isDir goes in query string, NOT in JSON body.
        """
        self._request(
            "POST", "/api/resources",
            params={"path": path, "source": "Principal", "isDir": "true"},
        )
        return {"message": f"Folder '{path}' created"}

    def delete_item(self, path: str) -> dict:
        """Delete a file or folder."""
        self._request(
            "DELETE", "/api/resources",
            params={"path": path, "source": "Principal"}
        )
        return {"message": f"Deleted: {path}"}

    def download_file(self, path: str) -> bytes:
        """Download a file as bytes."""
        response = self._request(
            "GET", "/api/resources/download",
            params={"path": path, "source": "Principal"}
        )
        return response.content

    # ============================================================
    # User Management (Admin Only)
    # ============================================================

    def list_users(self) -> list[dict]:
        """
        List all users.

        Returns list of users with: id, username, permissions{}, scopes[]
        """
        response = self._request("GET", "/api/users", admin_password=False)
        return response.json()


    def create_user(
        self,
        username: str,
        password: str,
        scope: str = "/",
        permissions: dict = None,
    ) -> dict:
        """
        Create a new user.

        Args:
            username: New username
            password: User password (min 5 chars)
            scope: Filesystem scope (default: root "/")
            permissions: Dict with permission flags. Default:
                {admin: false, api: true, modify: true, create: true,
                 delete: true, download: true, share: false, realtime: false}
        """
        if permissions is None:
            permissions = {
                "admin": False,
                "api": True,
                "modify": True,
                "create": True,
                "delete": True,
                "download": True,
                "share": False,
                "realtime": False,
            }

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

        response = self._request(
            "POST", "/api/users",
            json_data=user_data,
            admin_password=True,
        )

        try:
            return response.json()
        except Exception:
            return {"message": f"User '{username}' created successfully"}

    def update_user(
        self,
        user_id: int,
        username: str = None,
        scope: str = None,
        permissions: dict = None,
    ) -> dict:
        """
        Update an existing user.

        Only provided fields are updated.
        """
        update_data = {"which": ["all"], "data": {}}

        if username is not None:
            update_data["data"]["username"] = username
        if scope is not None:
            update_data["data"]["scopes"] = [{"name": "Principal", "scope": scope}]
        if permissions is not None:
            update_data["data"]["permissions"] = permissions

        response = self._request(
            "PUT", f"/api/users?id={user_id}",
            json_data=update_data,
            admin_password=True,
        )

        try:
            return response.json()
        except Exception:
            return {"message": f"User {user_id} updated"}

    def delete_user(self, user_id: int) -> dict:
        """Delete a user by ID."""
        self._request(
            "DELETE", f"/api/users?id={user_id}",
            admin_password=True,
        )
        return {"message": f"User {user_id} deleted"}

    # ============================================================
    # System
    # ============================================================

    def health_check(self) -> dict:
        """Check FileBrowser server status."""
        try:
            response = self._http.get(f"{self.url}/health")
            if response.status_code == 200:
                return {"status": "healthy", "url": self.url}
            return {"status": "unhealthy", "code": response.status_code}
        except httpx.RequestError as e:
            return {"status": "unreachable", "error": str(e)}

    def close(self):
        """Close the HTTP client."""
        self._http.close()

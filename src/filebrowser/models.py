"""
Pydantic models for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional


class UserPermissions(BaseModel):
    """FileBrowser user permissions."""
    admin: bool = False
    api: bool = True
    share: bool = False
    realtime: bool = False
    modify: bool = True
    create: bool = True
    delete: bool = True
    download: bool = True


class UserScope(BaseModel):
    """User filesystem scope."""
    name: str = "Principal"
    scope: str = "/"


class CreateuserRequest(BaseModel):
    """Request to create a new user."""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=5)
    scope: str = Field(default="/", description="Filesystem scope")
    admin: bool = Field(default=False, description="Grant admin access")
    permissions: Optional[UserPermissions] = None


class UpdateUserRequest(BaseModel):
    """Request to update an existing user."""
    user_id: int
    username: Optional[str] = None
    scope: Optional[str] = None
    admin: Optional[bool] = None
    permissions: Optional[UserPermissions] = None


class UploadFileRequest(BaseModel):
    """Request to upload/create a file."""
    path: str = Field(..., description="File path (e.g., /docs/note.txt)")
    content: str = Field(..., description="File content")
    content_type: str = Field(default="text/plain", description="MIME type")


class CreateFolderRequest(BaseModel):
    """Request to create a folder."""
    path: str = Field(..., description="Folder path (e.g., /docs/new-folder)")


class DeleteItemRequest(BaseModel):
    """Request to delete a file or folder."""
    path: str = Field(..., description="Path to delete")


class ListFilesRequest(BaseModel):
    """Request to list files."""
    path: str = Field(default="/", description="Directory path")


class ReadFileRequest(BaseModel):
    """Request to read a file."""
    path: str = Field(..., description="File path to read")


class DownloadFileRequest(BaseModel):
    """Request to download a file."""
    path: str = Field(..., description="File path to download")
    local_path: Optional[str] = Field(None, description="Local save path")

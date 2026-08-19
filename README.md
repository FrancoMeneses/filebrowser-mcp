# FileBrowser MCP

Model Context Protocol server for [FileBrowser Quantum](https://github.com/gtsteffaniak/filebrowser) — a self-hosted file management web interface with REST API.

## Features

- **File Operations**: List, read, upload, download, delete files and folders
- **User Management**: Create, update, delete users with granular permissions (admin only)
- **Authentication**: Automatic token management with session persistence
- **Multi-User**: Configurable credentials via environment variables
- **Error Handling**: Clear error messages with rate-limit awareness

## Installation

```bash
# Clone the repository
git clone https://github.com/FrancoMeneses/filebrowser-mcp.git
cd filebrowser-mcp

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Set environment variables for authentication:

```bash
export FB_URL="https://your-filebrowser-host:8080"
export FB_USER="your-username"
export FB_PASSWORD="your-password"
```

### With Hermes Agent

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  filebrowser:
    command: "python3"
    ```yaml
    env:
      FB_URL: "https://your-filebrowser-host"
      FB_USER: "your-username"
      FB_PASSWORD: "your-password"
    ```
```

### Multi-User Setup

For different users (e.g., admin vs restricted), use separate MCP instances:

```yaml
mcp_servers:
  filebrowser-admin:
    command: "python3"
    args: ["/path/to/server.py"]
    env:
      FB_URL: "https://your-filebrowser-host"
      FB_USER: "admin"
      FB_PASSWORD: "***"
    timeout: 30
  filebrowser-user:
    command: "python3"
    args: ["/path/to/server.py"]
    env:
      FB_URL: "https://your-filebrowser-host"
      FB_USER: "restricted-user"
      FB_PASSWORD: "***"
    timeout: 30
```

## Available Tools

### File Operations

| Tool | Description | Permissions Needed |
|------|-------------|-------------------|
| `list_files` | List files and folders in a directory | `api` |
| `get_file_info` | Get file/folder metadata | `api` |
| `read_file` | Read file contents | `api` |
| `upload_file` | Create or update a file | `modify` or `create` |
| `create_folder` | Create a new directory | `create` |
| `delete_item` | Delete a file or folder | `delete` |
| `download_file` | Download a file | `download` |

Permissions are checked against the user's scope — users can only operate on files within their allowed folders.

### User Management (Requires `admin` permission)

Users are managed with **8 granular permission flags**:

| Permission | Description |
|------------|-------------|
| `admin` | Access to admin panel and user management |
| `api` | Access to REST API |
| `modify` | Edit existing files |
| `create` | Create new files and folders |
| `delete` | Delete files and folders |
| `download` | Download files |
| `share` | Create public shares |
| `realtime` | WebSocket connections |

Each user also has a **scope** that defines which folders they can access (e.g., `/` for all, `/laserbox` for restricted).

Example: A user with `admin=false, modify=true, create=true, delete=false` can upload and edit files but cannot delete them or manage other users.

### System

| Tool | Description |
|------|-------------|
| `health_check` | Check FileBrowser server status |

## Permissions Reference

FileBrowser uses these permission flags:

| Permission | Description |
|------------|-------------|
| `admin` | Access to admin panel and user management |
| `api` | Access to REST API |
| `modify` | Edit existing files |
| `create` | Create new files and folders |
| `delete` | Delete files and folders |
| `download` | Download files |
| `share` | Create public shares |

## Rate Limiting

FileBrowser Quantum locks accounts after **8 failed login attempts** (15-minute cooldown). The MCP handles this gracefully with clear error messages.

## API Compatibility

Tested with FileBrowser Quantum v1.5.x. May work with other versions but not guaranteed.

## License

MIT

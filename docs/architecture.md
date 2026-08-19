# Architecture

## Overview

FileBrowser MCP is a Model Context Protocol server that wraps the FileBrowser Quantum REST API. It provides structured tools for file and user management, handling authentication automatically.

## Design Principles

1. **Security First**: Credentials never exposed in tool calls — stored in environment variables
2. **Automatic Auth**: Token management handled transparently by the client
3. **Error Handling**: Clear, actionable error messages for common issues
4. **Permission Awareness**: Admin-only tools clearly marked and enforced

## Layers

```
┌─────────────────────────────────────────┐
│           MCP Client (Hermes)           │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│          server.py (FastMCP)            │
│  - Tool definitions                     │
│  - Error handling                       │
│  - Logging                              │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│           client.py (API Client)        │
│  - Authentication (X-Password header)   │
│  - Token management                     │
│  - Request/response handling            │
│  - Rate limit awareness                 │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│     FileBrowser Quantum REST API        │
│  - /api/auth/login                      │
│  - /api/resources/*                     │
│  - /api/users/*                         │
└─────────────────────────────────────────┘
```

## Authentication Flow

```
1. Client created with username/password
2. First API call triggers _login()
3. POST /api/auth/login?username=X
   Header: X-Password: ***
4. Response body IS the JWT token
5. Token cached in client._token
6. Subsequent calls use Authorization: Bearer ***
7. On 401 → automatic re-login once
```

## Key Implementation Details

### Login Header (Common Pitfall)
```bash
# CORRECT — password in header
POST /api/auth/login?username=admin
Header: X-Password: admin123

# WRONG — password in JSON body (always returns 401)
POST /api/auth/login
Body: {"username":"admin", "password":"admin123"}
```

### Folder Creation (Common Pitfall)
```bash
# CORRECT — isDir in query string
POST /api/resources?path=/folder&source=Principal&isDir=true

# WRONG — isDir in JSON body (creates a file with that content)
POST /api/resources?path=/folder
Body: {"isDir": true}
```

### User Creation (Common Pitfall)
```bash
# Needs BOTH Authorization AND X-Password headers
POST /api/users
Header: Authorization: Bearer <token>
Header: X-Password: <admin-password>
Body: {"which": [], "data": {...}}
```

## Error Handling

All tools return consistent response format:

```python
# Success
{"field1": "value1", ...}

# Error
{"error": "Error type", "details": "Human-readable message"}
```

## Rate Limiting

FileBrowser Quantum locks accounts after 8 failed login attempts (15-minute cooldown). The client:
- Detects HTTP 429 responses
- Returns clear error message about lockout
- Does NOT retry automatically (would extend lockout)

# sipap-mcp Examples

This directory contains practical examples demonstrating how to build and deploy MCP servers using the sipap-mcp framework.

## Examples Overview

| Example | Description | Concepts |
|---------|-------------|----------|
| **01_basic_server.py** | Simple calculator MCP server | Basic server setup, @mcp_tool decorator, context manager |
| **02_lambda_with_auth.py** | Weather service for AWS Lambda | Lambda deployment, API key authentication, environment config |
| **03_http_with_sessions.py** | Chat server with sessions | HTTP/FastAPI deployment, Redis sessions, stateful interactions |
| **04_advanced_server.py** | Sports data with lifecycle hooks | Multiple tools, _setup/_cleanup hooks, caching, error handling |
| **05_authentication.py** | Authentication strategies comparison | NoAuth, APIKeyAuth, SigV4Auth, environment-based selection |

## Running the Examples

### Prerequisites

```bash
# Install sipap-mcp
pip install sipap-mcp

# For session management examples (03)
docker run -d -p 6379:6379 redis:7-alpine
```

### 01 - Basic Server

Demonstrates the fundamentals of creating an MCP server.

```bash
python examples/01_basic_server.py
```

**What you'll learn:**
- How to create an MCP server class
- Using the @mcp_tool decorator
- Defining JSON Schema for inputs
- Handling requests with the context manager

### 02 - Lambda with Authentication

Production-ready Lambda deployment with API key authentication.

```bash
python examples/02_lambda_with_auth.py
```

**What you'll learn:**
- Creating Lambda handlers
- Implementing API key authentication
- Environment-based configuration
- Testing Lambda functions locally

**Deployment:**
```bash
# Set environment variable
export API_KEYS='prod-key-1,prod-key-2,prod-key-3'

# Deploy to AWS Lambda
# - Handler: 02_lambda_with_auth.handler
# - Runtime: python3.12
# - Timeout: 30 seconds
```

### 03 - HTTP with Sessions

FastAPI server with Redis-backed session management.

```bash
# Ensure Redis is running
docker run -d -p 6379:6379 redis:7-alpine

# Run server
python examples/03_http_with_sessions.py
```

Server starts on http://localhost:8000

**Test workflow:**
```bash
# 1. Start session
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tools/call",
    "params": {
      "name": "start_session",
      "arguments": {"user_id": "user123"}
    }
  }'

# Response includes session_id, use it in subsequent requests

# 2. Send message
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "2",
    "method": "tools/call",
    "params": {
      "name": "send_message",
      "arguments": {
        "session_id": "<session_id_from_step_1>",
        "message": "Hello!"
      }
    }
  }'

# 3. Get history
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "3",
    "method": "tools/call",
    "params": {
      "name": "get_history",
      "arguments": {"session_id": "<session_id_from_step_1>"}
    }
  }'
```

**What you'll learn:**
- Creating FastAPI applications
- Using Redis for session management
- Maintaining state across requests
- Session creation, updates, and retrieval

### 04 - Advanced Server

Full-featured server with lifecycle management.

```bash
python examples/04_advanced_server.py
```

**What you'll learn:**
- Implementing custom _setup() and _cleanup() hooks
- Managing database connections
- Implementing in-memory caching
- Defining multiple tools with complex schemas
- Pattern matching with JSON Schema (regex, enums, ranges)

### 05 - Authentication

Comprehensive guide to authentication strategies.

```bash
python examples/05_authentication.py
```

**What you'll learn:**
- NoAuth for development
- APIKeyAuth for production APIs
- SigV4Auth for AWS IAM integration
- Environment-based auth selection
- Security best practices

## Common Patterns

### Creating a Server

```python
from sipap_mcp import MCPServer, mcp_tool

class MyServer(MCPServer):
    def __init__(self):
        super().__init__(name="my-server", version="1.0.0")

    @mcp_tool(
        description="Tool description",
        input_schema={
            "type": "object",
            "properties": {
                "param": {"type": "string"}
            },
            "required": ["param"]
        }
    )
    def my_tool(self, param: str) -> dict:
        return {"result": param}
```

### Lambda Deployment

```python
from sipap_mcp.transport import create_lambda_handler
from sipap_mcp.auth import APIKeyAuth

server = MyServer()
auth = APIKeyAuth(api_keys=["key1", "key2"])
handler = create_lambda_handler(server, auth=auth)
```

### HTTP Deployment

```python
from sipap_mcp.transport import create_http_app
import uvicorn

server = MyServer()
app = create_http_app(server, auth=auth)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Session Management

```python
import redis
from sipap_mcp.session import SessionManager

redis_client = redis.Redis(host="localhost", port=6379)
session_manager = SessionManager(redis_client, ttl=3600)

# Create session
session_id = session_manager.create_session(
    data={"user_id": "123"},
    ttl=1800  # 30 minutes
)

# Get session
data = session_manager.get_session(session_id)

# Update session
session_manager.update_session(session_id, {"user_id": "123", "count": 1})
```

## JSON-RPC 2.0 Request Format

All MCP servers use JSON-RPC 2.0:

### List Tools

```json
{
  "jsonrpc": "2.0",
  "id": "req-1",
  "method": "tools/list",
  "params": {}
}
```

### Call Tool

```json
{
  "jsonrpc": "2.0",
  "id": "req-2",
  "method": "tools/call",
  "params": {
    "name": "tool_name",
    "arguments": {
      "param1": "value1",
      "param2": "value2"
    }
  }
}
```

## Testing Examples

All examples can be tested using pytest:

```bash
# Run all examples as tests
pytest examples/

# Run specific example
pytest examples/01_basic_server.py -v
```

## Next Steps

1. Start with `01_basic_server.py` to understand fundamentals
2. Move to `02_lambda_with_auth.py` for production deployment
3. Explore `03_http_with_sessions.py` for stateful servers
4. Study `04_advanced_server.py` for advanced patterns
5. Review `05_authentication.py` for security best practices

## Additional Resources

- **Main README**: `../README.md` - Full framework documentation
- **Tests**: `../tests/` - Comprehensive test examples
- **Source Code**: `../src/sipap_mcp/` - Implementation reference

## Support

For issues or questions:
- Check the main README
- Review test files for usage patterns
- Consult the source code for implementation details

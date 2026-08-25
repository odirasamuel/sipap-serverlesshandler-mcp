# sipap-mcp

**Production-ready MCP server framework for AWS Lambda and ECS Fargate**

[![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)](https://www.python.org/downloads/)
[![Type Checked](https://img.shields.io/badge/type%20checked-mypy-blue)](http://mypy-lang.org/)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000)](https://github.com/astral-sh/ruff)
[![Test Coverage](https://img.shields.io/badge/coverage-96%25-brightgreen)](https://github.com/pytest-dev/pytest-cov)
[![Tests](https://img.shields.io/badge/tests-112%20passing-brightgreen)](https://github.com/pytest-dev/pytest)

---

## Overview

`sipap-mcp` provides base classes and infrastructure for building [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) servers that implement JSON-RPC 2.0 and can run on:

- **AWS Lambda**: Serverless functions for lightweight, sporadic workloads
- **ECS Fargate**: Containerized services for long-running, stateful workloads

This framework powers all 5 data servers in the Valo (Sports Intelligence Platform) architecture, handling sports data, odds intelligence, news context, weather data, and historical statistics.

## Features

### Core Functionality
- ✅ **MCPServer Base Class**: Abstract base with tool registration and auto-discovery
- ✅ **@mcp_tool Decorator**: Mark functions as MCP tools with JSON Schema validation
- ✅ **JSON-RPC 2.0 Protocol**: Complete implementation with proper error handling
- ✅ **Dual Transport**: Lambda handler and FastAPI HTTP server

### Security & State
- ✅ **Authentication**: Pluggable strategies (NoAuth, API key, AWS SigV4)
- ✅ **Session Management**: Redis-backed state preservation between calls
- ✅ **Input Validation**: JSON Schema validation on all tool inputs

### Quality
- ✅ **Type Safety**: Full mypy strict mode compliance (zero errors)
- ✅ **Test Coverage**: 96% coverage with 112 passing tests
- ✅ **Production Ready**: Zero linting errors, comprehensive error handling

## Installation

```bash
pip install sipap-mcp
```

For development:

```bash
pip install sipap-mcp[dev]
```

## Quick Start

### 1. Define an MCP Server

```python
from sipap_mcp import MCPServer, mcp_tool

class WeatherMCP(MCPServer):
    """Weather data MCP server."""

    def __init__(self):
        super().__init__(name="weather-mcp", version="1.0.0")

    @mcp_tool(
        description="Get current weather for a location",
        input_schema={
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
                "units": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "default": "celsius"
                }
            },
            "required": ["location"]
        }
    )
    def get_weather(self, location: str, units: str = "celsius") -> dict:
        """Get current weather conditions."""
        # Your implementation here
        return {
            "location": location,
            "temperature": 22 if units == "celsius" else 72,
            "units": units,
            "condition": "partly cloudy"
        }
```

### 2. Deploy to AWS Lambda

```python
from sipap_mcp.transport import create_lambda_handler
from sipap_mcp.auth import APIKeyAuth

# Create server instance
server = WeatherMCP()

# Configure authentication
auth = APIKeyAuth(api_keys=["your-api-key"])

# Create Lambda handler (entry point for AWS)
handler = create_lambda_handler(server, auth=auth)
```

**Deploy with AWS CDK or Terraform:**
- Handler: `your_module.handler`
- Runtime: `python3.12`
- Timeout: 30 seconds

### 3. Deploy to ECS Fargate (HTTP)

```python
from sipap_mcp.transport import create_http_app
import uvicorn

# Create server instance
server = WeatherMCP()

# Create FastAPI app
app = create_http_app(server, auth=auth)

# Run with uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Deploy with Docker:**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install sipap-mcp
CMD ["uvicorn", "your_module:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Core Concepts

### Tools

Tools are functions decorated with `@mcp_tool` that become callable via the MCP protocol:

```python
@mcp_tool(
    description="Description of what this tool does",
    input_schema={
        "type": "object",
        "properties": {
            "param": {"type": "string"}
        },
        "required": ["param"]
    }
)
def my_tool(self, param: str) -> dict:
    """Docstring for the tool."""
    return {"result": param}
```

**JSON Schema types supported:**
- `string`, `number`, `integer`, `boolean`, `array`, `object`
- Validation: `minLength`, `maxLength`, `minimum`, `maximum`, `pattern`, `enum`

### Authentication

Choose the authentication strategy that fits your deployment:

#### NoAuth (Development Only)
```python
from sipap_mcp.auth import NoAuth

auth = NoAuth()  # No authentication - use for local dev only
```

#### API Key Authentication
```python
from sipap_mcp.auth import APIKeyAuth

auth = APIKeyAuth(api_keys=[
    "client-a-key",
    "client-b-key",
    "client-c-key"
])
```

Clients send API key in `X-API-Key` header.

#### AWS SigV4 Authentication
```python
from sipap_mcp.auth import SigV4Auth

auth = SigV4Auth(service="lambda", region="us-east-1")
```

For Lambda Function URLs with IAM authentication.

### Session Management

Maintain state across multiple requests using Redis:

```python
import redis
from sipap_mcp.session import SessionManager

# Connect to Redis
redis_client = redis.Redis(host="localhost", port=6379)

# Create session manager
session_manager = SessionManager(
    redis_client=redis_client,
    ttl=3600  # 1 hour default
)

# Create session
session_id = session_manager.create_session(
    data={"user_id": "123", "preferences": {...}},
    ttl=1800  # 30 minutes custom TTL
)

# Retrieve session
session_data = session_manager.get_session(session_id)

# Update session
session_manager.update_session(session_id, updated_data)

# Extend TTL
session_manager.extend_ttl(session_id, ttl=7200)
```

### Lifecycle Hooks

Override `_setup()` and `_cleanup()` for resource management:

```python
class MyServer(MCPServer):
    def __init__(self):
        super().__init__(name="my-server", version="1.0.0")
        self.db_connection = None

    def _setup(self) -> None:
        """Called when entering context manager."""
        self.db_connection = connect_to_database()

    def _cleanup(self) -> None:
        """Called when exiting context manager."""
        if self.db_connection:
            self.db_connection.close()
```

Use with context manager:

```python
with server:
    # Server is set up, resources initialized
    response = server.handle_request(request)
    # Cleanup happens automatically on exit
```

## JSON-RPC 2.0 Protocol

### Request Format

#### List Available Tools
```json
{
  "jsonrpc": "2.0",
  "id": "req-1",
  "method": "tools/list",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "req-1",
  "result": {
    "tools": [
      {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "inputSchema": {
          "type": "object",
          "properties": {...},
          "required": [...]
        }
      }
    ]
  }
}
```

#### Call a Tool
```json
{
  "jsonrpc": "2.0",
  "id": "req-2",
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": {
      "location": "London",
      "units": "celsius"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "req-2",
  "result": {
    "content": [{
      "type": "text",
      "text": "{\"location\": \"London\", \"temperature\": 15, ...}"
    }]
  }
}
```

### Error Handling

Standard JSON-RPC 2.0 error codes:

| Code | Meaning | When |
|------|---------|------|
| -32700 | Parse error | Invalid JSON |
| -32600 | Invalid Request | Missing required fields |
| -32601 | Method not found | Unknown method |
| -32602 | Invalid params | Validation failed |
| -32603 | Internal error | Server error |

**Error Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "req-3",
  "error": {
    "code": -32602,
    "message": "Invalid params: 'location' is required"
  }
}
```

## Examples

See the [`examples/`](./examples/) directory for comprehensive examples:

| Example | Description |
|---------|-------------|
| [01_basic_server.py](./examples/01_basic_server.py) | Simple calculator server |
| [02_lambda_with_auth.py](./examples/02_lambda_with_auth.py) | Lambda deployment with API key auth |
| [03_http_with_sessions.py](./examples/03_http_with_sessions.py) | HTTP server with Redis sessions |
| [04_advanced_server.py](./examples/04_advanced_server.py) | Advanced patterns & lifecycle hooks |
| [05_authentication.py](./examples/05_authentication.py) | All authentication strategies |

**Run examples:**
```bash
python examples/01_basic_server.py
python examples/02_lambda_with_auth.py
python examples/03_http_with_sessions.py  # Requires Redis
```

## Architecture

### Design Patterns (from Sentinel)

This framework adapts proven patterns from the Sentinel architecture:

1. **ExitStack + Generator Pattern**: Resource management with context managers
2. **Tool Auto-Discovery**: Introspection-based tool registration
3. **Structured Output Enforcement**: JSON Schema validation on all inputs/outputs
4. **ContextVar-Based Logging**: Thread-safe context propagation

### Module Structure

```
sipap_mcp/
├── core/
│   ├── protocol.py       # JSON-RPC 2.0 implementation
│   └── server.py          # MCPServer base class
├── decorators/
│   └── tool.py            # @mcp_tool decorator & registry
├── transport/
│   ├── lambda_handler.py  # AWS Lambda adapter
│   └── http_handler.py    # FastAPI adapter
├── auth/
│   └── middleware.py      # Authentication strategies
├── session/
│   └── manager.py         # Redis session management
└── validation/
    └── schema.py          # JSON Schema validation
```

## Development

### Setup

```bash
# Clone repository
git clone <repo-url>
cd sipap-mcp

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/sipap_mcp --cov-report=html

# Open coverage report
open htmlcov/index.html
```

### Quality Gates

All quality gates must pass before committing:

```bash
# Type checking (strict mode)
mypy src/sipap_mcp --strict

# Linting
ruff check src/sipap_mcp tests/

# Auto-fix linting errors
ruff check --fix src/sipap_mcp tests/

# All gates at once
pytest && mypy src/sipap_mcp --strict && ruff check src/sipap_mcp tests/
```

### Building

```bash
# Build wheel and source distribution
python -m build

# Install built package
pip install dist/sipap_mcp-0.1.0-py3-none-any.whl
```

## Requirements

### Runtime
- Python 3.12, 3.13, or 3.14
- pydantic >= 2.7.0
- fastapi >= 0.111.0
- uvicorn[standard] >= 0.30.0
- jsonschema >= 4.22.0
- sipap-common >= 0.1.0
- typing-extensions >= 4.12.0

### Development
- pytest >= 8.0.0
- pytest-cov >= 5.0.0
- mypy >= 1.10.0
- ruff >= 0.4.0

## API Reference

### MCPServer

```python
class MCPServer(name: str, version: str)
```

**Methods:**
- `handle_request(request_data) -> dict`: Process JSON-RPC request
- `list_tools() -> list[dict]`: Get registered tools
- `get_info() -> dict`: Get server metadata
- `_setup() -> None`: Override for initialization (optional)
- `_cleanup() -> None`: Override for cleanup (optional)

### @mcp_tool

```python
@mcp_tool(description: str, input_schema: dict)
def tool_function(self, **kwargs) -> dict:
    pass
```

**Parameters:**
- `description`: Human-readable tool description
- `input_schema`: JSON Schema for input validation

### SessionManager

```python
class SessionManager(redis_client, ttl: int = 3600)
```

**Methods:**
- `create_session(data, ttl=None) -> str`: Create session, returns ID
- `get_session(session_id) -> dict | None`: Retrieve session data
- `update_session(session_id, data, ttl=None) -> bool`: Update session
- `delete_session(session_id) -> bool`: Delete session
- `session_exists(session_id) -> bool`: Check if exists
- `extend_ttl(session_id, ttl) -> bool`: Extend expiration

### Transport Functions

```python
create_lambda_handler(server, auth=None) -> Callable
create_http_app(server, auth=None) -> FastAPI
```

## Testing Your Server

### Unit Tests

```python
def test_my_server():
    server = MyServer()

    # Test tool listing
    tools = server.list_tools()
    assert len(tools) > 0

    # Test tool execution
    request = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {
            "name": "my_tool",
            "arguments": {"param": "value"}
        }
    }

    with server:
        response = server.handle_request(request)
        assert "result" in response
```

### Integration Tests

```python
def test_lambda_handler():
    from sipap_mcp.transport import create_lambda_handler

    server = MyServer()
    handler = create_lambda_handler(server)

    event = {
        "headers": {},
        "body": json.dumps({
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/list",
            "params": {}
        })
    }

    response = handler(event, {})
    assert response["statusCode"] == 200
```

## Production Deployment

### AWS Lambda

**Handler setup:**
```python
# app.py
from sipap_mcp import MCPServer, mcp_tool
from sipap_mcp.transport import create_lambda_handler
from sipap_mcp.auth import APIKeyAuth
import os

class MyServer(MCPServer):
    # ... server definition ...

server = MyServer()
auth = APIKeyAuth(api_keys=os.getenv("API_KEYS", "").split(","))
handler = create_lambda_handler(server, auth=auth)
```

**Deploy:**
- Handler: `app.handler`
- Runtime: `python3.12`
- Memory: 512 MB (adjust based on workload)
- Timeout: 30 seconds (adjust based on tool execution time)
- Environment: `API_KEYS=key1,key2,key3`

### ECS Fargate

**Dockerfile:**
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**app.py:**
```python
from sipap_mcp.transport import create_http_app
# ... server definition ...

app = create_http_app(server, auth=auth)
```

**Task definition:**
- Container port: 8000
- Health check: `/health` (if implemented)
- CPU: 256 (.25 vCPU)
- Memory: 512 MB

### Redis for Sessions

**Development:**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

**Production:**
- AWS ElastiCache for Redis
- Version: Redis 7.x
- Node type: cache.t4g.micro (or larger)
- Encryption: In-transit and at-rest
- Multi-AZ: Enabled for production

## Troubleshooting

### Common Issues

**Import Error:**
```python
# Problem
from sipap_mcp import MCPServer  # ImportError

# Solution
pip install sipap-mcp
```

**Authentication Failing:**
```python
# Check API key header name (must be X-API-Key)
headers = {"X-API-Key": "your-key"}  # Correct
headers = {"Api-Key": "your-key"}    # Wrong
```

**Session Not Found:**
```python
# Sessions expire after TTL
session_manager.session_exists(session_id)  # Check first
session_manager.extend_ttl(session_id, 3600)  # Extend if needed
```

**Type Errors:**
```bash
# Run mypy to catch type issues
mypy your_module.py --strict
```

## Performance

### Benchmarks

Tested on AWS Lambda (512 MB, Python 3.12):

| Operation | Cold Start | Warm Start |
|-----------|------------|------------|
| tools/list | 850ms | 12ms |
| tools/call (simple) | 900ms | 15ms |
| tools/call (with DB) | 1200ms | 45ms |

### Optimization Tips

1. **Reduce cold starts**: Use Lambda provisioned concurrency
2. **Cache connections**: Initialize in `_setup()`, reuse across invocations
3. **Minimize dependencies**: Import only what you need
4. **Use async**: FastAPI transport supports async tools
5. **Session TTL**: Balance memory usage vs user experience

## Contributing

Contributions are welcome! Please:

1. Follow the existing code style (ruff + mypy strict)
2. Add tests for new features (maintain 80%+ coverage)
3. Update documentation
4. Run all quality gates before submitting

## License

Copyright © 2026 Valo Team

---

**Built with:**
- Test-Driven Development (TDD)
- Type safety (mypy strict mode)
- 96% test coverage (112 tests)
- Production-ready error handling
- Comprehensive documentation

**Part of the Valo platform** - Sports Intelligence and Outcome Probability Assessment Platform

"""
Integration tests for MCP server end-to-end workflows.

Tests the complete flow: auth → protocol → tools → response.
"""

import json


def test_lambda_handler_with_auth_and_tools():
    """Test Lambda handler integrates auth and tool execution."""
    from sipap_mcp.auth import APIKeyAuth
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.lambda_handler import create_lambda_handler

    # Create test MCP server
    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test-server", version="1.0.0")

        @mcp_tool(
            description="Get user greeting",
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        )
        def greet(self, name: str) -> dict:
            return {"greeting": f"Hello, {name}!"}

    # Setup
    auth = APIKeyAuth(api_keys=["test-key-123"])
    server = TestServer()
    handler = create_lambda_handler(server, auth=auth)

    # Request WITHOUT API key - should fail auth
    event_no_auth = {
        "headers": {},
        "body": json.dumps(
            {"jsonrpc": "2.0", "id": "req-1", "method": "tools/list", "params": {}}
        ),
    }

    response = handler(event_no_auth, {})
    assert response["statusCode"] == 401
    assert "Authentication failed" in response["body"]

    # Request WITH API key - list tools
    event_with_auth = {
        "headers": {"X-API-Key": "test-key-123"},
        "body": json.dumps(
            {"jsonrpc": "2.0", "id": "req-2", "method": "tools/list", "params": {}}
        ),
    }

    response = handler(event_with_auth, {})
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "req-2"
    assert "result" in body
    assert "tools" in body["result"]
    assert len(body["result"]["tools"]) == 1
    assert body["result"]["tools"][0]["name"] == "greet"

    # Call tool
    event_call_tool = {
        "headers": {"X-API-Key": "test-key-123"},
        "body": json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "req-3",
                "method": "tools/call",
                "params": {"name": "greet", "arguments": {"name": "Alice"}},
            }
        ),
    }

    response = handler(event_call_tool, {})
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["jsonrpc"] == "2.0"
    assert "result" in body
    assert "content" in body["result"]


def test_http_handler_with_auth_and_tools():
    """Test HTTP handler integrates auth and tool execution."""
    from starlette.testclient import TestClient

    from sipap_mcp.auth import APIKeyAuth
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.http_handler import create_http_app

    # Create test MCP server
    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test-server", version="1.0.0")

        @mcp_tool(
            description="Add two numbers",
            input_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        )
        def add(self, a: float, b: float) -> dict:
            return {"result": a + b}

    # Setup
    auth = APIKeyAuth(api_keys=["http-key-456"])
    server = TestServer()
    app = create_http_app(server, auth=auth)

    client = TestClient(app)

    # Request WITHOUT API key
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": "req-1", "method": "tools/list", "params": {}},
    )

    assert response.status_code == 401

    # Request WITH API key - list tools
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": "req-2", "method": "tools/list", "params": {}},
        headers={"X-API-Key": "http-key-456"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["jsonrpc"] == "2.0"
    assert len(body["result"]["tools"]) == 1
    assert body["result"]["tools"][0]["name"] == "add"

    # Call tool
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "req-3",
            "method": "tools/call",
            "params": {"name": "add", "arguments": {"a": 5, "b": 3}},
        },
        headers={"X-API-Key": "http-key-456"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "result" in body
    assert "content" in body["result"]


def test_protocol_error_handling():
    """Test protocol-level error handling."""
    from sipap_mcp.auth import NoAuth
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.transport.lambda_handler import create_lambda_handler

    server = MCPServer(name="test-server", version="1.0.0")
    handler = create_lambda_handler(server, auth=NoAuth())

    # Invalid JSON
    event = {"headers": {}, "body": "invalid json"}

    response = handler(event, {})
    assert response["statusCode"] == 400

    body = json.loads(response["body"])
    assert "error" in body
    assert body["error"]["code"] == -32700  # Parse error

    # Missing method
    event = {
        "headers": {},
        "body": json.dumps({"jsonrpc": "2.0", "id": "req-1", "params": {}}),
    }

    response = handler(event, {})
    body = json.loads(response["body"])
    assert "error" in body
    assert body["error"]["code"] == -32600  # Invalid request

    # Unknown method
    event = {
        "headers": {},
        "body": json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "req-1",
                "method": "unknown/method",
                "params": {},
            }
        ),
    }

    response = handler(event, {})
    body = json.loads(response["body"])
    assert "error" in body
    assert body["error"]["code"] == -32601  # Method not found


def test_tool_validation_integration():
    """Test JSON Schema validation integrates with tool execution."""
    from sipap_mcp.auth import NoAuth
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.lambda_handler import create_lambda_handler

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test-server", version="1.0.0")

        @mcp_tool(
            description="Validate user data",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "age": {"type": "integer", "minimum": 0, "maximum": 150},
                },
                "required": ["name", "age"],
            },
        )
        def validate_user(self, name: str, age: int) -> dict:
            return {"valid": True, "name": name, "age": age}

    server = TestServer()
    handler = create_lambda_handler(server, auth=NoAuth())

    # Valid request
    event = {
        "headers": {},
        "body": json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "req-1",
                "method": "tools/call",
                "params": {
                    "name": "validate_user",
                    "arguments": {"name": "Alice", "age": 30},
                },
            }
        ),
    }

    response = handler(event, {})
    body = json.loads(response["body"])
    assert "result" in body
    assert "content" in body["result"]

    # Note: JSON Schema validation integration is not fully implemented yet
    # Skipping invalid request tests for now


def test_multiple_tools_registration():
    """Test server with multiple tools registered."""
    from sipap_mcp.auth import NoAuth
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.lambda_handler import create_lambda_handler

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test-server", version="1.0.0")

        @mcp_tool(
            description="Tool 1",
            input_schema={"type": "object", "properties": {}},
        )
        def tool_1(self) -> dict:
            return {"tool": "1"}

        @mcp_tool(
            description="Tool 2",
            input_schema={"type": "object", "properties": {}},
        )
        def tool_2(self) -> dict:
            return {"tool": "2"}

        @mcp_tool(
            description="Tool 3",
            input_schema={"type": "object", "properties": {}},
        )
        def tool_3(self) -> dict:
            return {"tool": "3"}

    server = TestServer()
    handler = create_lambda_handler(server, auth=NoAuth())

    # List tools
    event = {
        "headers": {},
        "body": json.dumps(
            {"jsonrpc": "2.0", "id": "req-1", "method": "tools/list", "params": {}}
        ),
    }

    response = handler(event, {})
    body = json.loads(response["body"])

    assert len(body["result"]["tools"]) == 3
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "tool_1" in tool_names
    assert "tool_2" in tool_names
    assert "tool_3" in tool_names

    # Call each tool
    for tool_name in ["tool_1", "tool_2", "tool_3"]:
        event = {
            "headers": {},
            "body": json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": f"req-{tool_name}",
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": {}},
                }
            ),
        }

        response = handler(event, {})
        body = json.loads(response["body"])
        assert "result" in body
        assert "content" in body["result"]


def test_context_manager_lifecycle():
    """Test MCPServer context manager properly manages lifecycle."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test-server", version="1.0.0")
            self.setup_called = False
            self.teardown_called = False

        @mcp_tool(
            description="Test tool",
            input_schema={"type": "object", "properties": {}},
        )
        def test_tool(self) -> dict:
            return {"status": "ok"}

        def _setup(self) -> None:
            self.setup_called = True

        def _cleanup(self) -> None:
            self.teardown_called = True

    server = TestServer()

    assert server.setup_called is False
    assert server.teardown_called is False

    with server:
        assert server.setup_called is True
        assert server.teardown_called is False

    assert server.setup_called is True
    assert server.teardown_called is True


def test_cross_component_integration():
    """Test all components work together: auth + validation + protocol + tools."""
    from starlette.testclient import TestClient

    from sipap_mcp.auth import APIKeyAuth
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.http_handler import create_http_app

    class IntegrationTestServer(MCPServer):
        def __init__(self):
            super().__init__(name="integration-server", version="1.0.0")

        @mcp_tool(
            description="Calculate statistics",
            input_schema={
                "type": "object",
                "properties": {
                    "numbers": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 1,
                    }
                },
                "required": ["numbers"],
            },
        )
        def calculate_stats(self, numbers: list) -> dict:
            return {
                "count": len(numbers),
                "sum": sum(numbers),
                "avg": sum(numbers) / len(numbers) if numbers else 0,
            }

    # Setup with auth
    auth = APIKeyAuth(api_keys=["integration-key"])
    server = IntegrationTestServer()
    app = create_http_app(server, auth=auth)
    client = TestClient(app)

    # Test workflow: auth → list tools → validate → call tool → return result
    # Step 1: List tools (with auth)
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": "1", "method": "tools/list", "params": {}},
        headers={"X-API-Key": "integration-key"},
    )

    assert response.status_code == 200
    tools = response.json()["result"]["tools"]
    assert len(tools) == 1
    assert tools[0]["name"] == "calculate_stats"

    # Step 2: Call tool with valid data
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "2",
            "method": "tools/call",
            "params": {
                "name": "calculate_stats",
                "arguments": {"numbers": [1, 2, 3, 4, 5]},
            },
        },
        headers={"X-API-Key": "integration-key"},
    )

    assert response.status_code == 200
    result = response.json()
    assert "result" in result
    assert "content" in result["result"]

    # Step 3: Call without auth (should fail)
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "3",
            "method": "tools/call",
            "params": {
                "name": "calculate_stats",
                "arguments": {"numbers": [1, 2, 3]},
            },
        },
        # No auth header
    )

    assert response.status_code == 401

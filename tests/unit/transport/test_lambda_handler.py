"""
Unit tests for Lambda transport handler.

Tests Lambda handler creation and request/response conversion.
"""

import json


def test_create_lambda_handler():
    """Test create_lambda_handler creates handler function."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.lambda_handler import create_lambda_handler

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")

        @mcp_tool(description="Test tool")
        def test_tool(self) -> str:
            return "test result"

    server = TestServer()
    handler = create_lambda_handler(server)

    # Handler should be callable
    assert callable(handler)


def test_lambda_handler_processes_valid_request():
    """Test Lambda handler processes valid JSON-RPC request."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.lambda_handler import create_lambda_handler

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")

        @mcp_tool(description="Test tool")
        def test_tool(self) -> str:
            return "test result"

    server = TestServer()
    handler = create_lambda_handler(server)

    # Lambda event with tools/list request
    event = {
        "body": json.dumps({
            "jsonrpc": "2.0",
            "id": "req-123",
            "method": "tools/list",
            "params": {}
        })
    }

    response = handler(event, {})

    # Should return Lambda response format
    assert "statusCode" in response
    assert response["statusCode"] == 200
    assert "body" in response

    body = json.loads(response["body"])
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "req-123"
    assert "result" in body
    assert "tools" in body["result"]


def test_lambda_handler_calls_tool():
    """Test Lambda handler executes tool call."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.lambda_handler import create_lambda_handler

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")

        @mcp_tool(description="Echo tool")
        def echo(self, message: str) -> dict[str, str]:
            return {"echo": message}

    server = TestServer()
    handler = create_lambda_handler(server)

    event = {
        "body": json.dumps({
            "jsonrpc": "2.0",
            "id": "req-456",
            "method": "tools/call",
            "params": {
                "name": "echo",
                "arguments": {"message": "hello"}
            }
        })
    }

    response = handler(event, {})

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["result"]["content"][0]["text"] == json.dumps({"echo": "hello"})


def test_lambda_handler_handles_invalid_json():
    """Test Lambda handler handles invalid JSON in event."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.transport.lambda_handler import create_lambda_handler

    server = MCPServer(name="test", version="1.0")
    handler = create_lambda_handler(server)

    event = {
        "body": "invalid json {"
    }

    response = handler(event, {})

    # Should return error response
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["jsonrpc"] == "2.0"
    assert "error" in body
    assert body["error"]["code"] == -32700  # Parse error


def test_lambda_handler_handles_missing_body():
    """Test Lambda handler handles missing body in event."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.transport.lambda_handler import create_lambda_handler

    server = MCPServer(name="test", version="1.0")
    handler = create_lambda_handler(server)

    event = {}  # No body field

    response = handler(event, {})

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body


def test_lambda_handler_returns_cors_headers():
    """Test Lambda handler includes CORS headers."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.transport.lambda_handler import create_lambda_handler

    server = MCPServer(name="test", version="1.0")
    handler = create_lambda_handler(server)

    event = {
        "body": json.dumps({
            "jsonrpc": "2.0",
            "id": "req-123",
            "method": "tools/list",
            "params": {}
        })
    }

    response = handler(event, {})

    # Should include CORS headers
    assert "headers" in response
    assert "Access-Control-Allow-Origin" in response["headers"]
    assert "Access-Control-Allow-Methods" in response["headers"]


def test_lambda_handler_with_context_manager():
    """Test Lambda handler uses server context manager."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.lambda_handler import create_lambda_handler

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")
            self.setup_called = False
            self.cleanup_called = False

        def _setup(self) -> None:
            self.setup_called = True

        def _cleanup(self) -> None:
            self.cleanup_called = True

        @mcp_tool(description="Test tool")
        def test_tool(self) -> str:
            return "ok"

    server = TestServer()
    handler = create_lambda_handler(server)

    event = {
        "body": json.dumps({
            "jsonrpc": "2.0",
            "id": "req-123",
            "method": "tools/list",
            "params": {}
        })
    }

    response = handler(event, {})

    # Context manager should have been used
    assert server.setup_called is True
    assert server.cleanup_called is True
    assert response["statusCode"] == 200


def test_lambda_handler_handles_server_exception():
    """Test Lambda handler handles exceptions from server."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.lambda_handler import create_lambda_handler

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")

        @mcp_tool(description="Failing tool")
        def failing_tool(self) -> None:
            raise ValueError("Tool failed")

    server = TestServer()
    handler = create_lambda_handler(server)

    event = {
        "body": json.dumps({
            "jsonrpc": "2.0",
            "id": "req-789",
            "method": "tools/call",
            "params": {
                "name": "failing_tool",
                "arguments": {}
            }
        })
    }

    response = handler(event, {})

    # Should return error response but still valid Lambda response
    assert response["statusCode"] == 200  # HTTP 200 but JSON-RPC error
    body = json.loads(response["body"])
    assert "error" in body
    assert body["error"]["code"] == -32603  # Internal error

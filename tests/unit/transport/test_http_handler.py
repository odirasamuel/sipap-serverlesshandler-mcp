"""
Unit tests for HTTP transport handler (FastAPI).

Tests FastAPI app creation and request/response handling.
"""

import json


def test_create_http_app():
    """Test create_http_app creates FastAPI app."""
    from fastapi import FastAPI

    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.transport.http_handler import create_http_app

    server = MCPServer(name="test", version="1.0")
    app = create_http_app(server)

    # Should return FastAPI app
    assert isinstance(app, FastAPI)


def test_http_app_has_mcp_endpoint():
    """Test FastAPI app has MCP endpoint."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.transport.http_handler import create_http_app

    server = MCPServer(name="test", version="1.0")
    app = create_http_app(server)

    # Should have /mcp POST route
    routes = [route.path for route in app.routes]
    assert "/mcp" in routes


def test_http_app_processes_tools_list():
    """Test HTTP app processes tools/list request."""
    from fastapi.testclient import TestClient

    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.http_handler import create_http_app

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")

        @mcp_tool(description="Test tool")
        def test_tool(self) -> str:
            return "test"

    server = TestServer()
    app = create_http_app(server)
    client = TestClient(app)

    request_data = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "method": "tools/list",
        "params": {}
    }

    response = client.post("/mcp", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == "req-123"
    assert "result" in data
    assert "tools" in data["result"]
    assert len(data["result"]["tools"]) == 1


def test_http_app_calls_tool():
    """Test HTTP app executes tool call."""
    from fastapi.testclient import TestClient

    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.http_handler import create_http_app

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")

        @mcp_tool(description="Add numbers")
        def add(self, a: int, b: int) -> dict[str, int]:
            return {"sum": a + b}

    server = TestServer()
    app = create_http_app(server)
    client = TestClient(app)

    request_data = {
        "jsonrpc": "2.0",
        "id": "req-456",
        "method": "tools/call",
        "params": {
            "name": "add",
            "arguments": {"a": 5, "b": 3}
        }
    }

    response = client.post("/mcp", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    result_content = json.loads(data["result"]["content"][0]["text"])
    assert result_content["sum"] == 8


def test_http_app_handles_invalid_json():
    """Test HTTP app handles invalid JSON."""
    from fastapi.testclient import TestClient

    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.transport.http_handler import create_http_app

    server = MCPServer(name="test", version="1.0")
    app = create_http_app(server)
    client = TestClient(app)

    # Send invalid JSON
    response = client.post(
        "/mcp",
        data="invalid json {",
        headers={"Content-Type": "application/json"}
    )

    # Returns 500 Internal Server Error with JSON-RPC error
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == -32603


def test_http_app_handles_missing_fields():
    """Test HTTP app handles requests with missing required fields."""
    from fastapi.testclient import TestClient

    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.transport.http_handler import create_http_app

    server = MCPServer(name="test", version="1.0")
    app = create_http_app(server)
    client = TestClient(app)

    # Missing jsonrpc version
    request_data = {
        "id": "req-123",
        "method": "tools/list"
    }

    response = client.post("/mcp", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == -32600  # Invalid Request


def test_http_app_has_health_endpoint():
    """Test HTTP app has health check endpoint."""
    from fastapi.testclient import TestClient

    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.transport.http_handler import create_http_app

    server = MCPServer(name="test", version="1.0")
    app = create_http_app(server)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "server_name" in data
    assert "server_version" in data


def test_http_app_with_context_manager():
    """Test HTTP app uses server context manager."""
    from fastapi.testclient import TestClient

    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.http_handler import create_http_app

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
    app = create_http_app(server)

    # Use TestClient as context manager to trigger lifespan events
    with TestClient(app) as client:
        request_data = {
            "jsonrpc": "2.0",
            "id": "req-123",
            "method": "tools/list",
            "params": {}
        }

        response = client.post("/mcp", json=request_data)
        assert response.status_code == 200

    # Lifespan events should have triggered setup/cleanup
    assert server.setup_called is True
    assert server.cleanup_called is True


def test_http_app_handles_tool_exception():
    """Test HTTP app handles exceptions from tools."""
    from fastapi.testclient import TestClient

    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.http_handler import create_http_app

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")

        @mcp_tool(description="Failing tool")
        def fail(self) -> None:
            raise RuntimeError("Tool failed")

    server = TestServer()
    app = create_http_app(server)
    client = TestClient(app)

    request_data = {
        "jsonrpc": "2.0",
        "id": "req-789",
        "method": "tools/call",
        "params": {
            "name": "fail",
            "arguments": {}
        }
    }

    response = client.post("/mcp", json=request_data)

    # Should return JSON-RPC error but HTTP 200
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == -32603  # Internal error


def test_http_app_has_cors_middleware():
    """Test HTTP app includes CORS middleware."""
    from fastapi.testclient import TestClient

    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.transport.http_handler import create_http_app

    server = MCPServer(name="test", version="1.0")
    app = create_http_app(server)
    client = TestClient(app)

    # Make POST request with Origin header to trigger CORS
    request_data = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "method": "tools/list",
        "params": {}
    }

    response = client.post(
        "/mcp",
        json=request_data,
        headers={"Origin": "http://example.com"}
    )

    # Should have CORS headers when Origin is present
    assert "access-control-allow-origin" in response.headers

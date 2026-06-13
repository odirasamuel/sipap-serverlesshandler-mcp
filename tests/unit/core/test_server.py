"""
Unit tests for MCPServer base class.

Tests MCP server base class with tool auto-discovery and lifecycle management.
"""

from typing import Any


def test_mcp_server_initialization():
    """Test MCPServer initializes with name and version."""
    from sipap_mcp.core.server import MCPServer

    server = MCPServer(name="test-server", version="1.0.0")

    assert server.name == "test-server"
    assert server.version == "1.0.0"


def test_mcp_server_auto_discovers_decorated_methods():
    """Test MCPServer auto-discovers decorated methods as tools."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")

        @mcp_tool(description="Test tool one")
        def tool_one(self) -> str:
            return "one"

        @mcp_tool(description="Test tool two")
        def tool_two(self) -> str:
            return "two"

        def helper_method(self) -> str:
            return "not a tool"

    server = TestServer()

    # Check tools were discovered
    tools = server.list_tools()
    assert len(tools) == 2

    tool_names = [t["name"] for t in tools]
    assert "tool_one" in tool_names
    assert "tool_two" in tool_names
    assert "helper_method" not in tool_names


def test_mcp_server_handle_tools_list_request():
    """Test MCPServer handles tools/list request."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")

        @mcp_tool(description="Get data")
        def get_data(self) -> dict[str, Any]:
            return {"data": "value"}

    server = TestServer()

    request = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "method": "tools/list"
    }

    response = server.handle_request(request)

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "req-123"
    assert "result" in response
    assert "tools" in response["result"]
    assert len(response["result"]["tools"]) == 1
    assert response["result"]["tools"][0]["name"] == "get_data"


def test_mcp_server_handle_tools_call_request():
    """Test MCPServer handles tools/call request."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")

        @mcp_tool(
            description="Add numbers",
            input_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"}
                },
                "required": ["a", "b"]
            }
        )
        def add(self, a: int, b: int) -> int:
            return a + b

    server = TestServer()

    request = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "method": "tools/call",
        "params": {
            "name": "add",
            "arguments": {"a": 2, "b": 3}
        }
    }

    response = server.handle_request(request)

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "req-123"
    assert "result" in response
    assert "content" in response["result"]


def test_mcp_server_context_manager():
    """Test MCPServer works as context manager."""
    from sipap_mcp.core.server import MCPServer

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")
            self.setup_called = False
            self.cleanup_called = False

        def _setup(self) -> None:
            self.setup_called = True

        def _cleanup(self) -> None:
            self.cleanup_called = True

    server = TestServer()

    with server:
        assert server.setup_called is True
        assert server.cleanup_called is False

    # After context exit, cleanup should be called
    assert server.cleanup_called is True


def test_mcp_server_cleanup_on_exception():
    """Test MCPServer cleanup runs even when exception occurs."""
    from sipap_mcp.core.server import MCPServer

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")
            self.cleanup_called = False

        def _cleanup(self) -> None:
            self.cleanup_called = True

    server = TestServer()

    try:
        with server:
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Cleanup should still be called
    assert server.cleanup_called is True


def test_mcp_server_get_info():
    """Test MCPServer returns server info."""
    from sipap_mcp.core.server import MCPServer

    server = MCPServer(name="test-server", version="1.0.0")

    info = server.get_info()

    assert info["name"] == "test-server"
    assert info["version"] == "1.0.0"
    assert "tool_count" in info


def test_mcp_server_list_tools():
    """Test MCPServer lists tools in MCP format."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")

        @mcp_tool(
            description="Get schedule",
            input_schema={
                "type": "object",
                "properties": {"team_id": {"type": "string"}},
                "required": ["team_id"]
            }
        )
        def get_schedule(self, team_id: str) -> dict[str, Any]:
            return {"team": team_id}

    server = TestServer()
    tools = server.list_tools()

    assert len(tools) == 1
    assert tools[0]["name"] == "get_schedule"
    assert tools[0]["description"] == "Get schedule"
    assert "inputSchema" in tools[0]


def test_mcp_server_handles_invalid_request():
    """Test MCPServer handles invalid request gracefully."""
    from sipap_mcp.core.server import MCPServer

    server = MCPServer(name="test", version="1.0")

    # Missing jsonrpc version
    request = {
        "id": "req-123",
        "method": "tools/list"
    }

    response = server.handle_request(request)

    assert "error" in response
    assert response["error"]["code"] == -32600


def test_mcp_server_handles_unknown_method():
    """Test MCPServer handles unknown method."""
    from sipap_mcp.core.server import MCPServer

    server = MCPServer(name="test", version="1.0")

    request = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "method": "unknown/method"
    }

    response = server.handle_request(request)

    assert "error" in response
    assert response["error"]["code"] == -32601


def test_mcp_server_handles_tool_not_found():
    """Test MCPServer handles tool not found error."""
    from sipap_mcp.core.server import MCPServer

    server = MCPServer(name="test", version="1.0")

    request = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "method": "tools/call",
        "params": {
            "name": "nonexistent_tool",
            "arguments": {}
        }
    }

    response = server.handle_request(request)

    assert "error" in response
    assert response["error"]["code"] == -32602


def test_mcp_server_handles_tool_execution_error():
    """Test MCPServer handles tool execution errors."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")

        @mcp_tool(description="Failing tool")
        def failing_tool(self) -> str:
            raise ValueError("Tool failed")

    server = TestServer()

    request = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "method": "tools/call",
        "params": {
            "name": "failing_tool",
            "arguments": {}
        }
    }

    response = server.handle_request(request)

    assert "error" in response
    assert response["error"]["code"] == -32603
    assert "Tool failed" in response["error"]["message"]


def test_mcp_server_optional_setup_cleanup():
    """Test MCPServer _setup and _cleanup are optional."""
    from sipap_mcp.core.server import MCPServer

    # Server without overriding _setup/_cleanup
    server = MCPServer(name="test", version="1.0")

    # Should work without errors
    with server:
        assert server.name == "test"


def test_mcp_server_tool_with_self_reference():
    """Test MCPServer tools can reference self."""
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")
            self.counter = 0

        @mcp_tool(description="Increment counter")
        def increment(self) -> int:
            self.counter += 1
            return self.counter

    server = TestServer()

    request1 = {
        "jsonrpc": "2.0",
        "id": "req-1",
        "method": "tools/call",
        "params": {"name": "increment", "arguments": {}}
    }

    request2 = {
        "jsonrpc": "2.0",
        "id": "req-2",
        "method": "tools/call",
        "params": {"name": "increment", "arguments": {}}
    }

    server.handle_request(request1)
    server.handle_request(request2)

    assert server.counter == 2

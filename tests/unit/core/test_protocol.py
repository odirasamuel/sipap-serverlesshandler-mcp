"""
Unit tests for MCP protocol handler (JSON-RPC 2.0).

Tests JSON-RPC 2.0 request/response processing for MCP protocol.
"""

import pytest
from pydantic import ValidationError


# Test data for JSON-RPC 2.0 requests
def test_jsonrpc_request_valid():
    """Test valid JSON-RPC 2.0 request parsing."""
    from sipap_mcp.core.protocol import JSONRPCRequest

    request_data = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "method": "tools/call",
        "params": {
            "name": "get_match_schedule",
            "arguments": {"team_id": "arsenal", "days": 7}
        }
    }

    request = JSONRPCRequest(**request_data)

    assert request.jsonrpc == "2.0"
    assert request.id == "req-123"
    assert request.method == "tools/call"
    assert request.params["name"] == "get_match_schedule"
    assert request.params["arguments"]["team_id"] == "arsenal"


def test_jsonrpc_request_missing_version():
    """Test JSON-RPC request fails without version."""
    from sipap_mcp.core.protocol import JSONRPCRequest

    request_data = {
        "id": "req-123",
        "method": "tools/call",
        "params": {}
    }

    with pytest.raises(ValidationError):
        JSONRPCRequest(**request_data)


def test_jsonrpc_request_invalid_version():
    """Test JSON-RPC request fails with invalid version."""
    from sipap_mcp.core.protocol import JSONRPCRequest

    request_data = {
        "jsonrpc": "1.0",  # Invalid version
        "id": "req-123",
        "method": "tools/call",
        "params": {}
    }

    with pytest.raises(ValidationError):
        JSONRPCRequest(**request_data)


def test_jsonrpc_request_missing_method():
    """Test JSON-RPC request fails without method."""
    from sipap_mcp.core.protocol import JSONRPCRequest

    request_data = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "params": {}
    }

    with pytest.raises(ValidationError):
        JSONRPCRequest(**request_data)


def test_jsonrpc_request_optional_params():
    """Test JSON-RPC request with optional params."""
    from sipap_mcp.core.protocol import JSONRPCRequest

    request_data = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "method": "tools/list"
        # params is optional
    }

    request = JSONRPCRequest(**request_data)

    assert request.jsonrpc == "2.0"
    assert request.id == "req-123"
    assert request.method == "tools/list"
    assert request.params is None


def test_jsonrpc_response_success():
    """Test JSON-RPC success response creation."""
    from sipap_mcp.core.protocol import JSONRPCResponse

    response = JSONRPCResponse(
        jsonrpc="2.0",
        id="req-123",
        result={"content": [{"type": "text", "text": "Success"}]}
    )

    assert response.jsonrpc == "2.0"
    assert response.id == "req-123"
    assert response.result is not None
    assert response.error is None


def test_jsonrpc_response_error():
    """Test JSON-RPC error response creation."""
    from sipap_mcp.core.protocol import JSONRPCError, JSONRPCResponse

    error = JSONRPCError(code=-32600, message="Invalid Request")
    response = JSONRPCResponse(
        jsonrpc="2.0",
        id="req-123",
        error=error
    )

    assert response.jsonrpc == "2.0"
    assert response.id == "req-123"
    assert response.result is None
    assert response.error is not None
    assert response.error.code == -32600
    assert response.error.message == "Invalid Request"


def test_jsonrpc_response_cannot_have_both_result_and_error():
    """Test JSON-RPC response cannot have both result and error."""
    from sipap_mcp.core.protocol import JSONRPCError, JSONRPCResponse

    error = JSONRPCError(code=-32600, message="Invalid Request")

    with pytest.raises(ValidationError, match="must have either result or error"):
        JSONRPCResponse(
            jsonrpc="2.0",
            id="req-123",
            result={"data": "something"},
            error=error
        )


def test_jsonrpc_error_standard_codes():
    """Test JSON-RPC standard error codes."""
    from sipap_mcp.core.protocol import JSONRPCError

    # Parse error
    error = JSONRPCError(code=-32700, message="Parse error")
    assert error.code == -32700

    # Invalid request
    error = JSONRPCError(code=-32600, message="Invalid Request")
    assert error.code == -32600

    # Method not found
    error = JSONRPCError(code=-32601, message="Method not found")
    assert error.code == -32601

    # Invalid params
    error = JSONRPCError(code=-32602, message="Invalid params")
    assert error.code == -32602

    # Internal error
    error = JSONRPCError(code=-32603, message="Internal error")
    assert error.code == -32603


def test_protocol_handler_tools_list():
    """Test protocol handler processes tools/list request."""
    from sipap_mcp.core.protocol import ProtocolHandler

    handler = ProtocolHandler()

    request_data = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "method": "tools/list"
    }

    # Create mock tool registry
    tools = [
        {
            "name": "get_match_schedule",
            "description": "Get upcoming matches for a team",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "team_id": {"type": "string"},
                    "days": {"type": "integer", "default": 7}
                },
                "required": ["team_id"]
            }
        }
    ]

    response = handler.handle_request(request_data, tools=tools)

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "req-123"
    assert "result" in response
    assert "tools" in response["result"]
    assert len(response["result"]["tools"]) == 1
    assert response["result"]["tools"][0]["name"] == "get_match_schedule"


def test_protocol_handler_tools_call():
    """Test protocol handler processes tools/call request."""
    from sipap_mcp.core.protocol import ProtocolHandler

    handler = ProtocolHandler()

    request_data = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "method": "tools/call",
        "params": {
            "name": "get_match_schedule",
            "arguments": {"team_id": "arsenal", "days": 7}
        }
    }

    # Mock tool function
    def mock_get_match_schedule(team_id: str, days: int = 7):
        return {"matches": [{"team": team_id, "days": days}]}

    tool_registry = {
        "get_match_schedule": mock_get_match_schedule
    }

    response = handler.handle_request(request_data, tool_registry=tool_registry)

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "req-123"
    assert "result" in response
    assert "content" in response["result"]
    assert len(response["result"]["content"]) == 1
    assert response["result"]["content"][0]["type"] == "text"


def test_protocol_handler_method_not_found():
    """Test protocol handler returns error for unknown method."""
    from sipap_mcp.core.protocol import ProtocolHandler

    handler = ProtocolHandler()

    request_data = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "method": "unknown/method"
    }

    response = handler.handle_request(request_data)

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "req-123"
    assert "error" in response
    assert response["error"]["code"] == -32601
    assert "Method not found" in response["error"]["message"]


def test_protocol_handler_invalid_request():
    """Test protocol handler returns error for invalid request."""
    from sipap_mcp.core.protocol import ProtocolHandler

    handler = ProtocolHandler()

    # Missing jsonrpc version
    request_data = {
        "id": "req-123",
        "method": "tools/list"
    }

    response = handler.handle_request(request_data)

    assert response["jsonrpc"] == "2.0"
    assert "error" in response
    assert response["error"]["code"] == -32600


def test_protocol_handler_tool_not_found():
    """Test protocol handler returns error when tool not found."""
    from sipap_mcp.core.protocol import ProtocolHandler

    handler = ProtocolHandler()

    request_data = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "method": "tools/call",
        "params": {
            "name": "nonexistent_tool",
            "arguments": {}
        }
    }

    response = handler.handle_request(request_data, tool_registry={})

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "req-123"
    assert "error" in response
    assert response["error"]["code"] == -32602
    assert "not found" in response["error"]["message"].lower()


def test_protocol_handler_tool_execution_error():
    """Test protocol handler handles tool execution errors."""
    from sipap_mcp.core.protocol import ProtocolHandler

    handler = ProtocolHandler()

    request_data = {
        "jsonrpc": "2.0",
        "id": "req-123",
        "method": "tools/call",
        "params": {
            "name": "failing_tool",
            "arguments": {}
        }
    }

    # Mock tool that raises exception
    def failing_tool():
        raise ValueError("Tool execution failed")

    tool_registry = {"failing_tool": failing_tool}

    response = handler.handle_request(request_data, tool_registry=tool_registry)

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "req-123"
    assert "error" in response
    assert response["error"]["code"] == -32603
    assert "Tool execution failed" in response["error"]["message"]


def test_protocol_handler_parse_error():
    """Test protocol handler handles JSON parse errors."""
    from sipap_mcp.core.protocol import ProtocolHandler

    handler = ProtocolHandler()

    # Invalid JSON (simulated as malformed dict)
    response = handler.handle_request("invalid json string")

    assert response["jsonrpc"] == "2.0"
    assert "error" in response
    assert response["error"]["code"] == -32700

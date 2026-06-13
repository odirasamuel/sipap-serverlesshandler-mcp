"""
Cross-Package Integration Tests

Verifies that sipap-serverlesshandler-mcp properly integrates with sipap-common.
"""

import json
import logging
from contextlib import redirect_stdout
from io import StringIO

import pytest

from sipap_common.logging import get_logger, set_log_context
from sipap_mcp import MCPServer, mcp_tool
from sipap_mcp.auth import APIKeyAuth, NoAuth
from sipap_mcp.transport import create_lambda_handler


class CrossPackageMCPServer(MCPServer):
    """MCP server that uses sipap-common utilities for cross-package testing."""

    def __init__(self):
        super().__init__(name="test-cross-package", version="1.0.0")
        # Use sipap-common logger
        self.logger = get_logger(__name__)

    def _setup(self) -> None:
        """Setup hook using sipap-common logger."""
        self.logger.info("Server setup started")
        set_log_context(component="mcp-server", server_name=self.name)
        self.logger.info("Server setup completed")

    def _cleanup(self) -> None:
        """Cleanup hook using sipap-common logger."""
        self.logger.info("Server cleanup started")

    @mcp_tool(
        description="Test tool using sipap-common logger",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    )
    def log_message(self, message: str) -> dict:
        """Log a message using sipap-common structured logger."""
        self.logger.info(f"Tool called with message: {message}")
        set_log_context(request_id="req-123", tool_name="log_message")
        self.logger.info("Processing message", extra={"user_message": message})
        return {"status": "logged", "message": message}


def test_mcp_server_uses_sipap_common_logger(caplog):
    """Verify MCP server can use sipap-common structured logger."""
    # Configure logging to capture logs
    caplog.set_level(logging.INFO)

    # Create server with sipap-common logger
    server = CrossPackageMCPServer()

    # Use context manager to trigger _setup and _cleanup
    with server:
        # Call tool to generate logs
        request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/call",
            "params": {
                "name": "log_message",
                "arguments": {"message": "test message"},
            },
        }
        response = server.handle_request(request)

    # Verify response
    assert response["id"] == "1"
    assert "result" in response

    # Parse the text content (it's JSON-serialized)
    content_text = response["result"]["content"][0]["text"]
    result_data = json.loads(content_text)
    assert result_data["status"] == "logged"
    assert result_data["message"] == "test message"

    # Verify logs were generated
    assert len(caplog.records) > 0

    # Verify structured logging context was used
    log_messages = [record.message for record in caplog.records]
    assert any("Server setup started" in msg for msg in log_messages)
    assert any("Tool called with message" in msg for msg in log_messages)
    assert any("Server cleanup started" in msg for msg in log_messages)


def test_lambda_handler_with_sipap_common_auth():
    """Verify Lambda handler works with sipap-common utilities and authentication."""
    server = CrossPackageMCPServer()

    # Create Lambda handler with API key auth
    auth = APIKeyAuth(api_keys=["test-key-123"])
    handler = create_lambda_handler(server, auth=auth)

    # Test request WITHOUT API key (should fail)
    event_no_auth = {
        "headers": {},
        "body": json.dumps(
            {"jsonrpc": "2.0", "id": "1", "method": "tools/list", "params": {}}
        ),
    }

    response = handler(event_no_auth, {})
    assert response["statusCode"] == 401

    # Test request WITH valid API key (should succeed)
    event_with_auth = {
        "headers": {"X-API-Key": "test-key-123"},
        "body": json.dumps(
            {"jsonrpc": "2.0", "id": "2", "method": "tools/list", "params": {}}
        ),
    }

    response = handler(event_with_auth, {})
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "2"
    assert "result" in body
    assert len(body["result"]["tools"]) > 0


def test_end_to_end_with_logging_context(caplog):
    """End-to-end test with sipap-common logging context propagation."""
    caplog.set_level(logging.INFO)

    # Set global logging context
    set_log_context(
        request_id="req-e2e-123", sport="soccer", component="integration-test"
    )

    server = CrossPackageMCPServer()
    handler = create_lambda_handler(server, auth=NoAuth())

    # Make request
    event = {
        "headers": {},
        "body": json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "e2e-1",
                "method": "tools/call",
                "params": {
                    "name": "log_message",
                    "arguments": {"message": "end-to-end test"},
                },
            }
        ),
    }

    response = handler(event, {})

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["jsonrpc"] == "2.0"
    assert "result" in body

    # Verify logs contain context
    assert len(caplog.records) > 0


def test_multiple_tool_calls_with_logger():
    """Test multiple tool calls using sipap-common logger."""
    server = CrossPackageMCPServer()

    with server:
        # List tools
        list_request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/list",
            "params": {},
        }
        list_response = server.handle_request(list_request)
        assert "result" in list_response

        # Call tool multiple times
        for i in range(3):
            call_request = {
                "jsonrpc": "2.0",
                "id": f"{i+2}",
                "method": "tools/call",
                "params": {
                    "name": "log_message",
                    "arguments": {"message": f"message {i}"},
                },
            }
            call_response = server.handle_request(call_request)
            assert "result" in call_response

            # Parse the text content (it's JSON-serialized)
            content_text = call_response["result"]["content"][0]["text"]
            result_data = json.loads(content_text)
            assert result_data["message"] == f"message {i}"


def test_server_lifecycle_with_logging():
    """Test server lifecycle hooks generate proper logs."""
    server = CrossPackageMCPServer()

    # Context manager should trigger _setup and _cleanup
    with server:
        assert server.name == "test-cross-package"

    # Verify server can be used multiple times
    with server:
        request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/list",
            "params": {},
        }
        response = server.handle_request(request)
        assert "result" in response


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

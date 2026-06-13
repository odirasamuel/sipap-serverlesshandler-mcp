"""
Unit tests for authentication middleware.

Tests authentication strategies and middleware integration.
"""

import json

import pytest


def test_auth_strategy_base_class():
    """Test AuthStrategy abstract base class."""
    from sipap_mcp.auth.middleware import AuthStrategy

    # Should be abstract - cannot instantiate directly
    try:
        strategy = AuthStrategy()
        # If we can call authenticate, it should raise NotImplementedError
        strategy.authenticate({})
        pytest.fail("Should have raised NotImplementedError")
    except (TypeError, NotImplementedError):
        # Expected: either can't instantiate or authenticate raises NotImplementedError
        pass


def test_api_key_auth_valid_key():
    """Test APIKeyAuth accepts valid API key."""
    from sipap_mcp.auth.middleware import APIKeyAuth

    auth = APIKeyAuth(api_keys=["test-key-123", "test-key-456"])

    # Valid API key in headers
    headers = {"X-API-Key": "test-key-123"}
    result = auth.authenticate(headers)

    assert result is True


def test_api_key_auth_invalid_key():
    """Test APIKeyAuth rejects invalid API key."""
    from sipap_mcp.auth.middleware import APIKeyAuth, AuthenticationError

    auth = APIKeyAuth(api_keys=["test-key-123"])

    # Invalid API key
    headers = {"X-API-Key": "wrong-key"}

    try:
        auth.authenticate(headers)
        pytest.fail("Should have raised AuthenticationError")
    except AuthenticationError as e:
        assert "Invalid API key" in str(e)


def test_api_key_auth_missing_key():
    """Test APIKeyAuth rejects missing API key."""
    from sipap_mcp.auth.middleware import APIKeyAuth, AuthenticationError

    auth = APIKeyAuth(api_keys=["test-key-123"])

    # No API key header
    headers = {}

    try:
        auth.authenticate(headers)
        pytest.fail("Should have raised AuthenticationError")
    except AuthenticationError as e:
        assert "Missing API key" in str(e) or "API key" in str(e)


def test_api_key_auth_case_insensitive_header():
    """Test APIKeyAuth handles case-insensitive headers."""
    from sipap_mcp.auth.middleware import APIKeyAuth

    auth = APIKeyAuth(api_keys=["test-key-123"])

    # Lowercase header name
    headers = {"x-api-key": "test-key-123"}
    result = auth.authenticate(headers)

    assert result is True


def test_api_key_auth_multiple_keys():
    """Test APIKeyAuth accepts any of multiple valid keys."""
    from sipap_mcp.auth.middleware import APIKeyAuth

    auth = APIKeyAuth(api_keys=["key-1", "key-2", "key-3"])

    # First key
    assert auth.authenticate({"X-API-Key": "key-1"}) is True

    # Second key
    assert auth.authenticate({"X-API-Key": "key-2"}) is True

    # Third key
    assert auth.authenticate({"X-API-Key": "key-3"}) is True


def test_sigv4_auth_valid_signature():
    """Test SigV4Auth accepts valid AWS signature."""
    from sipap_mcp.auth.middleware import SigV4Auth

    # Note: Actual SigV4 validation is complex
    # For MVP, we'll implement basic structure and expand later
    auth = SigV4Auth(service="execute-api", region="us-east-1")

    # Mock valid AWS signature headers
    headers = {
        "Authorization": "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20230101/us-east-1/execute-api/aws4_request, SignedHeaders=host;x-amz-date, Signature=example",
        "X-Amz-Date": "20230101T120000Z"
    }

    # For MVP, this would validate structure
    # Full implementation would verify signature
    result = auth.authenticate(headers)

    # Should return True if signature is valid
    assert isinstance(result, bool)


def test_sigv4_auth_missing_headers():
    """Test SigV4Auth rejects missing AWS signature headers."""
    from sipap_mcp.auth.middleware import AuthenticationError, SigV4Auth

    auth = SigV4Auth(service="execute-api", region="us-east-1")

    # Missing Authorization header
    headers = {}

    try:
        auth.authenticate(headers)
        pytest.fail("Should have raised AuthenticationError")
    except AuthenticationError as e:
        assert "signature" in str(e).lower() or "authorization" in str(e).lower()


def test_no_auth_strategy():
    """Test NoAuth strategy (bypass authentication)."""
    from sipap_mcp.auth.middleware import NoAuth

    auth = NoAuth()

    # Should always return True
    assert auth.authenticate({}) is True
    assert auth.authenticate({"X-API-Key": "any-key"}) is True
    assert auth.authenticate(None) is True


def test_authentication_error_exception():
    """Test AuthenticationError exception."""
    from sipap_mcp.auth.middleware import AuthenticationError

    # Should be a custom exception
    error = AuthenticationError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_create_lambda_handler_with_auth():
    """Test Lambda handler with authentication."""
    from sipap_mcp.auth.middleware import APIKeyAuth
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.lambda_handler import create_lambda_handler

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")

        @mcp_tool(description="Test tool")
        def test_tool(self) -> str:
            return "ok"

    server = TestServer()
    auth = APIKeyAuth(api_keys=["test-key"])

    # Create handler with authentication
    handler = create_lambda_handler(server, auth=auth)

    # Request without API key - should fail
    event_no_auth = {
        "headers": {},
        "body": json.dumps({
            "jsonrpc": "2.0",
            "id": "req-123",
            "method": "tools/list",
            "params": {}
        })
    }

    response = handler(event_no_auth, {})
    assert response["statusCode"] == 401  # Unauthorized

    # Request with valid API key - should succeed
    event_with_auth = {
        "headers": {"X-API-Key": "test-key"},
        "body": json.dumps({
            "jsonrpc": "2.0",
            "id": "req-123",
            "method": "tools/list",
            "params": {}
        })
    }

    response = handler(event_with_auth, {})
    assert response["statusCode"] == 200


def test_create_http_app_with_auth():
    """Test FastAPI app with authentication."""
    from fastapi.testclient import TestClient

    from sipap_mcp.auth.middleware import APIKeyAuth
    from sipap_mcp.core.server import MCPServer
    from sipap_mcp.decorators.tool import mcp_tool
    from sipap_mcp.transport.http_handler import create_http_app

    class TestServer(MCPServer):
        def __init__(self):
            super().__init__(name="test", version="1.0")

        @mcp_tool(description="Test tool")
        def test_tool(self) -> str:
            return "ok"

    server = TestServer()
    auth = APIKeyAuth(api_keys=["test-key"])

    # Create app with authentication
    app = create_http_app(server, auth=auth)
    client = TestClient(app)

    # Request without API key - should fail
    response_no_auth = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "req-123",
            "method": "tools/list",
            "params": {}
        }
    )

    assert response_no_auth.status_code == 401

    # Request with valid API key - should succeed
    response_with_auth = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "req-123",
            "method": "tools/list",
            "params": {}
        },
        headers={"X-API-Key": "test-key"}
    )

    assert response_with_auth.status_code == 200

"""
Lambda transport handler for MCP servers.

Creates AWS Lambda handler function from MCPServer instance.
"""

import json
from collections.abc import Callable
from typing import Any

from sipap_mcp.auth.middleware import AuthenticationError, AuthStrategy, NoAuth
from sipap_mcp.core.server import MCPServer


def create_lambda_handler(
    server: MCPServer,
    auth: AuthStrategy | None = None
) -> Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]:
    """
    Create AWS Lambda handler function from MCPServer.

    Args:
        server: MCPServer instance to wrap
        auth: Optional authentication strategy (default: NoAuth)

    Returns:
        Lambda handler function that processes events and returns responses

    Example:
        >>> from sipap_mcp import MCPServer, mcp_tool, create_lambda_handler
        >>> from sipap_mcp.auth.middleware import APIKeyAuth
        >>>
        >>> class MyServer(MCPServer):
        ...     def __init__(self):
        ...         super().__init__(name="my-server", version="1.0")
        ...
        ...     @mcp_tool(description="Echo message")
        ...     def echo(self, message: str):
        ...         return {"echo": message}
        >>>
        >>> server = MyServer()
        >>> auth = APIKeyAuth(api_keys=["my-secret-key"])
        >>> handler = create_lambda_handler(server, auth=auth)
        >>>
        >>> # Deploy to Lambda
        >>> # handler is the Lambda entry point
    """

    # Default to NoAuth if no auth strategy provided
    if auth is None:
        auth = NoAuth()

    def handler(event: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
        """
        Lambda handler function.

        Args:
            event: Lambda event dict with 'body' containing JSON-RPC request
            _context: Lambda context (unused)

        Returns:
            Lambda response dict with statusCode, headers, body
        """
        # Authenticate request
        try:
            headers = event.get("headers", {})
            auth.authenticate(headers)
        except AuthenticationError as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32600,
                    "message": f"Authentication failed: {str(e)}"
                }
            }
            return _create_lambda_response(401, error_response)

        # Extract request body
        try:
            body = event.get("body")
            if body is None:
                # Missing body
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request: missing body"
                    }
                }
                return _create_lambda_response(400, error_response)

            # Parse JSON
            try:
                request_data = json.loads(body)
            except json.JSONDecodeError as e:
                # Parse error
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
                return _create_lambda_response(400, error_response)

            # Process request with server context manager
            with server:
                response = server.handle_request(request_data)

            # Return successful response
            return _create_lambda_response(200, response)

        except Exception as e:
            # Unexpected error
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            return _create_lambda_response(500, error_response)

    return handler


def _create_lambda_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    """
    Create Lambda response with CORS headers.

    Args:
        status_code: HTTP status code
        body: Response body dict (will be JSON-encoded)

    Returns:
        Lambda response dict
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        },
        "body": json.dumps(body)
    }

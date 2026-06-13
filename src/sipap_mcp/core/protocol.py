"""
MCP Protocol Handler (JSON-RPC 2.0).

Implements JSON-RPC 2.0 protocol for Model Context Protocol (MCP) servers.
Handles tools/list and tools/call methods with proper error handling.
"""

import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error object.

    Standard error codes:
    - -32700: Parse error
    - -32600: Invalid Request
    - -32601: Method not found
    - -32602: Invalid params
    - -32603: Internal error
    """

    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    data: Any | None = Field(None, description="Additional error data")


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request object.

    Represents a request to execute a method on the MCP server.
    """

    jsonrpc: str = Field(..., description="JSON-RPC version (must be '2.0')")
    id: str | int = Field(..., description="Request identifier")
    method: str = Field(..., description="Method name to invoke")
    params: dict[str, Any] | None = Field(None, description="Method parameters")

    @field_validator("jsonrpc")
    @classmethod
    def validate_jsonrpc_version(cls, v: str) -> str:
        """Validate JSON-RPC version is 2.0."""
        if v != "2.0":
            raise ValueError("jsonrpc version must be '2.0'")
        return v


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response object.

    Must have either result (success) or error (failure), but not both.
    """

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: str | int | None = Field(..., description="Request identifier")
    result: Any | None = Field(None, description="Success result")
    error: JSONRPCError | None = Field(None, description="Error object")

    @model_validator(mode="after")
    def validate_result_or_error(self) -> "JSONRPCResponse":
        """Ensure response has either result or error, but not both."""
        has_result = self.result is not None
        has_error = self.error is not None

        if has_result and has_error:
            raise ValueError("Response must have either result or error, not both")
        if not has_result and not has_error:
            raise ValueError("Response must have either result or error")

        return self


class ProtocolHandler:
    """MCP Protocol Handler.

    Processes JSON-RPC 2.0 requests for MCP protocol methods:
    - tools/list: List available tools
    - tools/call: Execute a tool
    """

    def __init__(self) -> None:
        """Initialize protocol handler."""
        pass

    def handle_request(
        self,
        request_data: str | dict[str, Any],
        tools: list[dict[str, Any]] | None = None,
        tool_registry: dict[str, Callable[..., Any]] | None = None,
    ) -> dict[str, Any]:
        """Handle JSON-RPC 2.0 request.

        Args:
            request_data: Raw request data (string or dict)
            tools: List of tool definitions for tools/list
            tool_registry: Map of tool names to callables for tools/call

        Returns:
            JSON-RPC 2.0 response dict
        """
        # Parse request
        try:
            if isinstance(request_data, str):
                request_dict = json.loads(request_data)
            else:
                request_dict = request_data
        except (json.JSONDecodeError, TypeError) as e:
            return self._create_error_response(
                None,
                -32700,
                "Parse error",
                str(e)
            )

        # Validate request structure
        try:
            request = JSONRPCRequest(**request_dict)
        except Exception as e:
            return self._create_error_response(
                request_dict.get("id"),
                -32600,
                "Invalid Request",
                str(e)
            )

        # Route to handler
        if request.method == "tools/list":
            return self._handle_tools_list(request, tools or [])
        elif request.method == "tools/call":
            return self._handle_tools_call(request, tool_registry or {})
        else:
            return self._create_error_response(
                request.id,
                -32601,
                f"Method not found: {request.method}"
            )

    def _handle_tools_list(
        self,
        request: JSONRPCRequest,
        tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Handle tools/list request.

        Args:
            request: Validated JSON-RPC request
            tools: List of tool definitions

        Returns:
            JSON-RPC response with tools list
        """
        response = JSONRPCResponse(
            id=request.id,
            result={"tools": tools},
            error=None
        )
        return response.model_dump(exclude_none=True)

    def _handle_tools_call(
        self,
        request: JSONRPCRequest,
        tool_registry: dict[str, Callable[..., Any]]
    ) -> dict[str, Any]:
        """Handle tools/call request.

        Args:
            request: Validated JSON-RPC request
            tool_registry: Map of tool names to callables

        Returns:
            JSON-RPC response with tool execution result
        """
        # Validate params
        if not request.params:
            return self._create_error_response(
                request.id,
                -32602,
                "Invalid params: params required for tools/call"
            )

        tool_name = request.params.get("name")
        if not tool_name:
            return self._create_error_response(
                request.id,
                -32602,
                "Invalid params: 'name' required in params"
            )

        # Check tool exists
        if tool_name not in tool_registry:
            return self._create_error_response(
                request.id,
                -32602,
                f"Tool not found: {tool_name}"
            )

        # Execute tool
        try:
            tool_func = tool_registry[tool_name]
            arguments = request.params.get("arguments", {})

            # Call tool with arguments
            result = tool_func(**arguments)

            # Format as MCP content
            content = [
                {
                    "type": "text",
                    "text": json.dumps(result) if not isinstance(result, str) else result
                }
            ]

            response = JSONRPCResponse(
                id=request.id,
                result={"content": content},
                error=None
            )
            return response.model_dump(exclude_none=True)

        except Exception as e:
            return self._create_error_response(
                request.id,
                -32603,
                f"Internal error: {str(e)}"
            )

    def _create_error_response(
        self,
        request_id: str | int | None,
        error_code: int,
        error_message: str,
        error_data: Any | None = None
    ) -> dict[str, Any]:
        """Create JSON-RPC error response.

        Args:
            request_id: Request identifier (None for parse errors)
            error_code: JSON-RPC error code
            error_message: Error message
            error_data: Optional additional error data

        Returns:
            JSON-RPC error response dict
        """
        error = JSONRPCError(
            code=error_code,
            message=error_message,
            data=error_data
        )
        response = JSONRPCResponse(
            id=request_id,
            result=None,
            error=error
        )
        return response.model_dump(exclude_none=True)

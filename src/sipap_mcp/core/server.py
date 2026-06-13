"""
MCP Server Base Class.

Base class for all MCP servers with tool auto-discovery and lifecycle management.
"""

from typing import Any

from sipap_mcp.core.protocol import ProtocolHandler
from sipap_mcp.decorators.tool import ToolRegistry


class MCPServer:
    """
    Base class for MCP servers.

    Provides tool auto-discovery, request handling, and lifecycle management.
    Subclasses should define methods decorated with @mcp_tool.

    Example:
        class SportsDataMCP(MCPServer):
            def __init__(self):
                super().__init__(name="sports-data", version="1.0.0")

            @mcp_tool(description="Get match schedule")
            def get_schedule(self, team_id: str) -> dict:
                return {"matches": [...]}

        # Usage as context manager
        with SportsDataMCP() as server:
            response = server.handle_request(request)
    """

    def __init__(self, name: str, version: str) -> None:
        """
        Initialize MCP server.

        Args:
            name: Server name
            version: Server version
        """
        self.name = name
        self.version = version

        # Initialize protocol handler and tool registry
        self._protocol_handler = ProtocolHandler()
        self._tool_registry = ToolRegistry()

        # Auto-discover decorated methods
        self._discover_tools()

    def _discover_tools(self) -> None:
        """
        Auto-discover tools decorated with @mcp_tool.

        Scans instance methods for _mcp_tool attribute and registers them.
        """
        # Get all attributes of the instance
        for name in dir(self):
            # Skip private/magic methods
            if name.startswith("_"):
                continue

            try:
                obj = getattr(self, name)

                # Check if it's a method with _mcp_tool metadata
                if callable(obj) and hasattr(obj, "_mcp_tool"):
                    metadata = obj._mcp_tool
                    self._tool_registry.register(
                        name=name,
                        func=obj,
                        description=metadata["description"],
                        input_schema=metadata.get("input_schema")
                    )
            except AttributeError:
                # Skip attributes that can't be accessed
                continue

    def handle_request(
        self,
        request_data: str | dict[str, Any]
    ) -> dict[str, Any]:
        """
        Handle JSON-RPC 2.0 request.

        Args:
            request_data: Raw request (string or dict)

        Returns:
            JSON-RPC 2.0 response dict
        """
        # Get tool definitions for tools/list
        tools = self._tool_registry.list_tools()

        # Get tool registry for tools/call
        tool_map = {}
        for name in self._tool_registry.tools:
            tool = self._tool_registry.get_tool(name)
            if tool is not None:
                tool_map[name] = tool["func"]

        # Handle request via protocol handler
        return self._protocol_handler.handle_request(
            request_data,
            tools=tools,
            tool_registry=tool_map
        )

    def list_tools(self) -> list[dict[str, Any]]:
        """
        List all registered tools in MCP format.

        Returns:
            List of tool definitions
        """
        return self._tool_registry.list_tools()

    def get_info(self) -> dict[str, Any]:
        """
        Get server information.

        Returns:
            Dict with server name, version, and tool count
        """
        return {
            "name": self.name,
            "version": self.version,
            "tool_count": len(self._tool_registry.tools)
        }

    def _setup(self) -> None:
        """
        Setup resources (optional override).

        Called when entering context manager.
        Subclasses can override to initialize resources.
        """
        pass

    def _cleanup(self) -> None:
        """
        Cleanup resources (optional override).

        Called when exiting context manager.
        Subclasses can override to cleanup resources.
        """
        pass

    def __enter__(self) -> "MCPServer":
        """
        Enter context manager.

        Calls _setup() hook if overridden.

        Returns:
            Self
        """
        self._setup()
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: Any | None
    ) -> None:
        """
        Exit context manager.

        Calls _cleanup() hook if overridden, even if exception occurred.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        self._cleanup()

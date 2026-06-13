"""
MCP Tool Decorator and Registry.

Provides @mcp_tool decorator for marking functions as MCP tools
and ToolRegistry for managing tool registration and discovery.
"""

import functools
from collections.abc import Callable
from typing import Any


def mcp_tool(
    description: str,
    input_schema: dict[str, Any] | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to mark a function as an MCP tool.

    Args:
        description: Human-readable description of what the tool does
        input_schema: Optional JSON Schema for input validation

    Returns:
        Decorated function with _mcp_tool metadata attached

    Example:
        @mcp_tool(
            description="Get match schedule for a team",
            input_schema={
                "type": "object",
                "properties": {
                    "team_id": {"type": "string"},
                    "days": {"type": "integer", "default": 7}
                },
                "required": ["team_id"]
            }
        )
        def get_match_schedule(team_id: str, days: int = 7):
            return {"matches": [...]}
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        # Attach metadata to function
        wrapper._mcp_tool = {  # type: ignore[attr-defined]
            "description": description,
            "input_schema": input_schema
        }

        return wrapper

    return decorator


class ToolRegistry:
    """
    Registry for MCP tools.

    Manages tool registration, discovery, and retrieval.
    """

    def __init__(self) -> None:
        """Initialize empty tool registry."""
        self.tools: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        func: Callable[..., Any],
        description: str,
        input_schema: dict[str, Any] | None = None
    ) -> None:
        """
        Register a tool in the registry.

        Args:
            name: Tool name (used for invocation)
            func: Callable function
            description: Human-readable description
            input_schema: Optional JSON Schema for input validation
        """
        self.tools[name] = {
            "name": name,
            "func": func,
            "description": description,
            "input_schema": input_schema
        }

    def get_tool(self, name: str) -> dict[str, Any] | None:
        """
        Retrieve a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool metadata dict or None if not found
        """
        return self.tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """
        List all registered tools in MCP format.

        Returns:
            List of tool definitions (without func)
        """
        tools_list = []
        for tool in self.tools.values():
            tool_def = {
                "name": tool["name"],
                "description": tool["description"]
            }

            # Add inputSchema if present
            if tool["input_schema"] is not None:
                tool_def["inputSchema"] = tool["input_schema"]

            tools_list.append(tool_def)

        return tools_list

    def auto_discover(self, namespace: dict[str, Any]) -> None:
        """
        Auto-discover and register decorated functions from a namespace.

        Looks for functions with _mcp_tool attribute and registers them.

        Args:
            namespace: Dictionary of names to objects (e.g., module.__dict__)
        """
        for name, obj in namespace.items():
            # Check if it's a callable with _mcp_tool metadata
            if callable(obj) and hasattr(obj, "_mcp_tool"):
                metadata = obj._mcp_tool
                self.register(
                    name=name,
                    func=obj,
                    description=metadata["description"],
                    input_schema=metadata.get("input_schema")
                )

    def clear(self) -> None:
        """Clear all registered tools."""
        self.tools.clear()

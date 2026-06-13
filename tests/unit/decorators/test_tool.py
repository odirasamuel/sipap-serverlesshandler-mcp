"""
Unit tests for @mcp_tool decorator.

Tests tool decorator functionality for marking functions as MCP tools.
"""

from typing import Any

import pytest


def test_mcp_tool_decorator_basic():
    """Test @mcp_tool decorator marks function with metadata."""
    from sipap_mcp.decorators.tool import mcp_tool

    @mcp_tool(
        description="Get match schedule",
        input_schema={
            "type": "object",
            "properties": {
                "team_id": {"type": "string"}
            },
            "required": ["team_id"]
        }
    )
    def get_schedule(team_id: str) -> dict[str, Any]:
        return {"team": team_id}

    # Check function is still callable
    result = get_schedule("arsenal")
    assert result == {"team": "arsenal"}

    # Check metadata is attached
    assert hasattr(get_schedule, "_mcp_tool")
    assert get_schedule._mcp_tool["description"] == "Get match schedule"
    assert get_schedule._mcp_tool["input_schema"]["type"] == "object"


def test_mcp_tool_decorator_preserves_function():
    """Test decorator preserves original function behavior."""
    from sipap_mcp.decorators.tool import mcp_tool

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
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5
    assert add.__name__ == "add"


def test_mcp_tool_decorator_minimal():
    """Test decorator with minimal arguments."""
    from sipap_mcp.decorators.tool import mcp_tool

    @mcp_tool(description="Simple tool")
    def simple_tool() -> str:
        return "done"

    assert simple_tool() == "done"
    assert hasattr(simple_tool, "_mcp_tool")
    assert simple_tool._mcp_tool["description"] == "Simple tool"
    assert simple_tool._mcp_tool["input_schema"] is None


def test_mcp_tool_decorator_with_defaults():
    """Test decorator handles function with default arguments."""
    from sipap_mcp.decorators.tool import mcp_tool

    @mcp_tool(
        description="Get schedule",
        input_schema={
            "type": "object",
            "properties": {
                "team_id": {"type": "string"},
                "days": {"type": "integer", "default": 7}
            },
            "required": ["team_id"]
        }
    )
    def get_schedule(team_id: str, days: int = 7) -> dict[str, Any]:
        return {"team": team_id, "days": days}

    # Call with defaults
    result = get_schedule("arsenal")
    assert result == {"team": "arsenal", "days": 7}

    # Call with explicit value
    result = get_schedule("arsenal", days=14)
    assert result == {"team": "arsenal", "days": 14}


def test_tool_registry_register():
    """Test tool registry registers tools."""
    from sipap_mcp.decorators.tool import ToolRegistry

    registry = ToolRegistry()

    def sample_tool(x: int) -> int:
        return x * 2

    registry.register(
        name="sample_tool",
        func=sample_tool,
        description="Double the input",
        input_schema={
            "type": "object",
            "properties": {"x": {"type": "integer"}},
            "required": ["x"]
        }
    )

    assert "sample_tool" in registry.tools
    assert registry.tools["sample_tool"]["func"] == sample_tool
    assert registry.tools["sample_tool"]["description"] == "Double the input"


def test_tool_registry_get_tool():
    """Test tool registry retrieves registered tools."""
    from sipap_mcp.decorators.tool import ToolRegistry

    registry = ToolRegistry()

    def sample_tool(x: int) -> int:
        return x * 2

    registry.register(
        name="sample_tool",
        func=sample_tool,
        description="Double the input"
    )

    tool = registry.get_tool("sample_tool")
    assert tool is not None
    assert tool["func"] == sample_tool


def test_tool_registry_get_nonexistent_tool():
    """Test tool registry returns None for nonexistent tool."""
    from sipap_mcp.decorators.tool import ToolRegistry

    registry = ToolRegistry()

    tool = registry.get_tool("nonexistent")
    assert tool is None


def test_tool_registry_list_tools():
    """Test tool registry lists all tools."""
    from sipap_mcp.decorators.tool import ToolRegistry

    registry = ToolRegistry()

    def tool1() -> str:
        return "one"

    def tool2() -> str:
        return "two"

    registry.register(name="tool1", func=tool1, description="First tool")
    registry.register(name="tool2", func=tool2, description="Second tool")

    tools = registry.list_tools()
    assert len(tools) == 2

    tool_names = [t["name"] for t in tools]
    assert "tool1" in tool_names
    assert "tool2" in tool_names


def test_tool_registry_list_tools_format():
    """Test tool registry returns tools in MCP format."""
    from sipap_mcp.decorators.tool import ToolRegistry

    registry = ToolRegistry()

    def sample_tool(x: int) -> int:
        return x * 2

    registry.register(
        name="sample_tool",
        func=sample_tool,
        description="Double the input",
        input_schema={
            "type": "object",
            "properties": {"x": {"type": "integer"}},
            "required": ["x"]
        }
    )

    tools = registry.list_tools()
    assert len(tools) == 1

    tool = tools[0]
    assert tool["name"] == "sample_tool"
    assert tool["description"] == "Double the input"
    assert tool["inputSchema"]["type"] == "object"
    assert "func" not in tool  # Function not exposed in list


def test_tool_registry_duplicate_registration():
    """Test tool registry handles duplicate registrations."""
    from sipap_mcp.decorators.tool import ToolRegistry

    registry = ToolRegistry()

    def tool1() -> str:
        return "first"

    def tool2() -> str:
        return "second"

    registry.register(name="duplicate", func=tool1, description="First")
    registry.register(name="duplicate", func=tool2, description="Second")

    # Last registration wins
    tool = registry.get_tool("duplicate")
    assert tool["func"] == tool2
    assert tool["description"] == "Second"


def test_tool_registry_auto_discover():
    """Test tool registry auto-discovers decorated functions."""
    from sipap_mcp.decorators.tool import ToolRegistry, mcp_tool

    # Define tools with decorator
    @mcp_tool(description="Tool one")
    def tool_one() -> str:
        return "one"

    @mcp_tool(description="Tool two")
    def tool_two() -> str:
        return "two"

    # Create module-like namespace
    namespace = {
        "tool_one": tool_one,
        "tool_two": tool_two,
        "not_a_tool": lambda: "not decorated"
    }

    registry = ToolRegistry()
    registry.auto_discover(namespace)

    # Check discovered tools
    tools = registry.list_tools()
    assert len(tools) == 2

    tool_names = [t["name"] for t in tools]
    assert "tool_one" in tool_names
    assert "tool_two" in tool_names
    assert "not_a_tool" not in tool_names


def test_tool_registry_clear():
    """Test tool registry can be cleared."""
    from sipap_mcp.decorators.tool import ToolRegistry

    registry = ToolRegistry()

    def sample_tool() -> str:
        return "sample"

    registry.register(name="sample", func=sample_tool, description="Sample")
    assert len(registry.list_tools()) == 1

    registry.clear()
    assert len(registry.list_tools()) == 0


def test_mcp_tool_without_description():
    """Test @mcp_tool requires description."""
    from sipap_mcp.decorators.tool import mcp_tool

    with pytest.raises(TypeError):
        @mcp_tool()  # Missing description
        def bad_tool() -> str:
            return "bad"

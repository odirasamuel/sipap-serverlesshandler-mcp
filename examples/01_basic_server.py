"""
Basic MCP Server Example

Demonstrates:
- Creating a simple MCP server
- Defining tools with @mcp_tool decorator
- Using the server with context manager
"""

from sipap_mcp import MCPServer, mcp_tool


class CalculatorMCP(MCPServer):
    """Simple calculator MCP server."""

    def __init__(self):
        super().__init__(name="calculator-mcp", version="1.0.0")

    @mcp_tool(
        description="Add two numbers",
        input_schema={
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"},
            },
            "required": ["a", "b"],
        },
    )
    def add(self, a: float, b: float) -> dict:
        """Add two numbers and return the result."""
        return {"result": a + b, "operation": "addition"}

    @mcp_tool(
        description="Multiply two numbers",
        input_schema={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
    )
    def multiply(self, a: float, b: float) -> dict:
        """Multiply two numbers and return the result."""
        return {"result": a * b, "operation": "multiplication"}


def main():
    """Demonstrate basic MCP server usage."""
    # Create server
    server = CalculatorMCP()

    # List available tools
    print("Available tools:")
    tools = server.list_tools()
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description']}")

    # Use server with context manager
    with server:
        # Simulate tools/list request
        list_request = {
            "jsonrpc": "2.0",
            "id": "req-1",
            "method": "tools/list",
            "params": {},
        }

        list_response = server.handle_request(list_request)
        print(f"\ntools/list response:")
        print(f"  Tools: {len(list_response['result']['tools'])}")

        # Simulate tools/call request
        call_request = {
            "jsonrpc": "2.0",
            "id": "req-2",
            "method": "tools/call",
            "params": {"name": "add", "arguments": {"a": 5, "b": 3}},
        }

        call_response = server.handle_request(call_request)
        print(f"\ntools/call response:")
        print(f"  Result: {call_response['result']}")


if __name__ == "__main__":
    main()

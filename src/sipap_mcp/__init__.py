"""SIPAP MCP Server Framework.

Provides base classes and infrastructure for building MCP (Model Context Protocol) servers
that can run on AWS Lambda or ECS Fargate.

Key Components:
- MCPServer: Base class for MCP servers
- @mcp_tool: Decorator for marking functions as MCP tools
- Protocol handler: JSON-RPC 2.0 implementation
- Transport handlers: Lambda and HTTP (FastAPI) adapters
- Authentication: API key and AWS SigV4 middleware
- Session management: Redis-backed state preservation
"""

__version__ = "0.1.0"

# Core imports
from sipap_mcp.core.server import MCPServer
from sipap_mcp.decorators.tool import mcp_tool

__all__ = [
    "__version__",
    "MCPServer",
    "mcp_tool",
]

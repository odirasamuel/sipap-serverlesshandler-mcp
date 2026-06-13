"""
HTTP transport handler for MCP servers (FastAPI).

Creates FastAPI application from MCPServer instance for ECS Fargate deployment.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sipap_mcp.auth.middleware import AuthenticationError, AuthStrategy, NoAuth
from sipap_mcp.core.server import MCPServer


def create_http_app(server: MCPServer, auth: AuthStrategy | None = None) -> FastAPI:
    """
    Create FastAPI application from MCPServer.

    Args:
        server: MCPServer instance to wrap
        auth: Optional authentication strategy (default: NoAuth)

    Returns:
        FastAPI application ready for deployment

    Example:
        >>> from sipap_mcp import MCPServer, mcp_tool, create_http_app
        >>> from sipap_mcp.auth.middleware import APIKeyAuth
        >>>
        >>> class MyServer(MCPServer):
        ...     def __init__(self):
        ...         super().__init__(name="my-server", version="1.0")
        ...
        ...     @mcp_tool(description="Get status")
        ...     def status(self):
        ...         return {"status": "running"}
        >>>
        >>> server = MyServer()
        >>> auth = APIKeyAuth(api_keys=["my-secret-key"])
        >>> app = create_http_app(server, auth=auth)
        >>>
        >>> # Run with uvicorn
        >>> # uvicorn module:app --host 0.0.0.0 --port 8000
    """

    # Default to NoAuth if no auth strategy provided
    if auth is None:
        auth = NoAuth()

    # Define lifespan context manager for server setup/cleanup
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """
        FastAPI lifespan context manager.

        Handles server setup on startup and cleanup on shutdown.
        """
        # Setup (on startup)
        server._setup()
        yield
        # Cleanup (on shutdown)
        server._cleanup()

    # Create FastAPI app with lifespan
    app = FastAPI(
        title=server.name,
        version=server.version,
        lifespan=lifespan
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

    # Health check endpoint
    @app.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "server_name": server.name,
            "server_version": server.version
        }

    # MCP endpoint
    @app.post("/mcp")
    async def mcp_endpoint(request: Request) -> JSONResponse:
        """
        MCP endpoint for JSON-RPC requests.

        Args:
            request: FastAPI request with JSON body

        Returns:
            JSON-RPC response
        """
        # Authenticate request
        try:
            headers = dict(request.headers)
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
            return JSONResponse(content=error_response, status_code=401)

        try:
            # Parse request body as JSON
            request_data = await request.json()

            # Process request with server
            response = server.handle_request(request_data)

            # Return response
            return JSONResponse(content=response, status_code=200)

        except Exception as e:
            # Return error response
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            return JSONResponse(content=error_response, status_code=500)

    return app

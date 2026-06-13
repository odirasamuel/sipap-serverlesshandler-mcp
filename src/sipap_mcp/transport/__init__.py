"""
Transport handlers for MCP servers.

Provides transport adapters for different deployment environments:
- Lambda: AWS Lambda handler function
- HTTP: FastAPI application for ECS Fargate
"""

from sipap_mcp.transport.http_handler import create_http_app
from sipap_mcp.transport.lambda_handler import create_lambda_handler

__all__ = ["create_lambda_handler", "create_http_app"]

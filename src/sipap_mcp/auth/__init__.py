"""
Authentication middleware for MCP servers.

Provides pluggable authentication strategies for securing MCP endpoints.
"""

from sipap_mcp.auth.middleware import (
    APIKeyAuth,
    AuthenticationError,
    AuthStrategy,
    NoAuth,
    SigV4Auth,
)

__all__ = [
    "AuthStrategy",
    "AuthenticationError",
    "NoAuth",
    "APIKeyAuth",
    "SigV4Auth",
]

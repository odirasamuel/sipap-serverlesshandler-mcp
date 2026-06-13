"""
Session management for MCP servers.

Provides Redis-backed session storage with TTL expiration.
"""

from sipap_mcp.session.manager import SessionManager

__all__ = ["SessionManager"]

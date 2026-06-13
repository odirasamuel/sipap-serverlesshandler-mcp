"""
Session management for MCP servers.

Provides Redis-backed session storage with TTL expiration for maintaining
state across multiple JSON-RPC calls.
"""

import json
import uuid
from typing import Any, cast


class SessionManager:
    """
    Redis-backed session manager.

    Manages user sessions with automatic expiration (TTL) for MCP servers.
    Useful for multi-step workflows, user context, and state preservation.
    """

    def __init__(self, redis_client: Any, ttl: int = 3600):
        """
        Initialize session manager.

        Args:
            redis_client: Redis client instance (redis.Redis or compatible)
            ttl: Default session TTL in seconds (default: 3600 = 1 hour)

        Example:
            >>> import redis
            >>> from sipap_mcp.session import SessionManager
            >>>
            >>> redis_client = redis.Redis(host='localhost', port=6379)
            >>> manager = SessionManager(redis_client=redis_client, ttl=1800)
        """
        self.redis_client = redis_client
        self.ttl = ttl

    def create_session(
        self,
        data: dict[str, Any],
        ttl: int | None = None
    ) -> str:
        """
        Create a new session with data.

        Args:
            data: Session data to store (must be JSON-serializable)
            ttl: Optional custom TTL in seconds (uses default if not provided)

        Returns:
            Session ID (UUID string)

        Example:
            >>> session_id = manager.create_session(
            ...     data={"user_id": "123", "context": "sports"},
            ...     ttl=7200
            ... )
            >>> print(session_id)
            'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
        """
        # Generate unique session ID
        session_id = str(uuid.uuid4())

        # Use custom TTL or default
        session_ttl = ttl if ttl is not None else self.ttl

        # Serialize data to JSON
        serialized_data = json.dumps(data)

        # Store in Redis with TTL
        key = self._make_key(session_id)
        self.redis_client.setex(key, session_ttl, serialized_data)

        return session_id

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """
        Retrieve session data by ID.

        Args:
            session_id: Session ID to retrieve

        Returns:
            Session data dict if exists, None otherwise

        Example:
            >>> data = manager.get_session("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
            >>> print(data)
            {'user_id': '123', 'context': 'sports'}
        """
        key = self._make_key(session_id)
        value = self.redis_client.get(key)

        if value is None:
            return None

        # Deserialize JSON
        if isinstance(value, bytes):
            value = value.decode('utf-8')

        return cast(dict[str, Any], json.loads(value))

    def update_session(
        self,
        session_id: str,
        data: dict[str, Any],
        ttl: int | None = None
    ) -> bool:
        """
        Update session data.

        Args:
            session_id: Session ID to update
            data: New session data (replaces existing)
            ttl: Optional custom TTL in seconds (uses default if not provided)

        Returns:
            True if updated successfully

        Example:
            >>> manager.update_session(
            ...     "a1b2c3d4-...",
            ...     data={"user_id": "123", "updated": True}
            ... )
            True
        """
        # Use custom TTL or default
        session_ttl = ttl if ttl is not None else self.ttl

        # Serialize data to JSON
        serialized_data = json.dumps(data)

        # Store in Redis with TTL (overwrite existing)
        key = self._make_key(session_id)
        self.redis_client.setex(key, session_ttl, serialized_data)

        return True

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if session was deleted, False if didn't exist

        Example:
            >>> manager.delete_session("a1b2c3d4-...")
            True
        """
        key = self._make_key(session_id)
        result = self.redis_client.delete(key)

        # Redis delete returns number of keys deleted
        return bool(result > 0)

    def session_exists(self, session_id: str) -> bool:
        """
        Check if session exists.

        Args:
            session_id: Session ID to check

        Returns:
            True if session exists, False otherwise

        Example:
            >>> manager.session_exists("a1b2c3d4-...")
            True
        """
        key = self._make_key(session_id)
        result = self.redis_client.exists(key)

        # Redis exists returns number of keys that exist
        return bool(result > 0)

    def extend_ttl(self, session_id: str, ttl: int) -> bool:
        """
        Extend session TTL.

        Args:
            session_id: Session ID to extend
            ttl: New TTL in seconds

        Returns:
            True if TTL was extended, False if session doesn't exist

        Example:
            >>> # Extend session for another hour
            >>> manager.extend_ttl("a1b2c3d4-...", ttl=3600)
            True
        """
        key = self._make_key(session_id)
        result = self.redis_client.expire(key, ttl)

        # Redis expire returns True if key exists, False otherwise
        return bool(result)

    def _make_key(self, session_id: str) -> str:
        """
        Create Redis key with session prefix.

        Args:
            session_id: Session ID

        Returns:
            Prefixed key (e.g., "session:abc-123")
        """
        return f"session:{session_id}"

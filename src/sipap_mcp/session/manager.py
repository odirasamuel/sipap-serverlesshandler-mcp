"""
Session management for MCP servers with 5-zone architecture.

Provides Redis-backed session storage with deterministic session IDs,
proxy pattern support for memory safety, and 5-zone security isolation.
"""

import json
import uuid
from typing import Any

from sipap_mcp.core.models import SessionInstance
from sipap_mcp.core.zone import (
    SessionCache,
    SessionData,
    SessionEnv,
    SessionIdentity,
    SessionMetadata,
    generate_session_id,
)


class SessionManager:
    """
    Redis-backed session manager with 5-zone architecture.

    Features:
    - Deterministic session IDs (SHA256 of bearer token)
    - 5-zone session architecture for security and memory safety
    - Proxy pattern support for Zone 3 (Data) and Zone 5 (Cache)
    - Backward compatibility with legacy create_session()

    Usage:
        # Create session with deterministic ID
        manager = SessionManager(redis_client=redis.Redis())
        session_id = manager.create_session(
            bearer_token="bearer_abc123",
            owner="user@example.com",
            roles=["analyst"],
            env_vars={"API_KEY": "secret"}
        )

        # Get session (returns SessionInstance)
        session = manager.get_session(session_id)
        print(session.identity.owner)  # "user@example.com"
        session.data["context"] = {"sport": "football"}
    """

    def __init__(self, redis_client: Any, ttl: int = 3600, enable_proxy: bool = False):
        """
        Initialize session manager.

        Args:
            redis_client: Redis client instance (redis.Redis or compatible)
            ttl: Default session TTL in seconds (default: 3600 = 1 hour)
            enable_proxy: Enable proxy mode for Data and Cache zones (default: False)
        """
        self.redis_client = redis_client
        self.ttl = ttl
        self.enable_proxy = enable_proxy

    def create_session(
        self,
        bearer_token: str,
        owner: str,
        roles: list[str] | None = None,
        groups: list[str] | None = None,
        policies: list[str] | None = None,
        env_vars: dict[str, str] | None = None,
        ttl: int | None = None
    ) -> str:
        """
        Create a new session with deterministic session ID.

        Session ID is deterministic: session_id = SHA256(bearer_token)
        This ensures same token always maps to same session across Lambda instances.

        Args:
            bearer_token: Bearer token for deterministic session ID generation
            owner: User identifier (e.g., "user@example.com")
            roles: List of roles (e.g., ["analyst", "viewer"])
            groups: List of groups (e.g., ["sports_team"])
            policies: List of policy names (e.g., ["read_matches"])
            env_vars: Dict of environment variables/secrets
            ttl: Optional custom TTL in seconds (uses default if not provided)

        Returns:
            Deterministic session ID (SHA256 hash of bearer_token)

        Example:
            >>> manager = SessionManager(redis_client)
            >>> session_id = manager.create_session(
            ...     bearer_token="bearer_abc123",
            ...     owner="test_user",
            ...     roles=["analyst"]
            ... )
            >>> len(session_id)
            64  # SHA256 hex hash length
        """
        # Generate deterministic session ID from bearer token
        session_id = generate_session_id(bearer_token)
        token_hash = session_id  # session_id IS the token hash

        # Use custom TTL or default
        session_ttl = ttl if ttl is not None else self.ttl

        # Create SessionInstance with all zones
        session = SessionInstance.create(
            session_id=session_id,
            token_hash=token_hash,
            owner=owner,
            roles=roles,
            groups=groups,
            policies=policies,
            env_vars=env_vars,
            ttl=session_ttl
        )

        # Serialize session to JSON-compatible dict
        session_data = self._serialize_session(session)

        # Store in Redis with TTL
        key = self._make_key(session_id)
        serialized = json.dumps(session_data)
        self.redis_client.setex(key, session_ttl, serialized)

        return session_id

    def get_session(
        self,
        session_id: str,
        enable_proxy: bool | None = None
    ) -> SessionInstance | None:
        """
        Retrieve session by ID (returns SessionInstance).

        Args:
            session_id: Session ID to retrieve
            enable_proxy: Enable proxy mode for Data/Cache zones (uses instance default if None)

        Returns:
            SessionInstance if exists, None otherwise

        Example:
            >>> session = manager.get_session("abc123...")
            >>> print(session.identity.owner)
            'test_user'
            >>> session.data["context"] = {"sport": "football"}
        """
        key = self._make_key(session_id)
        value = self.redis_client.get(key)

        if value is None:
            return None

        # Deserialize JSON
        if isinstance(value, bytes):
            value = value.decode('utf-8')

        session_data = json.loads(value)

        # Deserialize to SessionInstance
        use_proxy = enable_proxy if enable_proxy is not None else self.enable_proxy
        session = self._deserialize_session(session_data, use_proxy)

        return session

    def update_session(
        self,
        session_id: str,
        session: SessionInstance | dict[str, Any],
        ttl: int | None = None
    ) -> bool:
        """
        Update session data.

        Args:
            session_id: Session ID to update
            session: SessionInstance or dict to store
            ttl: Optional custom TTL in seconds (uses default if not provided)

        Returns:
            True if updated successfully

        Example:
            >>> session = manager.get_session("abc123")
            >>> session.data["updated"] = True
            >>> manager.update_session("abc123", session)
            True
        """
        # Use custom TTL or default
        session_ttl = ttl if ttl is not None else self.ttl

        # Serialize session
        if isinstance(session, SessionInstance):
            session_data = self._serialize_session(session)
        else:
            session_data = session

        # Store in Redis with TTL (overwrite existing)
        key = self._make_key(session_id)
        serialized = json.dumps(session_data)
        self.redis_client.setex(key, session_ttl, serialized)

        return True

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if session was deleted, False if didn't exist
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
        """
        key = self._make_key(session_id)
        result = self.redis_client.expire(key, ttl)

        # Redis expire returns True if key exists, False otherwise
        return bool(result)

    # ========================================================================
    # PROXY PATTERN SUPPORT (for memory safety)
    # ========================================================================

    def _load_zone_field_from_storage(
        self,
        session_id: str,
        zone_name: str,
        field_name: str
    ) -> Any:
        """
        Load a single field from a zone (for proxy pattern).

        Used by SessionData and SessionCache in proxy mode to lazily load
        fields from Redis storage on access.

        Args:
            session_id: Session ID
            zone_name: Zone name ("data" or "cache")
            field_name: Field name to load

        Returns:
            Field value

        Raises:
            KeyError: If field not found
        """
        # Redis key for zone fields: session:<session_id>:<zone_name>
        zone_key = f"session:{session_id}:{zone_name}"

        # Get field from Redis hash
        value = self.redis_client.hget(zone_key, field_name)

        if value is None:
            raise KeyError(f"Field '{field_name}' not found in zone '{zone_name}'")

        # Deserialize JSON
        if isinstance(value, bytes):
            value = value.decode('utf-8')

        return json.loads(value)

    def _save_zone_field_to_storage(
        self,
        session_id: str,
        zone_name: str,
        field_name: str,
        value: Any
    ) -> None:
        """
        Save a single field to a zone (for proxy pattern).

        Used by SessionData and SessionCache to persist individual fields
        to Redis storage.

        Args:
            session_id: Session ID
            zone_name: Zone name ("data" or "cache")
            field_name: Field name to save
            value: Field value (must be JSON-serializable)
        """
        # Redis key for zone fields: session:<session_id>:<zone_name>
        zone_key = f"session:{session_id}:{zone_name}"

        # Serialize value to JSON
        serialized = json.dumps(value)

        # Store in Redis hash
        self.redis_client.hset(zone_key, field_name, serialized)

    # ========================================================================
    # BACKWARD COMPATIBILITY (for legacy code)
    # ========================================================================

    def create_session_legacy(
        self,
        data: dict[str, Any],
        ttl: int | None = None
    ) -> str:
        """
        Create session with random UUID (backward compatibility).

        DEPRECATED: Use create_session() with bearer_token for deterministic IDs.

        Args:
            data: Session data to store (must be JSON-serializable)
            ttl: Optional custom TTL in seconds (uses default if not provided)

        Returns:
            Session ID (UUID string)
        """
        # Generate random session ID (legacy behavior)
        session_id = str(uuid.uuid4())

        # Use custom TTL or default
        session_ttl = ttl if ttl is not None else self.ttl

        # Serialize data to JSON
        serialized_data = json.dumps(data)

        # Store in Redis with TTL
        key = self._make_key(session_id)
        self.redis_client.setex(key, session_ttl, serialized_data)

        return session_id

    # ========================================================================
    # INTERNAL HELPERS
    # ========================================================================

    def _make_key(self, session_id: str) -> str:
        """
        Create Redis key with session prefix.

        Args:
            session_id: Session ID

        Returns:
            Prefixed key (e.g., "session:abc123")
        """
        return f"session:{session_id}"

    def _serialize_session(self, session: SessionInstance) -> dict[str, Any]:
        """
        Serialize SessionInstance to JSON-compatible dict.

        Args:
            session: SessionInstance to serialize

        Returns:
            Dict representation of session
        """
        return {
            "identity": {
                "owner": session.identity.owner,
                "roles": session.identity.roles,
                "groups": session.identity.groups,
                "policies": session.identity.policies
            },
            "metadata": {
                "session_id": session.metadata.session_id,
                "token_hash": session.metadata.token_hash,
                "created_at": session.metadata.created_at,
                "last_accessed_at": session.metadata.last_accessed_at,
                "ttl": session.metadata.ttl
            },
            "data": session.data._fields,  # In-memory fields only
            "env": session.env._env,  # Environment variables
            "cache": session.cache._cache  # In-memory cache only
        }

    def _deserialize_session(
        self,
        session_data: dict[str, Any],
        enable_proxy: bool = False
    ) -> SessionInstance:
        """
        Deserialize dict to SessionInstance.

        Args:
            session_data: Dict representation of session
            enable_proxy: Enable proxy mode for Data/Cache zones

        Returns:
            SessionInstance
        """
        # Create zones from data
        identity = SessionIdentity(
            owner=session_data["identity"]["owner"],
            roles=session_data["identity"]["roles"],
            groups=session_data["identity"]["groups"],
            policies=session_data["identity"]["policies"]
        )

        metadata = SessionMetadata(
            session_id=session_data["metadata"]["session_id"],
            token_hash=session_data["metadata"]["token_hash"],
            created_at=session_data["metadata"]["created_at"],
            last_accessed_at=session_data["metadata"]["last_accessed_at"],
            ttl=session_data["metadata"]["ttl"]
        )

        # Data zone (proxy or in-memory)
        if enable_proxy:
            data = SessionData.create_proxy(self, session_data["metadata"]["session_id"])
        else:
            data = SessionData()
            data._fields = session_data.get("data", {})

        env = SessionEnv.from_dict(session_data.get("env", {}))

        # Cache zone (proxy or in-memory)
        if enable_proxy:
            cache = SessionCache.create_proxy(self, session_data["metadata"]["session_id"])
        else:
            cache = SessionCache()
            cache._cache = session_data.get("cache", {})

        return SessionInstance(
            identity=identity,
            metadata=metadata,
            data=data,
            env=env,
            cache=cache
        )

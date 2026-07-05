"""
Session Zone Models for SIPAP MCP.

5-Zone Session Architecture for memory-safe, security-isolated session
management in serverless environments (AWS Lambda, ECS Fargate).

Zone Architecture:
    1. SessionIdentity  - Immutable authorization (owner, roles, groups, policies)
    2. SessionMetadata  - Mutable session management (timestamps, TTL)
    3. SessionData      - Mutable app data with proxy pattern (lazy loading)
    4. SessionEnv       - Immutable secrets with masked repr (API keys, credentials)
    5. SessionCache     - Mutable TTL cache with proxy pattern (lazy loading)

Memory Safety:
    - Zones 1, 2, 4 loaded eagerly (small data)
    - Zones 3, 5 support proxy pattern (large data, lazy loading)
    - 128MB Lambda can handle 10,000+ sessions with proxy mode

Security:
    - Zones 1 & 4 immutable (frozen dataclasses) prevent privilege escalation
    - Zone 4 secrets masked in logs (__repr__ redaction)
    - Deterministic session IDs (SHA256 of bearer token)
"""

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

# ============================================================================
# SESSION ZONE BASE CLASS
# ============================================================================


class SessionZone(ABC):
    """
    Abstract base class for all session zones.

    Provides dict-like interface for accessing zone fields:
    - zone["field"]          # Get field value
    - zone["field"] = value  # Set field value (if mutable)
    - "field" in zone        # Check field existence
    - len(zone)              # Count fields

    All zone implementations must provide __getitem__ and __setitem__.
    """

    @abstractmethod
    def __getitem__(self, key: str) -> Any:
        """
        Get a field value from this zone (dict-like access).

        Args:
            key: Name of the field to retrieve

        Returns:
            Field value

        Raises:
            KeyError: If field not found
        """
        pass

    @abstractmethod
    def __setitem__(self, key: str, value: Any) -> None:
        """
        Set a field value in this zone (dict-like access).

        Args:
            key: Name of the field to set
            value: Value to set

        Raises:
            AttributeError: If zone is immutable
        """
        pass

    def __contains__(self, key: str) -> bool:
        """Check if field exists in zone."""
        try:
            self[key]
            return True
        except (KeyError, AttributeError):
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get field with default value if not found."""
        try:
            return self[key]
        except (KeyError, AttributeError):
            return default


# ============================================================================
# ZONE 1: SESSION IDENTITY (Immutable Authorization)
# ============================================================================


@dataclass(frozen=True)
class SessionIdentity(SessionZone):
    """
    Zone 1: Immutable identity and authorization data.

    Security:
    - Frozen dataclass prevents privilege escalation
    - Cannot modify owner, roles, groups after session creation
    - Authorization decisions based on immutable data

    Fields:
    - owner: User identifier (e.g., "user@example.com")
    - roles: List of roles (e.g., ["analyst", "viewer"])
    - groups: List of groups (e.g., ["sports_team", "premium"])
    - policies: List of policy names (e.g., ["read_matches", "read_odds"])
    """

    owner: str
    roles: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    policies: list[str] = field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        """Get field by name (dict-like access)."""
        if not hasattr(self, key):
            raise KeyError(f"Field '{key}' not found in SessionIdentity")
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Raise error - SessionIdentity is immutable."""
        raise AttributeError("SessionIdentity is immutable (frozen dataclass)")


# ============================================================================
# ZONE 2: SESSION METADATA (Mutable Management)
# ============================================================================


@dataclass
class SessionMetadata(SessionZone):
    """
    Zone 2: Mutable session lifecycle management.

    Fields:
    - session_id: Deterministic session ID (SHA256 of bearer token)
    - token_hash: Hash of bearer token for validation
    - created_at: ISO 8601 UTC timestamp of session creation
    - last_accessed_at: ISO 8601 UTC timestamp of last access
    - ttl: Session TTL in seconds (default: 3600 = 1 hour)
    """

    session_id: str
    token_hash: str
    created_at: str
    last_accessed_at: str
    ttl: int = 3600

    def __getitem__(self, key: str) -> Any:
        """Get field by name (dict-like access)."""
        if not hasattr(self, key):
            raise KeyError(f"Field '{key}' not found in SessionMetadata")
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Set field by name (dict-like access)."""
        if not hasattr(self, key):
            raise KeyError(f"Field '{key}' not found in SessionMetadata")
        setattr(self, key, value)


# ============================================================================
# ZONE 3: SESSION DATA (Mutable Proxy for Large Data)
# ============================================================================


@dataclass
class SessionData(SessionZone):
    """
    Zone 3: Mutable application data with proxy pattern support.

    Memory Safety:
    - In-memory mode: All data stored in _fields dict
    - Proxy mode: Data loaded lazily from storage on access
    - Proxy mode prevents Lambda OOM with large datasets

    Usage:
        # In-memory mode
        data = SessionData()
        data["user_context"] = {"sport": "football"}

        # Proxy mode (lazy loading)
        data = SessionData.create_proxy(handler, session_id)
        value = data["large_dataset"]  # Loads from Redis on access
    """

    _fields: dict[str, Any] = field(default_factory=dict, repr=False)
    _session_handler: Any = field(default=None, repr=False)
    _session_id: str | None = field(default=None, repr=False)
    _is_proxy: bool = field(default=False, repr=False)

    def __getitem__(self, key: str) -> Any:
        """
        Get field value (with lazy loading in proxy mode).

        Proxy Mode:
        - Delegates to handler._load_zone_field_from_storage()
        - Loads field from Redis/DynamoDB on first access
        - Subsequent accesses may hit local cache (handler decides)

        In-Memory Mode:
        - Returns value from _fields dict directly
        """
        if self._is_proxy and self._session_handler:
            # Proxy mode - lazy load from storage
            return self._session_handler._load_zone_field_from_storage(
                self._session_id, "data", key
            )
        else:
            # In-memory mode
            if key not in self._fields:
                raise KeyError(f"Field '{key}' not found in SessionData")
            return self._fields[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set field value (always updates _fields dict)."""
        self._fields[key] = value

    def keys(self) -> Iterator[str]:
        """Return iterator of field names."""
        return iter(self._fields.keys())

    def values(self) -> Iterator[Any]:
        """Return iterator of field values."""
        return iter(self._fields.values())

    def items(self) -> Iterator[tuple[str, Any]]:
        """Return iterator of (key, value) pairs."""
        return iter(self._fields.items())

    def __len__(self) -> int:
        """Return number of fields."""
        return len(self._fields)

    @classmethod
    def create_proxy(
        cls,
        session_handler: Any,
        session_id: str
    ) -> "SessionData":
        """
        Create SessionData in proxy mode (lazy loading).

        Args:
            session_handler: Handler with _load_zone_field_from_storage() method
            session_id: Session ID for storage lookups

        Returns:
            SessionData instance in proxy mode
        """
        return cls(
            _session_handler=session_handler,
            _session_id=session_id,
            _is_proxy=True
        )


# ============================================================================
# ZONE 4: SESSION ENV (Immutable Secrets with Masked Repr)
# ============================================================================


@dataclass(frozen=True)
class SessionEnv(SessionZone):
    """
    Zone 4: Immutable environment variables and secrets.

    Security:
    - Frozen dataclass prevents secret modification
    - __repr__ masks secret values in logs
    - Secrets never exposed in error messages or logs

    Fields stored in _env dict:
    - API keys (e.g., "API_KEY": "sk_prod_...")
    - Database credentials (e.g., "DB_PASSWORD": "...")
    - Third-party tokens (e.g., "STRIPE_KEY": "...")
    """

    _env: dict[str, str] = field(default_factory=dict, repr=False)

    def __getitem__(self, key: str) -> str:
        """Get environment variable value."""
        if key not in self._env:
            raise KeyError(f"Environment variable '{key}' not found")
        return self._env[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Raise error - SessionEnv is immutable."""
        raise AttributeError("SessionEnv is immutable (frozen dataclass)")

    def __repr__(self) -> str:
        """
        Masked repr for security (secrets not exposed in logs).

        Example:
            SessionEnv(API_KEY='sk_p***', DB_PASSWORD='***')
        """
        masked_items = []
        for key, value in self._env.items():
            masked_value = f"{value[:4]}***" if len(value) > 5 else "***"
            masked_items.append(f"{key}='{masked_value}'")

        return f"SessionEnv({', '.join(masked_items)})"

    @classmethod
    def from_dict(cls, env_vars: dict[str, str]) -> "SessionEnv":
        """
        Create SessionEnv from dict of environment variables.

        Args:
            env_vars: Dict of environment variables

        Returns:
            SessionEnv instance
        """
        return cls(_env=env_vars.copy())


# ============================================================================
# ZONE 5: SESSION CACHE (Mutable Proxy for TTL Cache)
# ============================================================================


@dataclass
class SessionCache(SessionZone):
    """
    Zone 5: Mutable TTL-based ephemeral cache with proxy pattern support.

    Memory Safety:
    - In-memory mode: Cache data stored in _cache dict
    - Proxy mode: Cache loaded lazily from Redis on access
    - TTL expiration handled by storage backend (Redis EXPIRE)

    Usage:
        # In-memory mode
        cache = SessionCache()
        cache["query_results"] = {"matches": [...]}

        # Proxy mode (lazy loading)
        cache = SessionCache.create_proxy(handler, session_id)
        value = cache["large_results"]  # Loads from Redis on access
    """

    _cache: dict[str, Any] = field(default_factory=dict, repr=False)
    _session_handler: Any = field(default=None, repr=False)
    _session_id: str | None = field(default=None, repr=False)
    _is_proxy: bool = field(default=False, repr=False)

    def __getitem__(self, key: str) -> Any:
        """
        Get cached value (with lazy loading in proxy mode).

        Proxy Mode:
        - Delegates to handler._load_zone_field_from_storage()
        - Loads field from Redis on first access
        - Redis TTL handles cache expiration

        In-Memory Mode:
        - Returns value from _cache dict directly
        """
        if self._is_proxy and self._session_handler:
            # Proxy mode - lazy load from storage
            return self._session_handler._load_zone_field_from_storage(
                self._session_id, "cache", key
            )
        else:
            # In-memory mode
            if key not in self._cache:
                raise KeyError(f"Cache key '{key}' not found")
            return self._cache[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set cached value (always updates _cache dict)."""
        self._cache[key] = value

    def __delitem__(self, key: str) -> None:
        """Delete cached value."""
        if key in self._cache:
            del self._cache[key]
        else:
            raise KeyError(f"Cache key '{key}' not found")

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()

    def __len__(self) -> int:
        """Return number of cached items."""
        return len(self._cache)

    @classmethod
    def create_proxy(
        cls,
        session_handler: Any,
        session_id: str
    ) -> "SessionCache":
        """
        Create SessionCache in proxy mode (lazy loading).

        Args:
            session_handler: Handler with _load_zone_field_from_storage() method
            session_id: Session ID for storage lookups

        Returns:
            SessionCache instance in proxy mode
        """
        return cls(
            _session_handler=session_handler,
            _session_id=session_id,
            _is_proxy=True
        )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def generate_session_id(bearer_token: str) -> str:
    """
    Generate deterministic session ID from bearer token.

    Implementation:
    - session_id = SHA256(bearer_token)
    - Same token always generates same session ID
    - Enables session reuse across Lambda instances
    - Prevents session enumeration attacks

    Args:
        bearer_token: Bearer token string

    Returns:
        Hex-encoded SHA256 hash (64 characters)

    Example:
        >>> token = "bearer_abc123"
        >>> session_id = generate_session_id(token)
        >>> len(session_id)
        64
        >>> session_id == generate_session_id(token)  # Deterministic
        True
    """
    return hashlib.sha256(bearer_token.encode()).hexdigest()

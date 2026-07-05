"""
Session Models for SIPAP MCP.

Provides unified session model that integrates all 5 zones into a single,
type-safe session object.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sipap_mcp.core.zone import (
    SessionCache,
    SessionData,
    SessionEnv,
    SessionIdentity,
    SessionMetadata,
)


@dataclass
class SessionInstance:
    """
    Unified session instance with 5-zone architecture.

    Zones:
        1. identity: SessionIdentity - Immutable authorization
        2. metadata: SessionMetadata - Mutable session management
        3. data: SessionData - Mutable app data (proxy-enabled)
        4. env: SessionEnv - Immutable secrets (masked repr)
        5. cache: SessionCache - Mutable TTL cache (proxy-enabled)

    Usage:
        # Create session from factory
        session = SessionInstance.create(
            session_id="abc123",
            token_hash="def456",
            owner="user@example.com",
            roles=["analyst"],
            env_vars={"API_KEY": "secret"}
        )

        # Access zones
        print(session.identity.owner)  # "user@example.com"
        session.data["context"] = {"sport": "football"}
        session.cache["results"] = [...]

        # Backward compatibility properties
        print(session.owner)  # Same as session.identity.owner
        print(session.session_id)  # Same as session.metadata.session_id
    """

    identity: SessionIdentity
    metadata: SessionMetadata
    data: SessionData
    env: SessionEnv
    cache: SessionCache

    # ========================================================================
    # BACKWARD COMPATIBILITY PROPERTIES
    # ========================================================================

    @property
    def owner(self) -> str:
        """Backward compatibility: session.owner → session.identity.owner"""
        return self.identity.owner

    @property
    def roles(self) -> list[str]:
        """Backward compatibility: session.roles → session.identity.roles"""
        return self.identity.roles

    @property
    def groups(self) -> list[str]:
        """Backward compatibility: session.groups → session.identity.groups"""
        return self.identity.groups

    @property
    def policies(self) -> list[str]:
        """Backward compatibility: session.policies → session.identity.policies"""
        return self.identity.policies

    @property
    def session_id(self) -> str:
        """Backward compatibility: session.session_id → session.metadata.session_id"""
        return self.metadata.session_id

    @property
    def token_hash(self) -> str:
        """Backward compatibility: session.token_hash → session.metadata.token_hash"""
        return self.metadata.token_hash

    @property
    def created_at(self) -> str:
        """Backward compatibility: session.created_at → session.metadata.created_at"""
        return self.metadata.created_at

    @property
    def last_accessed_at(self) -> str:
        """Backward compatibility: session.last_accessed_at → session.metadata.last_accessed_at"""
        return self.metadata.last_accessed_at

    @property
    def ttl(self) -> int:
        """Backward compatibility: session.ttl → session.metadata.ttl"""
        return self.metadata.ttl

    # ========================================================================
    # FACTORY METHOD
    # ========================================================================

    @classmethod
    def create(
        cls,
        session_id: str,
        token_hash: str,
        owner: str,
        roles: list[str] | None = None,
        groups: list[str] | None = None,
        policies: list[str] | None = None,
        env_vars: dict[str, str] | None = None,
        ttl: int = 3600,
    ) -> "SessionInstance":
        """
        Factory method to create SessionInstance with all zones.

        Args:
            session_id: Deterministic session ID (SHA256 of bearer token)
            token_hash: Hash of bearer token for validation
            owner: User identifier (e.g., "user@example.com")
            roles: List of roles (e.g., ["analyst", "viewer"])
            groups: List of groups (e.g., ["sports_team"])
            policies: List of policy names (e.g., ["read_matches"])
            env_vars: Dict of environment variables/secrets
            ttl: Session TTL in seconds (default: 3600 = 1 hour)

        Returns:
            SessionInstance with all zones initialized

        Example:
            >>> session = SessionInstance.create(
            ...     session_id="abc123",
            ...     token_hash="def456",
            ...     owner="test_user",
            ...     roles=["analyst"],
            ...     env_vars={"API_KEY": "secret123"}
            ... )
            >>> session.owner
            'test_user'
        """
        # Get current time
        created_at = datetime.now(UTC).isoformat()

        # Create Zone 1: Identity (immutable authorization)
        identity = SessionIdentity(
            owner=owner,
            roles=roles or [],
            groups=groups or [],
            policies=policies or []
        )

        # Create Zone 2: Metadata (mutable session management)
        metadata = SessionMetadata(
            session_id=session_id,
            token_hash=token_hash,
            created_at=created_at,
            last_accessed_at=created_at,
            ttl=ttl
        )

        # Create Zone 3: Data (mutable app data, in-memory mode by default)
        data = SessionData()

        # Create Zone 4: Env (immutable secrets)
        env = SessionEnv.from_dict(env_vars or {})

        # Create Zone 5: Cache (mutable TTL cache, in-memory mode by default)
        cache = SessionCache()

        return cls(
            identity=identity,
            metadata=metadata,
            data=data,
            env=env,
            cache=cache
        )

"""
Tests for 5-zone session architecture.

Tests the core zone classes that provide memory-safe, security-isolated
session management for serverless MCP deployments.

Test Coverage:
- SessionZone ABC contract
- SessionIdentity (Zone 1 - immutable authorization)
- SessionMetadata (Zone 2 - mutable management)
- SessionData (Zone 3 - mutable proxy for large data)
- SessionEnv (Zone 4 - immutable secrets)
- SessionCache (Zone 5 - mutable proxy for TTL cache)
"""

import hashlib
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest


class TestSessionIdentity:
    """Test SessionIdentity (Zone 1) - Immutable authorization data."""

    def test_create_session_identity(self):
        """Test SessionIdentity creation with required fields."""
        from sipap_mcp.core.zone import SessionIdentity

        identity = SessionIdentity(
            owner="test_user",
            roles=["analyst", "viewer"],
            groups=["sports_team"],
            policies=["read_matches", "read_odds"]
        )

        assert identity.owner == "test_user"
        assert identity.roles == ["analyst", "viewer"]
        assert identity.groups == ["sports_team"]
        assert identity.policies == ["read_matches", "read_odds"]

    def test_session_identity_immutable(self):
        """Test SessionIdentity is immutable (frozen dataclass)."""
        from sipap_mcp.core.zone import SessionIdentity

        identity = SessionIdentity(
            owner="test_user",
            roles=["analyst"],
            groups=[],
            policies=[]
        )

        # Should raise AttributeError when trying to modify
        with pytest.raises(AttributeError):
            identity.owner = "hacker"

        with pytest.raises(AttributeError):
            identity.roles = ["admin"]

    def test_session_identity_dict_like_access(self):
        """Test SessionIdentity supports dict-like access."""
        from sipap_mcp.core.zone import SessionIdentity

        identity = SessionIdentity(
            owner="test_user",
            roles=["analyst"],
            groups=["team_a"],
            policies=["read"]
        )

        # Dict-like read access
        assert identity["owner"] == "test_user"
        assert identity["roles"] == ["analyst"]
        assert identity["groups"] == ["team_a"]

    def test_session_identity_dict_like_write_raises_error(self):
        """Test SessionIdentity __setitem__ raises error (immutable)."""
        from sipap_mcp.core.zone import SessionIdentity

        identity = SessionIdentity(
            owner="test_user",
            roles=["analyst"],
            groups=[],
            policies=[]
        )

        # Should raise AttributeError (immutable zone)
        with pytest.raises(AttributeError):
            identity["owner"] = "hacker"


class TestSessionMetadata:
    """Test SessionMetadata (Zone 2) - Mutable session management."""

    def test_create_session_metadata(self):
        """Test SessionMetadata creation with required fields."""
        from sipap_mcp.core.zone import SessionMetadata

        created_at = datetime.now(UTC).isoformat()
        metadata = SessionMetadata(
            session_id="abc123",
            token_hash="def456",
            created_at=created_at,
            last_accessed_at=created_at,
            ttl=3600
        )

        assert metadata.session_id == "abc123"
        assert metadata.token_hash == "def456"
        assert metadata.created_at == created_at
        assert metadata.ttl == 3600

    def test_session_metadata_mutable(self):
        """Test SessionMetadata is mutable."""
        from sipap_mcp.core.zone import SessionMetadata

        created_at = datetime.now(UTC).isoformat()
        metadata = SessionMetadata(
            session_id="abc123",
            token_hash="def456",
            created_at=created_at,
            last_accessed_at=created_at,
            ttl=3600
        )

        # Should allow modification
        new_time = datetime.now(UTC).isoformat()
        metadata.last_accessed_at = new_time
        assert metadata.last_accessed_at == new_time

        metadata.ttl = 7200
        assert metadata.ttl == 7200

    def test_session_metadata_dict_like_access(self):
        """Test SessionMetadata supports dict-like access."""
        from sipap_mcp.core.zone import SessionMetadata

        created_at = datetime.now(UTC).isoformat()
        metadata = SessionMetadata(
            session_id="abc123",
            token_hash="def456",
            created_at=created_at,
            last_accessed_at=created_at,
            ttl=3600
        )

        # Dict-like read
        assert metadata["session_id"] == "abc123"
        assert metadata["ttl"] == 3600

        # Dict-like write (mutable)
        metadata["ttl"] = 7200
        assert metadata["ttl"] == 7200


class TestSessionData:
    """Test SessionData (Zone 3) - Mutable proxy for large app data."""

    def test_create_session_data_in_memory(self):
        """Test SessionData creation with in-memory fields."""
        from sipap_mcp.core.zone import SessionData

        data = SessionData()
        data["user_context"] = {"sport": "football", "league": "premier_league"}
        data["last_query"] = "matches_today"

        assert data["user_context"] == {"sport": "football", "league": "premier_league"}
        assert data["last_query"] == "matches_today"

    def test_session_data_proxy_mode(self):
        """Test SessionData proxy mode (lazy loading from storage)."""
        from sipap_mcp.core.zone import SessionData

        # Mock session handler
        mock_handler = Mock()
        mock_handler._load_zone_field_from_storage = Mock(
            return_value={"large_data": "from_redis"}
        )

        # Create proxy
        data = SessionData.create_proxy(
            session_handler=mock_handler,
            session_id="test_session"
        )

        # Access field - should trigger lazy load
        data["query_results"]

        # Verify lazy load was called
        mock_handler._load_zone_field_from_storage.assert_called_once_with(
            "test_session", "data", "query_results"
        )

    def test_session_data_get_nonexistent_key(self):
        """Test SessionData raises KeyError for nonexistent key."""
        from sipap_mcp.core.zone import SessionData

        data = SessionData()

        with pytest.raises(KeyError):
            _ = data["nonexistent_key"]

    def test_session_data_keys_values_items(self):
        """Test SessionData supports keys(), values(), items()."""
        from sipap_mcp.core.zone import SessionData

        data = SessionData()
        data["field1"] = "value1"
        data["field2"] = "value2"

        assert "field1" in data
        assert "value1" in data.values()
        assert ("field1", "value1") in data.items()


class TestSessionEnv:
    """Test SessionEnv (Zone 4) - Immutable secrets with masked repr."""

    def test_create_session_env(self):
        """Test SessionEnv creation with environment variables."""
        from sipap_mcp.core.zone import SessionEnv

        env = SessionEnv.from_dict({
            "API_KEY": "sk_prod_abc123def456",
            "DATABASE_URL": "postgresql://user:pass@host/db",
            "DEBUG": "false"
        })

        assert env["API_KEY"] == "sk_prod_abc123def456"
        assert env["DATABASE_URL"] == "postgresql://user:pass@host/db"
        assert env["DEBUG"] == "false"

    def test_session_env_immutable(self):
        """Test SessionEnv is immutable (frozen dataclass)."""
        from sipap_mcp.core.zone import SessionEnv

        env = SessionEnv.from_dict({"API_KEY": "secret123"})

        # Should raise AttributeError when trying to modify
        with pytest.raises(AttributeError):
            env["API_KEY"] = "new_secret"

    def test_session_env_repr_masks_secrets(self):
        """Test SessionEnv __repr__ masks secret values."""
        from sipap_mcp.core.zone import SessionEnv

        env = SessionEnv.from_dict({
            "API_KEY": "sk_prod_abc123def456",
            "PASSWORD": "supersecret",
            "DEBUG": "true"
        })

        repr_str = repr(env)

        # Secrets should be masked
        assert "sk_prod_abc123def456" not in repr_str
        assert "supersecret" not in repr_str

        # Should show masked format
        assert "***" in repr_str or "sk_p***" in repr_str

    def test_session_env_get_with_default(self):
        """Test SessionEnv.get() with default value."""
        from sipap_mcp.core.zone import SessionEnv

        env = SessionEnv.from_dict({"API_KEY": "secret"})

        # Existing key
        assert env.get("API_KEY") == "secret"

        # Non-existent key with default
        assert env.get("MISSING_KEY", "default_value") == "default_value"

        # Non-existent key without default
        assert env.get("MISSING_KEY") is None


class TestSessionCache:
    """Test SessionCache (Zone 5) - Mutable proxy for TTL-based cache."""

    def test_create_session_cache_in_memory(self):
        """Test SessionCache creation with in-memory fields."""
        from sipap_mcp.core.zone import SessionCache

        cache = SessionCache()
        cache["query_results"] = [{"match_id": "123", "team": "Arsenal"}]
        cache["odds_data"] = {"bookmaker": "Bet365", "odds": 1.5}

        assert cache["query_results"] == [{"match_id": "123", "team": "Arsenal"}]
        assert cache["odds_data"] == {"bookmaker": "Bet365", "odds": 1.5}

    def test_session_cache_proxy_mode(self):
        """Test SessionCache proxy mode (lazy loading from storage)."""
        from sipap_mcp.core.zone import SessionCache

        # Mock session handler
        mock_handler = Mock()
        mock_handler._load_zone_field_from_storage = Mock(
            return_value={"cached": "data"}
        )

        # Create proxy
        cache = SessionCache.create_proxy(
            session_handler=mock_handler,
            session_id="test_session"
        )

        # Access field - should trigger lazy load
        cache["large_cached_data"]

        # Verify lazy load was called
        mock_handler._load_zone_field_from_storage.assert_called_once_with(
            "test_session", "cache", "large_cached_data"
        )

    def test_session_cache_deletion(self):
        """Test SessionCache supports field deletion."""
        from sipap_mcp.core.zone import SessionCache

        cache = SessionCache()
        cache["field1"] = "value1"
        cache["field2"] = "value2"

        assert "field1" in cache

        # Delete field
        del cache["field1"]

        assert "field1" not in cache
        assert "field2" in cache

    def test_session_cache_clear(self):
        """Test SessionCache.clear() removes all fields."""
        from sipap_mcp.core.zone import SessionCache

        cache = SessionCache()
        cache["field1"] = "value1"
        cache["field2"] = "value2"

        assert len(cache) == 2

        # Clear all
        cache.clear()

        assert len(cache) == 0


class TestDeterministicSessionID:
    """Test deterministic session ID generation (SHA256 of bearer token)."""

    def test_generate_session_id_from_token(self):
        """Test session_id = SHA256(bearer_token)."""
        from sipap_mcp.core.zone import generate_session_id

        token = "bearer_token_abc123"
        session_id = generate_session_id(token)

        # Should be SHA256 hash
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert session_id == expected

    def test_same_token_same_session_id(self):
        """Test same token always generates same session ID."""
        from sipap_mcp.core.zone import generate_session_id

        token = "bearer_token_xyz789"

        session_id_1 = generate_session_id(token)
        session_id_2 = generate_session_id(token)

        assert session_id_1 == session_id_2

    def test_different_tokens_different_session_ids(self):
        """Test different tokens generate different session IDs."""
        from sipap_mcp.core.zone import generate_session_id

        token_1 = "bearer_token_1"
        token_2 = "bearer_token_2"

        session_id_1 = generate_session_id(token_1)
        session_id_2 = generate_session_id(token_2)

        assert session_id_1 != session_id_2

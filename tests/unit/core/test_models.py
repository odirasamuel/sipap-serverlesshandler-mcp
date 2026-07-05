"""
Tests for SessionInstance model.

Tests the unified session model that integrates all 5 zones into
a single, type-safe session object.
"""

from datetime import UTC, datetime

import pytest


class TestSessionInstance:
    """Test SessionInstance model with 5-zone architecture."""

    def test_create_session_instance(self):
        """Test SessionInstance creation with all zones."""
        from sipap_mcp.core.models import SessionInstance
        from sipap_mcp.core.zone import (
            SessionCache,
            SessionData,
            SessionEnv,
            SessionIdentity,
            SessionMetadata,
        )

        created_at = datetime.now(UTC).isoformat()

        # Create zones
        identity = SessionIdentity(
            owner="test_user",
            roles=["analyst"],
            groups=["team_a"],
            policies=["read_matches"]
        )
        metadata = SessionMetadata(
            session_id="abc123",
            token_hash="def456",
            created_at=created_at,
            last_accessed_at=created_at,
            ttl=3600
        )
        data = SessionData()
        env = SessionEnv.from_dict({"API_KEY": "secret123"})
        cache = SessionCache()

        # Create session instance
        session = SessionInstance(
            identity=identity,
            metadata=metadata,
            data=data,
            env=env,
            cache=cache
        )

        assert session.identity.owner == "test_user"
        assert session.metadata.session_id == "abc123"
        assert session.env["API_KEY"] == "secret123"

    def test_session_instance_create_factory(self):
        """Test SessionInstance.create() factory method."""
        from sipap_mcp.core.models import SessionInstance

        session = SessionInstance.create(
            session_id="test_session",
            token_hash="token_hash_123",
            owner="test_user",
            roles=["analyst", "viewer"],
            groups=["sports_team"],
            policies=["read_matches"],
            env_vars={"API_KEY": "secret123", "DB_URL": "postgresql://..."}
        )

        # Verify all zones created
        assert session.identity.owner == "test_user"
        assert session.identity.roles == ["analyst", "viewer"]
        assert session.metadata.session_id == "test_session"
        assert session.metadata.token_hash == "token_hash_123"
        assert session.env["API_KEY"] == "secret123"
        assert len(session.data) == 0  # Empty by default
        assert len(session.cache) == 0  # Empty by default

    def test_session_instance_backward_compatibility_properties(self):
        """Test backward compatibility properties (session.owner, session.session_id)."""
        from sipap_mcp.core.models import SessionInstance

        session = SessionInstance.create(
            session_id="abc123",
            token_hash="def456",
            owner="test_user",
            roles=["analyst"]
        )

        # Backward compatibility properties
        assert session.owner == "test_user"
        assert session.session_id == "abc123"
        assert session.token_hash == "def456"
        assert session.roles == ["analyst"]

    def test_session_instance_with_proxy_zones(self):
        """Test SessionInstance with proxy zones for Data and Cache."""
        from unittest.mock import Mock

        from sipap_mcp.core.models import SessionInstance
        from sipap_mcp.core.zone import SessionCache, SessionData

        # Mock session handler
        mock_handler = Mock()

        # Create session with proxy zones
        session = SessionInstance.create(
            session_id="test_session",
            token_hash="token_hash",
            owner="test_user",
            roles=[]
        )

        # Replace data and cache with proxy versions
        session.data = SessionData.create_proxy(mock_handler, "test_session")
        session.cache = SessionCache.create_proxy(mock_handler, "test_session")

        # Verify zones are in proxy mode
        assert session.data._is_proxy is True
        assert session.cache._is_proxy is True

    def test_session_instance_immutable_zones(self):
        """Test that immutable zones (Identity, Env) cannot be modified."""
        from sipap_mcp.core.models import SessionInstance

        session = SessionInstance.create(
            session_id="test_session",
            token_hash="token_hash",
            owner="test_user",
            roles=["analyst"],
            env_vars={"API_KEY": "secret"}
        )

        # Identity is immutable
        with pytest.raises(AttributeError):
            session.identity.owner = "hacker"

        # Env is immutable
        with pytest.raises(AttributeError):
            session.env["API_KEY"] = "new_secret"

    def test_session_instance_mutable_zones(self):
        """Test that mutable zones (Metadata, Data, Cache) can be modified."""
        from sipap_mcp.core.models import SessionInstance

        session = SessionInstance.create(
            session_id="test_session",
            token_hash="token_hash",
            owner="test_user",
            roles=[]
        )

        # Metadata is mutable
        new_time = datetime.now(UTC).isoformat()
        session.metadata.last_accessed_at = new_time
        assert session.metadata.last_accessed_at == new_time

        # Data is mutable
        session.data["user_context"] = {"sport": "football"}
        assert session.data["user_context"]["sport"] == "football"

        # Cache is mutable
        session.cache["query_results"] = [{"match_id": "123"}]
        assert len(session.cache["query_results"]) == 1

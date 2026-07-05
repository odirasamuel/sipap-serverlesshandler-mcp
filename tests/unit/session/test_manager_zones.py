"""
Tests for SessionManager with 5-zone architecture integration.

Tests that SessionManager properly creates and manages sessions using
the 5-zone architecture with deterministic session IDs.
"""

import hashlib
from datetime import UTC, datetime
from unittest.mock import Mock


class TestSessionManagerDeterministicIDs:
    """Test deterministic session ID generation in SessionManager."""

    def test_create_session_with_deterministic_id(self):
        """Test session ID is deterministic (SHA256 of bearer token)."""
        from sipap_mcp.session.manager import SessionManager

        mock_redis = Mock()
        manager = SessionManager(redis_client=mock_redis)

        bearer_token = "bearer_token_abc123"
        session_id = manager.create_session(
            bearer_token=bearer_token,
            owner="test_user",
            roles=["analyst"]
        )

        # Verify session_id is SHA256 hash of token
        expected_id = hashlib.sha256(bearer_token.encode()).hexdigest()
        assert session_id == expected_id

    def test_same_token_same_session_id(self):
        """Test same bearer token always generates same session ID."""
        from sipap_mcp.session.manager import SessionManager

        mock_redis = Mock()
        manager = SessionManager(redis_client=mock_redis)

        bearer_token = "bearer_token_xyz789"

        session_id_1 = manager.create_session(
            bearer_token=bearer_token,
            owner="user1",
            roles=[]
        )
        session_id_2 = manager.create_session(
            bearer_token=bearer_token,
            owner="user2",
            roles=[]
        )

        assert session_id_1 == session_id_2

    def test_different_tokens_different_session_ids(self):
        """Test different bearer tokens generate different session IDs."""
        from sipap_mcp.session.manager import SessionManager

        mock_redis = Mock()
        manager = SessionManager(redis_client=mock_redis)

        session_id_1 = manager.create_session(
            bearer_token="token_1",
            owner="user1",
            roles=[]
        )
        session_id_2 = manager.create_session(
            bearer_token="token_2",
            owner="user2",
            roles=[]
        )

        assert session_id_1 != session_id_2


class TestSessionManagerZoneStorage:
    """Test SessionManager stores sessions with 5-zone architecture."""

    def test_create_session_stores_all_zones(self):
        """Test creating session stores all 5 zones in Redis."""
        from sipap_mcp.session.manager import SessionManager

        mock_redis = Mock()
        manager = SessionManager(redis_client=mock_redis)

        manager.create_session(
            bearer_token="test_token",
            owner="test_user",
            roles=["analyst", "viewer"],
            groups=["team_a"],
            policies=["read_matches"],
            env_vars={"API_KEY": "secret123"},
            ttl=7200
        )

        # Verify Redis was called to store session
        assert mock_redis.hset.called or mock_redis.setex.called

    def test_get_session_returns_session_instance(self):
        """Test getting session returns SessionInstance with all zones."""
        import json

        from sipap_mcp.core.models import SessionInstance
        from sipap_mcp.session.manager import SessionManager

        mock_redis = Mock()

        # Mock Redis to return serialized session data
        session_data = {
            "identity": {
                "owner": "test_user",
                "roles": ["analyst"],
                "groups": ["team_a"],
                "policies": ["read_matches"]
            },
            "metadata": {
                "session_id": "abc123",
                "token_hash": "def456",
                "created_at": datetime.now(UTC).isoformat(),
                "last_accessed_at": datetime.now(UTC).isoformat(),
                "ttl": 3600
            },
            "env": {
                "API_KEY": "secret123"
            }
        }
        mock_redis.get.return_value = json.dumps(session_data).encode()

        manager = SessionManager(redis_client=mock_redis)
        session = manager.get_session("abc123")

        # Verify SessionInstance returned
        assert isinstance(session, SessionInstance)
        assert session.identity.owner == "test_user"
        assert session.metadata.session_id == "abc123"
        assert session.env["API_KEY"] == "secret123"

    def test_get_session_nonexistent_returns_none(self):
        """Test getting nonexistent session returns None."""
        from sipap_mcp.session.manager import SessionManager

        mock_redis = Mock()
        mock_redis.get.return_value = None

        manager = SessionManager(redis_client=mock_redis)
        session = manager.get_session("nonexistent")

        assert session is None


class TestSessionManagerProxyPattern:
    """Test SessionManager supports proxy pattern for Zone 3 & 5."""

    def test_load_zone_field_from_storage(self):
        """Test _load_zone_field_from_storage() loads field from Redis."""
        import json

        from sipap_mcp.session.manager import SessionManager

        mock_redis = Mock()
        mock_redis.hget.return_value = json.dumps({"large": "data"}).encode()

        manager = SessionManager(redis_client=mock_redis)

        # Load field from storage
        result = manager._load_zone_field_from_storage(
            session_id="test_session",
            zone_name="data",
            field_name="user_context"
        )

        # Verify Redis HGET was called
        mock_redis.hget.assert_called_once_with(
            "session:test_session:data",
            "user_context"
        )
        assert result == {"large": "data"}

    def test_save_zone_field_to_storage(self):
        """Test _save_zone_field_to_storage() saves field to Redis."""
        from sipap_mcp.session.manager import SessionManager

        mock_redis = Mock()
        manager = SessionManager(redis_client=mock_redis)

        # Save field to storage
        manager._save_zone_field_to_storage(
            session_id="test_session",
            zone_name="cache",
            field_name="query_results",
            value={"matches": [1, 2, 3]}
        )

        # Verify Redis HSET was called
        assert mock_redis.hset.called

    def test_create_session_with_proxy_zones(self):
        """Test creating session with proxy-enabled Data and Cache zones."""
        from sipap_mcp.session.manager import SessionManager

        mock_redis = Mock()
        manager = SessionManager(redis_client=mock_redis, enable_proxy=True)

        session_id = manager.create_session(
            bearer_token="test_token",
            owner="test_user",
            roles=[]
        )

        # Get session back
        # Mock Redis response
        import json
        session_data = {
            "identity": {"owner": "test_user", "roles": [], "groups": [], "policies": []},
            "metadata": {
                "session_id": session_id,
                "token_hash": hashlib.sha256(b"test_token").hexdigest(),
                "created_at": datetime.now(UTC).isoformat(),
                "last_accessed_at": datetime.now(UTC).isoformat(),
                "ttl": 3600
            },
            "env": {}
        }
        mock_redis.get.return_value = json.dumps(session_data).encode()

        session = manager.get_session(session_id, enable_proxy=True)

        # Verify Data and Cache zones are in proxy mode
        assert session.data._is_proxy is True
        assert session.cache._is_proxy is True


class TestSessionManagerBackwardCompatibility:
    """Test SessionManager maintains backward compatibility."""

    def test_create_session_without_bearer_token_uses_uuid(self):
        """Test backward compatibility: create_session without bearer_token uses UUID."""
        from sipap_mcp.session.manager import SessionManager

        mock_redis = Mock()
        manager = SessionManager(redis_client=mock_redis)

        # Call without bearer_token (backward compatibility)
        session_id = manager.create_session_legacy(
            data={"user_id": "123"},
            ttl=3600
        )

        # Should be UUID format (not SHA256 hash)
        assert len(session_id) == 36  # UUID length with dashes
        assert "-" in session_id

    def test_update_session_with_session_instance(self):
        """Test update_session accepts SessionInstance."""
        from sipap_mcp.core.models import SessionInstance
        from sipap_mcp.session.manager import SessionManager

        mock_redis = Mock()
        manager = SessionManager(redis_client=mock_redis)

        session = SessionInstance.create(
            session_id="abc123",
            token_hash="def456",
            owner="test_user",
            roles=["analyst"]
        )

        # Update session data
        session.data["updated"] = True

        # Update in manager
        result = manager.update_session("abc123", session)

        assert result is True
        assert mock_redis.setex.called or mock_redis.hset.called

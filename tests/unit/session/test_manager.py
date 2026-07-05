"""
Unit tests for session management.

Tests Redis-backed session storage with TTL expiration.
"""

import json
from unittest.mock import MagicMock


def test_session_manager_initialization():
    """Test SessionManager initializes with Redis connection."""
    from sipap_mcp.session.manager import SessionManager

    # Mock Redis client
    redis_client = MagicMock()

    manager = SessionManager(redis_client=redis_client, ttl=3600)

    assert manager.redis_client == redis_client
    assert manager.ttl == 3600


def test_create_session():
    """Test creating a new session."""
    import hashlib

    from sipap_mcp.session.manager import SessionManager

    redis_client = MagicMock()
    manager = SessionManager(redis_client=redis_client, ttl=3600)

    bearer_token = "bearer_test_token_123"
    session_id = manager.create_session(
        bearer_token=bearer_token,
        owner="user_123",
        roles=["analyst"],
    )

    # Should return a deterministic session ID (SHA256 of bearer token)
    assert session_id is not None
    assert isinstance(session_id, str)
    assert len(session_id) == 64  # SHA256 hex length
    expected_id = hashlib.sha256(bearer_token.encode()).hexdigest()
    assert session_id == expected_id

    # Should have called Redis setex (set with expiration)
    redis_client.setex.assert_called_once()


def test_create_session_with_custom_ttl():
    """Test creating session with custom TTL."""
    from sipap_mcp.session.manager import SessionManager

    redis_client = MagicMock()
    manager = SessionManager(redis_client=redis_client, ttl=3600)

    _ = manager.create_session(
        bearer_token="bearer_custom_ttl",
        owner="test_user",
        roles=[],
        ttl=7200
    )

    # Should use custom TTL (7200 seconds)
    call_args = redis_client.setex.call_args
    assert call_args[0][1] == 7200  # Second argument is TTL


def test_get_session_existing():
    """Test retrieving existing session."""
    from datetime import UTC, datetime

    from sipap_mcp.core.models import SessionInstance
    from sipap_mcp.session.manager import SessionManager

    redis_client = MagicMock()
    # Mock Redis to return serialized 5-zone session data
    session_data = {
        "identity": {
            "owner": "user_123",
            "roles": ["analyst"],
            "groups": [],
            "policies": []
        },
        "metadata": {
            "session_id": "test-session-id",
            "token_hash": "abc123",
            "created_at": datetime.now(UTC).isoformat(),
            "last_accessed_at": datetime.now(UTC).isoformat(),
            "ttl": 3600
        },
        "data": {},
        "env": {},
        "cache": {}
    }
    redis_client.get.return_value = json.dumps(session_data).encode()

    manager = SessionManager(redis_client=redis_client, ttl=3600)

    session = manager.get_session("test-session-id")

    # Should return SessionInstance with zones
    assert isinstance(session, SessionInstance)
    assert session.identity.owner == "user_123"
    assert session.metadata.session_id == "test-session-id"
    redis_client.get.assert_called_once_with("session:test-session-id")


def test_get_session_non_existent():
    """Test retrieving non-existent session returns None."""
    from sipap_mcp.session.manager import SessionManager

    redis_client = MagicMock()
    redis_client.get.return_value = None

    manager = SessionManager(redis_client=redis_client, ttl=3600)

    data = manager.get_session("non-existent-id")

    assert data is None


def test_update_session():
    """Test updating existing session."""
    from sipap_mcp.core.models import SessionInstance
    from sipap_mcp.session.manager import SessionManager

    redis_client = MagicMock()
    manager = SessionManager(redis_client=redis_client, ttl=3600)

    # Create a SessionInstance to update
    session = SessionInstance.create(
        session_id="test-session-id",
        token_hash="hash123",
        owner="user_456",
        roles=["analyst"]
    )
    session.data["updated"] = True

    result = manager.update_session("test-session-id", session)

    assert result is True
    redis_client.setex.assert_called_once()


def test_delete_session():
    """Test deleting a session."""
    from sipap_mcp.session.manager import SessionManager

    redis_client = MagicMock()
    redis_client.delete.return_value = 1  # 1 key deleted

    manager = SessionManager(redis_client=redis_client, ttl=3600)

    result = manager.delete_session("test-session-id")

    assert result is True
    redis_client.delete.assert_called_once_with("session:test-session-id")


def test_delete_non_existent_session():
    """Test deleting non-existent session returns False."""
    from sipap_mcp.session.manager import SessionManager

    redis_client = MagicMock()
    redis_client.delete.return_value = 0  # 0 keys deleted

    manager = SessionManager(redis_client=redis_client, ttl=3600)

    result = manager.delete_session("non-existent-id")

    assert result is False


def test_session_key_prefix():
    """Test session keys use correct prefix."""
    from sipap_mcp.session.manager import SessionManager

    redis_client = MagicMock()
    redis_client.get.return_value = None  # Session doesn't exist
    manager = SessionManager(redis_client=redis_client, ttl=3600)

    session_id = "abc-123"
    manager.get_session(session_id)

    # Should use "session:" prefix
    redis_client.get.assert_called_with(f"session:{session_id}")


def test_session_data_serialization():
    """Test session data is properly serialized to JSON."""
    from sipap_mcp.session.manager import SessionManager

    redis_client = MagicMock()
    manager = SessionManager(redis_client=redis_client, ttl=3600)

    manager.create_session(
        bearer_token="bearer_serialize",
        owner="user_123",
        roles=["analyst"],
        env_vars={"API_KEY": "secret"}
    )

    # Should serialize session to JSON
    call_args = redis_client.setex.call_args
    stored_value = call_args[0][2]  # Third argument is value
    assert isinstance(stored_value, (str, bytes))

    # Should be valid JSON with 5-zone structure
    if isinstance(stored_value, bytes):
        stored_value = stored_value.decode()
    parsed = json.loads(stored_value)

    # Verify 5-zone structure
    assert "identity" in parsed
    assert "metadata" in parsed
    assert "data" in parsed
    assert "env" in parsed
    assert "cache" in parsed

    # Verify identity zone content
    assert parsed["identity"]["owner"] == "user_123"
    assert parsed["identity"]["roles"] == ["analyst"]


def test_session_data_deserialization():
    """Test session data is properly deserialized from JSON."""
    from datetime import UTC, datetime

    from sipap_mcp.core.models import SessionInstance
    from sipap_mcp.session.manager import SessionManager

    # Create serialized 5-zone session data
    session_data = {
        "identity": {
            "owner": "user_123",
            "roles": ["analyst"],
            "groups": [],
            "policies": []
        },
        "metadata": {
            "session_id": "test-id",
            "token_hash": "hash123",
            "created_at": datetime.now(UTC).isoformat(),
            "last_accessed_at": datetime.now(UTC).isoformat(),
            "ttl": 3600
        },
        "data": {"context": "test"},
        "env": {},
        "cache": {}
    }

    redis_client = MagicMock()
    redis_client.get.return_value = json.dumps(session_data).encode()

    manager = SessionManager(redis_client=redis_client, ttl=3600)

    retrieved = manager.get_session("test-id")

    # Should deserialize to SessionInstance
    assert isinstance(retrieved, SessionInstance)
    assert retrieved.identity.owner == "user_123"
    assert retrieved.data["context"] == "test"


def test_generate_session_id_uniqueness():
    """Test generated session IDs are unique for different tokens."""
    from sipap_mcp.session.manager import SessionManager

    redis_client = MagicMock()
    manager = SessionManager(redis_client=redis_client, ttl=3600)

    # Generate multiple IDs with different bearer tokens
    ids = set()
    for i in range(100):
        session_id = manager.create_session(
            bearer_token=f"bearer_token_{i}",
            owner="test_user",
            roles=[]
        )
        ids.add(session_id)

    # All should be unique (different tokens = different IDs)
    assert len(ids) == 100


def test_session_ttl_default():
    """Test sessions use default TTL."""
    from sipap_mcp.session.manager import SessionManager

    redis_client = MagicMock()
    manager = SessionManager(redis_client=redis_client, ttl=1800)

    manager.create_session(
        bearer_token="bearer_ttl_test",
        owner="test_user",
        roles=[]
    )

    # Should use default TTL (1800 seconds)
    call_args = redis_client.setex.call_args
    assert call_args[0][1] == 1800


def test_session_exists():
    """Test checking if session exists."""
    from sipap_mcp.session.manager import SessionManager

    redis_client = MagicMock()
    redis_client.exists.return_value = 1  # Session exists

    manager = SessionManager(redis_client=redis_client, ttl=3600)

    result = manager.session_exists("test-session-id")

    assert result is True
    redis_client.exists.assert_called_once_with("session:test-session-id")


def test_session_not_exists():
    """Test checking non-existent session."""
    from sipap_mcp.session.manager import SessionManager

    redis_client = MagicMock()
    redis_client.exists.return_value = 0  # Session doesn't exist

    manager = SessionManager(redis_client=redis_client, ttl=3600)

    result = manager.session_exists("non-existent-id")

    assert result is False


def test_extend_session_ttl():
    """Test extending session TTL."""
    from sipap_mcp.session.manager import SessionManager

    redis_client = MagicMock()
    redis_client.expire.return_value = True

    manager = SessionManager(redis_client=redis_client, ttl=3600)

    result = manager.extend_ttl("test-session-id", ttl=7200)

    assert result is True
    redis_client.expire.assert_called_once_with("session:test-session-id", 7200)

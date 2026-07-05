"""
Example: 5-Zone Session Lifecycle Management

Demonstrates how to:
1. Create sessions with 5-zone architecture
2. Use deterministic session IDs (SHA256 of bearer token)
3. Access zones for different purposes
4. Update session metadata and data
5. Manage session lifecycle (create, get, delete)

This example shows production-grade session management for serverless
MCP deployments with memory safety and security isolation.
"""

from sipap_mcp.core.models import SessionInstance
from sipap_mcp.core.zone import generate_session_id
from sipap_mcp.session.manager import SessionManager


def example_create_session_with_deterministic_id():
    """Example: Create session with deterministic session ID."""
    print("=" * 60)
    print("Example 1: Deterministic Session IDs")
    print("=" * 60)

    # Bearer token from request
    bearer_token = "bearer_abc123xyz"

    # Generate deterministic session ID (SHA256)
    session_id = generate_session_id(bearer_token)
    print(f"Bearer Token: {bearer_token}")
    print(f"Session ID (SHA256): {session_id[:16]}...{session_id[-16:]}")
    print(f"Full length: {len(session_id)} characters")

    # Same token always generates same ID
    session_id_2 = generate_session_id(bearer_token)
    assert session_id == session_id_2
    print("\n✅ Session ID is deterministic (same token = same ID)")


def example_session_zones():
    """Example: Access different session zones."""
    print("\n" + "=" * 60)
    print("Example 2: 5-Zone Session Architecture")
    print("=" * 60)

    # Create session with all zones
    session = SessionInstance.create(
        session_id="session_demo",
        token_hash="hash_demo",
        owner="user@example.com",
        roles=["analyst", "viewer"],
        groups=["sports_team"],
        policies=["read_matches", "read_odds"],
        env_vars={"API_KEY": "secret123", "DB_PASSWORD": "supersecret"},
        ttl=3600
    )

    print("Zone 1 - Identity (Immutable Authorization):")
    print(f"  Owner: {session.identity.owner}")
    print(f"  Roles: {', '.join(session.identity.roles)}")
    print(f"  Groups: {', '.join(session.identity.groups)}")
    print(f"  Policies: {', '.join(session.identity.policies)}")

    print("\nZone 2 - Metadata (Mutable Management):")
    print(f"  Session ID: {session.metadata.session_id}")
    print(f"  Created At: {session.metadata.created_at}")
    print(f"  TTL: {session.metadata.ttl}s")

    print("\nZone 3 - Data (Mutable App State):")
    session.data["user_context"] = {"sport": "football", "league": "EPL"}
    session.data["preferences"] = {"notifications": True}
    print(f"  Keys: {list(session.data.keys())}")
    print(f"  User Context: {session.data['user_context']}")

    print("\nZone 4 - Env (Immutable Secrets - Masked):")
    print(f"  Repr: {session.env}")  # Secrets masked in logs
    # Access individual secrets (not masked)
    # print(f"  API_KEY: {session.env['API_KEY']}")  # Would show real value

    print("\nZone 5 - Cache (Mutable TTL Cache):")
    session.cache["query_results"] = {"matches": [1, 2, 3]}
    print(f"  Cached Keys: {list(session.cache._cache.keys())}")
    print(f"  Cache Length: {len(session.cache)}")

    print("\n✅ All 5 zones accessible with distinct purposes")


def example_immutable_zones():
    """Example: Zone 1 and Zone 4 are immutable (security)."""
    print("\n" + "=" * 60)
    print("Example 3: Immutable Zones for Security")
    print("=" * 60)

    session = SessionInstance.create(
        session_id="session_security",
        token_hash="hash_security",
        owner="admin@example.com",
        roles=["admin"],
        env_vars={"SECRET_KEY": "production_secret"}
    )

    print("Zone 1 (Identity) - Attempt to modify owner:")
    try:
        session.identity.owner = "hacker@evil.com"  # type: ignore
        print("  ❌ SECURITY BREACH - Owner was modified!")
    except AttributeError as e:
        print(f"  ✅ Blocked: {e}")

    print("\nZone 4 (Env) - Attempt to modify secret:")
    try:
        session.env["SECRET_KEY"] = "hacked_secret"
        print("  ❌ SECURITY BREACH - Secret was modified!")
    except AttributeError as e:
        print(f"  ✅ Blocked: {e}")

    print("\n✅ Immutable zones prevent privilege escalation")


def example_session_manager_lifecycle():
    """Example: Complete session lifecycle with SessionManager."""
    print("\n" + "=" * 60)
    print("Example 4: Session Manager Lifecycle")
    print("=" * 60)

    # Create SessionManager (uses fakeredis for demo)
    from fakeredis import FakeRedis
    redis_client = FakeRedis()
    manager = SessionManager(redis_client=redis_client, ttl=3600)

    # Create session
    bearer_token = "bearer_lifecycle_demo"
    session_id = manager.create_session(
        bearer_token=bearer_token,
        owner="demo@example.com",
        roles=["analyst"],
        env_vars={"DEMO_KEY": "demo_value"}
    )

    print(f"Session Created:")
    print(f"  Session ID: {session_id[:16]}...{session_id[-16:]}")

    # Get session
    session = manager.get_session(session_id)
    print(f"\nSession Retrieved:")
    print(f"  Owner: {session.owner}")
    print(f"  Roles: {', '.join(session.roles)}")

    # Update session data
    session.data["processing_state"] = {"step": 1, "status": "in_progress"}
    manager.update_session(session_id, session)
    print(f"\nSession Updated:")
    print(f"  Data keys: {list(session.data.keys())}")

    # Verify update persisted
    session_reloaded = manager.get_session(session_id)
    assert "processing_state" in session_reloaded.data._fields
    print(f"  Update persisted: ✅")

    # Delete session
    manager.delete_session(session_id)
    print(f"\nSession Deleted:")

    # Verify deletion
    try:
        manager.get_session(session_id)
        print("  ❌ Session still exists!")
    except ValueError:
        print("  ✅ Session no longer exists")

    print("\n✅ Complete lifecycle managed successfully")


def example_backward_compatibility():
    """Example: Backward compatible property access."""
    print("\n" + "=" * 60)
    print("Example 5: Backward Compatibility")
    print("=" * 60)

    session = SessionInstance.create(
        session_id="session_compat",
        token_hash="hash_compat",
        owner="user@example.com",
        roles=["viewer"]
    )

    print("New zone-based access:")
    print(f"  session.identity.owner = '{session.identity.owner}'")
    print(f"  session.metadata.session_id = '{session.metadata.session_id}'")

    print("\nBackward compatible properties:")
    print(f"  session.owner = '{session.owner}'")
    print(f"  session.session_id = '{session.session_id}'")
    print(f"  session.roles = {session.roles}")

    # Both work the same
    assert session.owner == session.identity.owner
    assert session.session_id == session.metadata.session_id
    print("\n✅ Backward compatible properties work correctly")


if __name__ == "__main__":
    print("\nSIPAP 5-Zone Session Lifecycle Examples")
    print("=" * 60)

    example_create_session_with_deterministic_id()
    example_session_zones()
    example_immutable_zones()
    example_session_manager_lifecycle()
    example_backward_compatibility()

    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("- Session IDs are deterministic (SHA256 of bearer token)")
    print("- 5 zones provide memory safety and security isolation")
    print("- Zones 1 & 4 immutable (prevent privilege escalation)")
    print("- Zones 3 & 5 support proxy pattern (lazy loading)")
    print("- Backward compatible property access maintained")

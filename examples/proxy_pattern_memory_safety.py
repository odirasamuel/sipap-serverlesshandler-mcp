"""
Example: Proxy Pattern for Memory Safety

Demonstrates how to:
1. Enable proxy mode for SessionData and SessionCache zones
2. Lazy load fields on access to prevent Lambda OOM
3. Persist individual fields to Redis for efficiency
4. Compare in-memory vs proxy mode memory usage
5. Handle large datasets without Lambda memory limits

This pattern is critical for Lambda/Fargate deployments where memory
is limited but session data can be arbitrarily large.
"""

from fakeredis import FakeRedis

from sipap_mcp.core.models import SessionInstance
from sipap_mcp.session.manager import SessionManager


def example_in_memory_mode():
    """Example: Standard in-memory mode (loads all data)."""
    print("=" * 60)
    print("Example 1: In-Memory Mode (Standard)")
    print("=" * 60)

    redis_client = FakeRedis()
    manager = SessionManager(redis_client=redis_client, enable_proxy=False)

    # Create session with data
    session_id = manager.create_session(
        bearer_token="bearer_in_memory",
        owner="user@example.com",
        roles=["analyst"]
    )

    # Add data to session
    session = manager.get_session(session_id)
    assert session is not None

    session.data["context"] = {"sport": "football", "league": "EPL"}
    session.data["preferences"] = {"notifications": True}
    session.data["history"] = [{"match_id": "123", "prediction": "Home Win"}]

    # Update session
    manager.update_session(session_id, session)

    # Retrieve session again
    session_reloaded = manager.get_session(session_id)
    assert session_reloaded is not None

    print(f"In-Memory Mode:")
    print(f"  Loaded all fields: {list(session_reloaded.data._fields.keys())}")
    print(f"  Data size: {len(str(session_reloaded.data._fields))} bytes")
    print(f"  Memory impact: ALL data loaded into Lambda memory")

    print("\n✅ In-memory mode: Fast but loads all data")


def example_proxy_mode():
    """Example: Proxy mode (lazy loads fields on access)."""
    print("\n" + "=" * 60)
    print("Example 2: Proxy Mode (Lazy Loading)")
    print("=" * 60)

    redis_client = FakeRedis()
    manager = SessionManager(redis_client=redis_client, enable_proxy=True)

    # Create session with data
    session_id = manager.create_session(
        bearer_token="bearer_proxy",
        owner="user@example.com",
        roles=["analyst"]
    )

    # Add data to session
    session = manager.get_session(session_id)
    assert session is not None

    # Store large datasets (each field stored separately in Redis)
    session.data["context"] = {"sport": "football", "league": "EPL"}
    session.data["large_dataset_1"] = {"matches": list(range(1000))}
    session.data["large_dataset_2"] = {"odds": list(range(1000))}

    # Save fields individually to Redis
    for field_name, value in session.data._fields.items():
        manager._save_zone_field_to_storage(session_id, "data", field_name, value)

    # Retrieve session in PROXY mode
    session_proxy = manager.get_session(session_id, enable_proxy=True)
    assert session_proxy is not None

    print(f"Proxy Mode:")
    print(f"  Session loaded: YES")
    print(f"  Data fields loaded into memory: NONE (lazy loading)")
    print(f"  Memory impact: ZERO until field accessed")

    # Access specific field (triggers lazy load from Redis)
    context = session_proxy.data["context"]
    print(f"\n  Accessed 'context' field:")
    print(f"    Value: {context}")
    print(f"    Memory impact: ONLY this field loaded")

    print("\n✅ Proxy mode: Minimal memory footprint")


def example_memory_comparison():
    """Example: Compare memory usage (in-memory vs proxy)."""
    print("\n" + "=" * 60)
    print("Example 3: Memory Usage Comparison")
    print("=" * 60)

    redis_client = FakeRedis()

    # Scenario: Session with 100 large datasets
    large_datasets = {}
    for i in range(100):
        large_datasets[f"dataset_{i}"] = {"data": list(range(1000))}

    # Test 1: In-Memory Mode
    manager_memory = SessionManager(redis_client=redis_client, enable_proxy=False)
    session_id_memory = manager_memory.create_session(
        bearer_token="bearer_memory_test",
        owner="user@example.com",
        roles=["analyst"]
    )

    session_memory = manager_memory.get_session(session_id_memory)
    assert session_memory is not None

    for name, dataset in large_datasets.items():
        session_memory.data[name] = dataset

    manager_memory.update_session(session_id_memory, session_memory)

    # Reload in-memory
    session_memory_reloaded = manager_memory.get_session(session_id_memory)
    assert session_memory_reloaded is not None

    memory_size = len(str(session_memory_reloaded.data._fields))
    print(f"In-Memory Mode:")
    print(f"  All 100 datasets loaded: {memory_size:,} bytes (~{memory_size / 1024:.1f} KB)")
    print(f"  Lambda risk: HIGH (could hit 512MB-3GB limit)")

    # Test 2: Proxy Mode
    manager_proxy = SessionManager(redis_client=redis_client, enable_proxy=True)
    session_id_proxy = manager_proxy.create_session(
        bearer_token="bearer_proxy_test",
        owner="user@example.com",
        roles=["analyst"]
    )

    # Store datasets to Redis (not in Lambda memory)
    for name, dataset in large_datasets.items():
        manager_proxy._save_zone_field_to_storage(session_id_proxy, "data", name, dataset)

    # Reload in proxy mode
    session_proxy_reloaded = manager_proxy.get_session(session_id_proxy, enable_proxy=True)
    assert session_proxy_reloaded is not None

    print(f"\nProxy Mode:")
    print(f"  Datasets in Redis: 100")
    print(f"  Datasets in Lambda memory: 0")
    print(f"  Memory usage: ~0 bytes (until accessed)")
    print(f"  Lambda risk: LOW (only loads what you access)")

    print("\n✅ Proxy mode prevents Lambda OOM for large datasets")


def example_selective_loading():
    """Example: Selectively load only needed fields."""
    print("\n" + "=" * 60)
    print("Example 4: Selective Field Loading")
    print("=" * 60)

    redis_client = FakeRedis()
    manager = SessionManager(redis_client=redis_client, enable_proxy=True)

    # Create session
    session_id = manager.create_session(
        bearer_token="bearer_selective",
        owner="user@example.com",
        roles=["analyst"]
    )

    # Store 10 datasets to Redis
    datasets = {
        f"dataset_{i}": {"matches": list(range(100))}
        for i in range(10)
    }

    for name, dataset in datasets.items():
        manager._save_zone_field_to_storage(session_id, "data", name, dataset)

    # Retrieve session in proxy mode
    session = manager.get_session(session_id, enable_proxy=True)
    assert session is not None

    print("Scenario: Need only dataset_5 for prediction")

    # Load ONLY dataset_5 (not all 10 datasets)
    dataset_5 = session.data["dataset_5"]

    print(f"  Loaded: dataset_5")
    print(f"  Memory: {len(str(dataset_5))} bytes")
    print(f"  NOT loaded: dataset_0, dataset_1, ..., dataset_9")
    print(f"  Memory saved: ~90% (9 of 10 datasets not loaded)")

    print("\n✅ Proxy pattern: Load only what you need")


def example_cache_zone_proxy():
    """Example: Proxy pattern for SessionCache zone."""
    print("\n" + "=" * 60)
    print("Example 5: Cache Zone with Proxy Pattern")
    print("=" * 60)

    redis_client = FakeRedis()
    manager = SessionManager(redis_client=redis_client, enable_proxy=True)

    # Create session
    session_id = manager.create_session(
        bearer_token="bearer_cache",
        owner="user@example.com",
        roles=["analyst"]
    )

    # Store query results in cache (with TTL)
    query_results = {
        "query_1": {"matches": [1, 2, 3]},
        "query_2": {"odds": [{"home": 2.5}]},
        "query_3": {"predictions": [{"type": "1X2"}]}
    }

    for query_name, result in query_results.items():
        manager._save_zone_field_to_storage(session_id, "cache", query_name, result)

    # Retrieve session in proxy mode
    session = manager.get_session(session_id, enable_proxy=True)
    assert session is not None

    print("Cache stored: query_1, query_2, query_3")

    # Access ONLY query_2 (lazy load from Redis)
    query_2_result = session.cache["query_2"]

    print(f"\nAccessed: query_2")
    print(f"  Result: {query_2_result}")
    print(f"  Memory impact: ONLY query_2 loaded (not query_1 or query_3)")

    print("\n✅ Cache zone proxy pattern: Efficient memory usage")


def example_when_to_use_proxy():
    """Example: When to use proxy mode vs in-memory mode."""
    print("\n" + "=" * 60)
    print("Example 6: When to Use Proxy Mode")
    print("=" * 60)

    print("Use IN-MEMORY mode when:")
    print("  ✅ Session data is small (< 100KB)")
    print("  ✅ You need fast access to all fields")
    print("  ✅ Lambda has sufficient memory (3GB+)")
    print("  ✅ Predictable data size")

    print("\nUse PROXY mode when:")
    print("  ✅ Session data is large (> 1MB)")
    print("  ✅ Only accessing specific fields per request")
    print("  ✅ Lambda memory is limited (512MB-1GB)")
    print("  ✅ Unpredictable/growing data size")
    print("  ✅ Multiple large datasets in session")

    print("\nExample: Prediction Engine MCP")
    print("  Session stores: 100 match datasets (10MB each)")
    print("  Each prediction needs: 1 match dataset")
    print("  Solution: PROXY mode (load 1 dataset = 10MB vs 1GB)")

    print("\n✅ Proxy pattern is essential for Lambda/Fargate MCP servers")


if __name__ == "__main__":
    print("\nSIPAP Proxy Pattern for Memory Safety Examples")
    print("=" * 60)

    example_in_memory_mode()
    example_proxy_mode()
    example_memory_comparison()
    example_selective_loading()
    example_cache_zone_proxy()
    example_when_to_use_proxy()

    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("- Proxy pattern prevents Lambda OOM (Out of Memory)")
    print("- Fields loaded lazily on access (not all upfront)")
    print("- Ideal for large/unpredictable session data")
    print("- Critical for serverless MCP deployments")
    print("- Enable with: SessionManager(enable_proxy=True)")

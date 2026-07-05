"""
Example: MCP Handler Integration with Sessions

Demonstrates how to:
1. Create MCP servers with @mcp_tool decorated methods
2. Integrate SessionManager with MCP request handlers
3. Use bearer tokens for deterministic session management
4. Build Lambda handlers with session support
5. Handle session lifecycle in serverless environments

This pattern shows production-grade MCP server implementation
with secure session management for Lambda/Fargate deployments.
"""

import json

from fakeredis import FakeRedis

from sipap_mcp.core.server import MCPServer
from sipap_mcp.decorators.tool import mcp_tool
from sipap_mcp.session.manager import SessionManager
from sipap_mcp.transport.lambda_handler import create_lambda_handler


class SportsDataMCP(MCPServer):
    """
    Example MCP server with session-backed tools.

    Demonstrates how to integrate SessionManager with MCP tools
    for stateful request handling in serverless environments.
    """

    def __init__(self, redis_client=None):
        """Initialize MCP server with SessionManager."""
        super().__init__(name="sports-data", version="1.0.0")

        # Create session manager
        if redis_client is None:
            redis_client = FakeRedis()
        self.session_manager = SessionManager(redis_client=redis_client, ttl=3600)

    @mcp_tool(
        description="Get user's favorite team from session",
        input_schema={
            "type": "object",
            "properties": {
                "bearer_token": {"type": "string"}
            },
            "required": ["bearer_token"]
        }
    )
    def get_favorite_team(self, bearer_token: str) -> dict:
        """
        Get user's favorite team from session.

        Args:
            bearer_token: Bearer token for session lookup

        Returns:
            Dict with favorite team or error
        """
        # Get deterministic session ID from bearer token
        from sipap_mcp.core.zone import generate_session_id
        session_id = generate_session_id(bearer_token)

        # Retrieve session
        session = self.session_manager.get_session(session_id)

        if session is None:
            return {"error": "Session not found"}

        # Get favorite team from session data
        favorite_team = session.data.get("favorite_team", "Not set")

        return {
            "session_id": session_id[:16] + "...",
            "owner": session.identity.owner,
            "favorite_team": favorite_team
        }

    @mcp_tool(
        description="Set user's favorite team in session",
        input_schema={
            "type": "object",
            "properties": {
                "bearer_token": {"type": "string"},
                "team_id": {"type": "string"}
            },
            "required": ["bearer_token", "team_id"]
        }
    )
    def set_favorite_team(self, bearer_token: str, team_id: str) -> dict:
        """
        Set user's favorite team in session.

        Args:
            bearer_token: Bearer token for session lookup
            team_id: Team ID to set as favorite

        Returns:
            Dict with success status
        """
        from sipap_mcp.core.zone import generate_session_id
        session_id = generate_session_id(bearer_token)

        # Get or create session
        session = self.session_manager.get_session(session_id)

        if session is None:
            # Create new session
            self.session_manager.create_session(
                bearer_token=bearer_token,
                owner=f"user_{session_id[:8]}",
                roles=["viewer"]
            )
            session = self.session_manager.get_session(session_id)

        # Update favorite team
        assert session is not None
        session.data["favorite_team"] = team_id
        self.session_manager.update_session(session_id, session)

        return {
            "status": "success",
            "team_id": team_id,
            "session_id": session_id[:16] + "..."
        }


def example_mcp_server_with_sessions():
    """Example: MCP server with SessionManager integration."""
    print("=" * 60)
    print("Example 1: MCP Server with Sessions")
    print("=" * 60)

    # Create MCP server
    redis_client = FakeRedis()
    server = SportsDataMCP(redis_client=redis_client)

    print(f"Server created: {server.name} v{server.version}")
    print(f"Tools registered: {server.get_info()['tool_count']}")

    # List tools
    tools = server.list_tools()
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description']}")

    print("\n✅ MCP server with session support ready")


def example_set_favorite_team_via_mcp():
    """Example: Call MCP tool to set favorite team."""
    print("\n" + "=" * 60)
    print("Example 2: Set Favorite Team via MCP Tool")
    print("=" * 60)

    # Create server
    redis_client = FakeRedis()
    server = SportsDataMCP(redis_client=redis_client)

    # Bearer token (would come from request headers)
    bearer_token = "bearer_user_123"

    # Create JSON-RPC 2.0 request to set favorite team
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "set_favorite_team",
            "arguments": {
                "bearer_token": bearer_token,
                "team_id": "team_liverpool"
            }
        }
    }

    print(f"Request:")
    print(f"  Method: {request['method']}")
    print(f"  Tool: {request['params']['name']}")
    print(f"  Team ID: {request['params']['arguments']['team_id']}")

    # Process request
    with server:
        response = server.handle_request(request)

    # Parse MCP content response
    content = response['result']['content'][0]['text']
    result_data = json.loads(content)

    print(f"\nResponse:")
    print(f"  Status: {result_data['status']}")
    print(f"  Session ID: {result_data['session_id']}")

    print("\n✅ Favorite team stored in session")


def example_get_favorite_team_via_mcp():
    """Example: Call MCP tool to retrieve favorite team."""
    print("\n" + "=" * 60)
    print("Example 3: Get Favorite Team via MCP Tool")
    print("=" * 60)

    # Create server
    redis_client = FakeRedis()
    server = SportsDataMCP(redis_client=redis_client)

    # Same bearer token (deterministic session ID)
    bearer_token = "bearer_user_123"

    # First, set favorite team
    set_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "set_favorite_team",
            "arguments": {
                "bearer_token": bearer_token,
                "team_id": "team_manchester_united"
            }
        }
    }

    with server:
        server.handle_request(set_request)

    # Then, retrieve favorite team
    get_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "get_favorite_team",
            "arguments": {
                "bearer_token": bearer_token
            }
        }
    }

    with server:
        response = server.handle_request(get_request)

    # Parse MCP content response
    content = response['result']['content'][0]['text']
    result_data = json.loads(content)

    print(f"Favorite Team Retrieved:")
    print(f"  Owner: {result_data['owner']}")
    print(f"  Team: {result_data['favorite_team']}")
    print(f"  Session ID: {result_data['session_id']}")

    print("\n✅ Session persists across requests (deterministic ID)")


def example_lambda_handler_with_sessions():
    """Example: Create Lambda handler with session support."""
    print("\n" + "=" * 60)
    print("Example 4: Lambda Handler with Sessions")
    print("=" * 60)

    # Create MCP server
    redis_client = FakeRedis()
    server = SportsDataMCP(redis_client=redis_client)

    # Create Lambda handler (no auth for demo)
    handler = create_lambda_handler(server, auth=None)

    print("Lambda handler created")

    # Simulate Lambda event (API Gateway)
    bearer_token = "bearer_lambda_user"
    event = {
        "headers": {},
        "body": json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "set_favorite_team",
                "arguments": {
                    "bearer_token": bearer_token,
                    "team_id": "team_arsenal"
                }
            }
        })
    }

    context = {}  # Lambda context (unused)

    # Invoke handler
    response = handler(event, context)

    # Parse Lambda response
    body = json.loads(response['body'])
    content = body['result']['content'][0]['text']
    result_data = json.loads(content)

    print(f"\nLambda Response:")
    print(f"  Status Code: {response['statusCode']}")
    print(f"  Result: {result_data}")

    print("\n✅ Lambda handler with session management ready for deployment")


def example_session_lifecycle_in_mcp():
    """Example: Complete session lifecycle in MCP context."""
    print("\n" + "=" * 60)
    print("Example 5: Session Lifecycle in MCP")
    print("=" * 60)

    redis_client = FakeRedis()
    server = SportsDataMCP(redis_client=redis_client)

    bearer_token = "bearer_lifecycle_demo"

    print("Session Lifecycle:")

    # 1. First request: Create session
    request1 = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "set_favorite_team",
            "arguments": {
                "bearer_token": bearer_token,
                "team_id": "team_chelsea"
            }
        }
    }

    with server:
        server.handle_request(request1)
    print("  1. Session created with favorite team")

    # 2. Second request: Update session
    request2 = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "set_favorite_team",
            "arguments": {
                "bearer_token": bearer_token,
                "team_id": "team_tottenham"
            }
        }
    }

    with server:
        server.handle_request(request2)
    print("  2. Session updated with new favorite team")

    # 3. Third request: Retrieve session
    request3 = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "get_favorite_team",
            "arguments": {
                "bearer_token": bearer_token
            }
        }
    }

    with server:
        response = server.handle_request(request3)

    # Parse MCP content response
    content = response['result']['content'][0]['text']
    result_data = json.loads(content)

    print(f"  3. Session retrieved:")
    print(f"     Current favorite: {result_data['favorite_team']}")

    # 4. Delete session
    from sipap_mcp.core.zone import generate_session_id
    session_id = generate_session_id(bearer_token)
    server.session_manager.delete_session(session_id)
    print("  4. Session deleted")

    # 5. Verify deletion
    request4 = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "get_favorite_team",
            "arguments": {
                "bearer_token": bearer_token
            }
        }
    }

    with server:
        response = server.handle_request(request4)

    # Parse MCP content response
    content = response['result']['content'][0]['text']
    result_data = json.loads(content)

    if "error" in result_data:
        print(f"  5. Session no longer exists: {result_data['error']}")

    print("\n✅ Complete session lifecycle managed in MCP context")


def example_multi_user_sessions():
    """Example: Multiple users with isolated sessions."""
    print("\n" + "=" * 60)
    print("Example 6: Multi-User Session Isolation")
    print("=" * 60)

    redis_client = FakeRedis()
    server = SportsDataMCP(redis_client=redis_client)

    # Three users with different bearer tokens
    users = [
        ("bearer_user_a", "team_liverpool"),
        ("bearer_user_b", "team_manchester_city"),
        ("bearer_user_c", "team_newcastle")
    ]

    print("Creating sessions for 3 users:")

    # Set favorite teams for each user
    for bearer_token, team_id in users:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "set_favorite_team",
                "arguments": {
                    "bearer_token": bearer_token,
                    "team_id": team_id
                }
            }
        }

        with server:
            response = server.handle_request(request)

        print(f"  User: {bearer_token} -> {team_id}")

    # Verify isolation: Each user gets their own favorite team
    print("\nVerifying session isolation:")

    for bearer_token, expected_team in users:
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_favorite_team",
                "arguments": {
                    "bearer_token": bearer_token
                }
            }
        }

        with server:
            response = server.handle_request(request)

        # Parse MCP content response
        content = response['result']['content'][0]['text']
        result_data = json.loads(content)

        actual_team = result_data['favorite_team']
        assert actual_team == expected_team
        print(f"  {bearer_token}: {actual_team} ✅")

    print("\n✅ Sessions are isolated per user (deterministic IDs)")


if __name__ == "__main__":
    print("\nSIPAP MCP Handler Integration Examples")
    print("=" * 60)

    example_mcp_server_with_sessions()
    example_set_favorite_team_via_mcp()
    example_get_favorite_team_via_mcp()
    example_lambda_handler_with_sessions()
    example_session_lifecycle_in_mcp()
    example_multi_user_sessions()

    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("- MCP tools can access SessionManager for stateful requests")
    print("- Bearer tokens generate deterministic session IDs")
    print("- Sessions persist across multiple tool calls")
    print("- Lambda handlers integrate seamlessly with sessions")
    print("- Multi-user sessions are isolated by bearer token")

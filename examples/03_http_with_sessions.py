"""
HTTP Deployment with Session Management Example

Demonstrates:
- Creating FastAPI app from MCP server
- Session management with Redis
- Stateful interactions across requests
- Running on ECS Fargate or local development
"""

import redis
from sipap_mcp import MCPServer, mcp_tool
from sipap_mcp.auth import NoAuth
from sipap_mcp.session import SessionManager
from sipap_mcp.transport import create_http_app


class ChatMCP(MCPServer):
    """Conversational MCP server with session state."""

    def __init__(self, session_manager: SessionManager | None = None):
        super().__init__(name="chat-mcp", version="1.0.0")
        self.session_manager = session_manager

    @mcp_tool(
        description="Start a new conversation session",
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User identifier"}
            },
            "required": ["user_id"],
        },
    )
    def start_session(self, user_id: str) -> dict:
        """Start a new conversation session."""
        if not self.session_manager:
            return {"error": "Session management not available"}

        # Create session with user context
        session_id = self.session_manager.create_session(
            data={"user_id": user_id, "message_count": 0, "context": []}, ttl=1800  # 30 minutes
        )

        return {
            "session_id": session_id,
            "user_id": user_id,
            "message": "Session started. Use this session_id in subsequent requests.",
        }

    @mcp_tool(
        description="Send a message in a session",
        input_schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session identifier"},
                "message": {"type": "string", "description": "User message"},
            },
            "required": ["session_id", "message"],
        },
    )
    def send_message(self, session_id: str, message: str) -> dict:
        """Send a message and get a response."""
        if not self.session_manager:
            return {"error": "Session management not available"}

        # Retrieve session
        session_data = self.session_manager.get_session(session_id)
        if not session_data:
            return {"error": "Session not found or expired"}

        # Update session state
        session_data["message_count"] += 1
        session_data["context"].append({"role": "user", "message": message})

        # Simulate response (in production, this would use an LLM)
        response = f"Echo: {message} (Message #{session_data['message_count']})"
        session_data["context"].append({"role": "assistant", "message": response})

        # Save updated session
        self.session_manager.update_session(session_id, session_data)

        return {
            "response": response,
            "message_count": session_data["message_count"],
            "session_id": session_id,
        }

    @mcp_tool(
        description="Get session history",
        input_schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session identifier"}
            },
            "required": ["session_id"],
        },
    )
    def get_history(self, session_id: str) -> dict:
        """Get conversation history for a session."""
        if not self.session_manager:
            return {"error": "Session management not available"}

        session_data = self.session_manager.get_session(session_id)
        if not session_data:
            return {"error": "Session not found or expired"}

        return {
            "session_id": session_id,
            "user_id": session_data["user_id"],
            "message_count": session_data["message_count"],
            "history": session_data["context"],
        }


def create_app():
    """Create FastAPI app with Redis session management."""
    # Connect to Redis (local or ElastiCache)
    redis_host = "localhost"  # Change to ElastiCache endpoint in production
    redis_port = 6379
    redis_client = redis.Redis(
        host=redis_host, port=redis_port, decode_responses=False
    )

    # Create session manager
    session_manager = SessionManager(redis_client=redis_client, ttl=1800)

    # Create server
    server = ChatMCP(session_manager=session_manager)

    # Create FastAPI app (no auth for demo, use APIKeyAuth in production)
    app = create_http_app(server, auth=NoAuth())

    return app


# Create app instance (this is what uvicorn runs)
app = create_app()


if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("HTTP Server with Session Management")
    print("=" * 60)
    print("\nStarting server on http://localhost:8000")
    print("Endpoint: POST http://localhost:8000/mcp")
    print("\nMake sure Redis is running:")
    print("  docker run -d -p 6379:6379 redis:7-alpine")
    print("\nExample workflow:")
    print("  1. Start session: tools/call -> start_session")
    print("  2. Send message: tools/call -> send_message (with session_id)")
    print("  3. Get history: tools/call -> get_history (with session_id)")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8000)

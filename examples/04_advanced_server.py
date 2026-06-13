"""
Advanced MCP Server Example

Demonstrates:
- Multiple tools with different input schemas
- Custom lifecycle hooks (_setup and _cleanup)
- Error handling and validation
- Logging integration
- Database connections
"""

from sipap_mcp import MCPServer, mcp_tool


class SportsDataMCP(MCPServer):
    """Advanced sports data MCP server with lifecycle management."""

    def __init__(self, api_key: str):
        super().__init__(name="sports-data-mcp", version="1.0.0")
        self.api_key = api_key
        self.db_connection = None
        self.cache = {}

    def _setup(self) -> None:
        """
        Setup hook called when entering context manager.

        Initialize resources like database connections, caches, etc.
        """
        print(f"[{self.name}] Setting up resources...")

        # Simulate database connection
        self.db_connection = {"connected": True, "host": "sports-db.example.com"}
        print(f"[{self.name}] Connected to database")

        # Initialize cache
        self.cache = {"teams": {}, "matches": {}}
        print(f"[{self.name}] Initialized cache")

    def _cleanup(self) -> None:
        """
        Cleanup hook called when exiting context manager.

        Clean up resources to prevent leaks.
        """
        print(f"[{self.name}] Cleaning up resources...")

        # Close database connection
        if self.db_connection:
            self.db_connection = None
            print(f"[{self.name}] Closed database connection")

        # Clear cache
        self.cache.clear()
        print(f"[{self.name}] Cleared cache")

    @mcp_tool(
        description="Get team information by ID",
        input_schema={
            "type": "object",
            "properties": {
                "team_id": {
                    "type": "string",
                    "description": "Unique team identifier",
                    "pattern": "^[a-z0-9-]+$",
                },
                "include_stats": {
                    "type": "boolean",
                    "description": "Include season statistics",
                    "default": False,
                },
            },
            "required": ["team_id"],
        },
    )
    def get_team(self, team_id: str, include_stats: bool = False) -> dict:
        """Get detailed team information."""
        # Check cache first
        if team_id in self.cache["teams"]:
            print(f"  Cache hit for team: {team_id}")
            return self.cache["teams"][team_id]

        # Simulate API call
        team_data = {
            "team_id": team_id,
            "name": f"Team {team_id.upper()}",
            "league": "Premier League",
            "founded": 1886,
        }

        if include_stats:
            team_data["stats"] = {
                "wins": 15,
                "draws": 5,
                "losses": 3,
                "goals_scored": 42,
                "goals_conceded": 18,
            }

        # Cache result
        self.cache["teams"][team_id] = team_data
        return team_data

    @mcp_tool(
        description="Get match schedule for a team",
        input_schema={
            "type": "object",
            "properties": {
                "team_id": {"type": "string"},
                "days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 30,
                    "default": 7,
                    "description": "Number of days to look ahead",
                },
                "competition": {
                    "type": "string",
                    "enum": ["league", "cup", "european", "all"],
                    "default": "all",
                },
            },
            "required": ["team_id"],
        },
    )
    def get_schedule(
        self, team_id: str, days: int = 7, competition: str = "all"
    ) -> dict:
        """Get upcoming match schedule for a team."""
        # Simulate database query
        matches = [
            {
                "match_id": f"m{i}",
                "home_team": team_id if i % 2 == 0 else f"opponent-{i}",
                "away_team": f"opponent-{i}" if i % 2 == 0 else team_id,
                "date": f"2026-06-{14 + i}",
                "competition": "league" if i % 2 == 0 else "cup",
            }
            for i in range(min(days // 7, 5))
        ]

        # Filter by competition
        if competition != "all":
            matches = [m for m in matches if m["competition"] == competition]

        return {
            "team_id": team_id,
            "days": days,
            "competition": competition,
            "matches": matches,
            "count": len(matches),
        }

    @mcp_tool(
        description="Get live match score",
        input_schema={
            "type": "object",
            "properties": {
                "match_id": {
                    "type": "string",
                    "description": "Unique match identifier",
                }
            },
            "required": ["match_id"],
        },
    )
    def get_live_score(self, match_id: str) -> dict:
        """Get live score and match status."""
        # Simulate live data
        return {
            "match_id": match_id,
            "status": "live",
            "minute": 67,
            "home_score": 2,
            "away_score": 1,
            "home_team": "arsenal",
            "away_team": "chelsea",
            "events": [
                {"minute": 23, "type": "goal", "team": "home", "player": "Saka"},
                {"minute": 45, "type": "goal", "team": "away", "player": "Palmer"},
                {"minute": 61, "type": "goal", "team": "home", "player": "Havertz"},
            ],
        }

    @mcp_tool(
        description="Search for teams by name",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 2,
                    "description": "Search query (minimum 2 characters)",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    )
    def search_teams(self, query: str, limit: int = 10) -> dict:
        """Search for teams by name."""
        # Simulate search
        all_teams = [
            {"team_id": "arsenal", "name": "Arsenal FC"},
            {"team_id": "chelsea", "name": "Chelsea FC"},
            {"team_id": "liverpool", "name": "Liverpool FC"},
            {"team_id": "manchester-united", "name": "Manchester United"},
            {"team_id": "manchester-city", "name": "Manchester City"},
        ]

        # Filter by query
        query_lower = query.lower()
        results = [t for t in all_teams if query_lower in t["name"].lower()]

        return {
            "query": query,
            "count": len(results),
            "results": results[:limit],
        }


def main():
    """Demonstrate advanced server features."""
    # Create server with API key
    server = SportsDataMCP(api_key="demo-key-12345")

    # List all tools
    print("\n" + "=" * 60)
    print("Available Tools")
    print("=" * 60)
    tools = server.list_tools()
    for i, tool in enumerate(tools, 1):
        print(f"{i}. {tool['name']}")
        print(f"   Description: {tool['description']}")
        print(
            f"   Required: {tool.get('inputSchema', {}).get('required', [])}"
        )

    # Use server with context manager (triggers _setup and _cleanup)
    print("\n" + "=" * 60)
    print("Server Lifecycle Demo")
    print("=" * 60)

    with server:
        print("\n[Server is now active - resources initialized]\n")

        # Call some tools
        requests = [
            {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {
                    "name": "get_team",
                    "arguments": {"team_id": "arsenal", "include_stats": True},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": "2",
                "method": "tools/call",
                "params": {
                    "name": "get_schedule",
                    "arguments": {"team_id": "arsenal", "days": 14},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": "3",
                "method": "tools/call",
                "params": {
                    "name": "search_teams",
                    "arguments": {"query": "man", "limit": 5},
                },
            },
        ]

        for req in requests:
            print(f"Request: {req['params']['name']}")
            response = server.handle_request(req)
            if "result" in response:
                print(f"  Success: {response['result']}")
            else:
                print(f"  Error: {response.get('error', {}).get('message')}")
            print()

    print("[Server context exited - resources cleaned up]\n")
    print("=" * 60)


if __name__ == "__main__":
    main()

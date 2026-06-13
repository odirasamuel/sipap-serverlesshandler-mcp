"""
Lambda Deployment with Authentication Example

Demonstrates:
- Creating Lambda handler from MCP server
- API key authentication
- Environment-based configuration
- Production-ready deployment
"""

import json
import os

from sipap_mcp import MCPServer, mcp_tool
from sipap_mcp.auth import APIKeyAuth
from sipap_mcp.transport import create_lambda_handler


class WeatherMCP(MCPServer):
    """Weather data MCP server."""

    def __init__(self):
        super().__init__(name="weather-mcp", version="1.0.0")

    @mcp_tool(
        description="Get current weather for a location",
        input_schema={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name or coordinates",
                },
                "units": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "default": "celsius",
                },
            },
            "required": ["location"],
        },
    )
    def get_current_weather(self, location: str, units: str = "celsius") -> dict:
        """Get current weather conditions."""
        # In production, this would call a weather API
        return {
            "location": location,
            "temperature": 22 if units == "celsius" else 72,
            "units": units,
            "condition": "partly cloudy",
            "humidity": 65,
        }

    @mcp_tool(
        description="Get weather forecast for a location",
        input_schema={
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "days": {"type": "integer", "minimum": 1, "maximum": 7, "default": 3},
            },
            "required": ["location"],
        },
    )
    def get_forecast(self, location: str, days: int = 3) -> dict:
        """Get weather forecast for upcoming days."""
        # In production, this would call a weather API
        forecast = []
        for day in range(days):
            forecast.append(
                {
                    "day": f"Day {day + 1}",
                    "temperature_high": 25,
                    "temperature_low": 18,
                    "condition": "sunny",
                }
            )
        return {"location": location, "days": days, "forecast": forecast}


# Production deployment configuration
def get_api_keys() -> list[str]:
    """Get API keys from environment variable."""
    api_keys_str = os.getenv("API_KEYS", "")
    if not api_keys_str:
        # Development fallback (never use in production)
        return ["dev-key-12345"]

    # Production: comma-separated keys from environment
    return [key.strip() for key in api_keys_str.split(",") if key.strip()]


# Create server instance
server = WeatherMCP()

# Configure authentication
auth = APIKeyAuth(api_keys=get_api_keys())

# Create Lambda handler (this is the entry point AWS Lambda calls)
handler = create_lambda_handler(server, auth=auth)


def demo_local():
    """Demonstrate handler locally (for testing)."""
    # Simulate Lambda event WITHOUT API key (should fail)
    event_no_auth = {
        "headers": {},
        "body": json.dumps(
            {"jsonrpc": "2.0", "id": "1", "method": "tools/list", "params": {}}
        ),
    }

    print("Request WITHOUT API key:")
    response = handler(event_no_auth, {})
    print(f"  Status: {response['statusCode']}")
    if response["statusCode"] == 401:
        print("  Result: Authentication failed (expected)")

    # Simulate Lambda event WITH valid API key (should succeed)
    event_with_auth = {
        "headers": {"X-API-Key": "dev-key-12345"},
        "body": json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "2",
                "method": "tools/call",
                "params": {
                    "name": "get_current_weather",
                    "arguments": {"location": "London"},
                },
            }
        ),
    }

    print("\nRequest WITH valid API key:")
    response = handler(event_with_auth, {})
    print(f"  Status: {response['statusCode']}")
    if response["statusCode"] == 200:
        body = json.loads(response["body"])
        print(f"  Result: Success")
        print(f"  Content: {body['result']}")


if __name__ == "__main__":
    print("=" * 60)
    print("Lambda Handler with Authentication Demo")
    print("=" * 60)
    demo_local()
    print("\n" + "=" * 60)
    print("Deployment Instructions:")
    print("=" * 60)
    print("1. Set environment variable:")
    print("   export API_KEYS='key1,key2,key3'")
    print("\n2. Deploy to Lambda:")
    print("   - Function name: weather-mcp")
    print("   - Handler: 02_lambda_with_auth.handler")
    print("   - Runtime: python3.12")
    print("   - Timeout: 30 seconds")
    print("\n3. Test with API key in X-API-Key header")
    print("=" * 60)

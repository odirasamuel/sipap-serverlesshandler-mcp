"""
Authentication Strategies Example

Demonstrates:
- NoAuth (development)
- APIKeyAuth (production)
- SigV4Auth (AWS IAM)
- Environment-based configuration
"""

import json
import os

from sipap_mcp import MCPServer, mcp_tool
from sipap_mcp.auth import APIKeyAuth, NoAuth, SigV4Auth
from sipap_mcp.transport import create_lambda_handler


class SecureMCP(MCPServer):
    """MCP server demonstrating different authentication strategies."""

    def __init__(self):
        super().__init__(name="secure-mcp", version="1.0.0")

    @mcp_tool(
        description="Get server status",
        input_schema={"type": "object", "properties": {}},
    )
    def get_status(self) -> dict:
        """Get server health status."""
        return {"status": "healthy", "version": "1.0.0", "uptime": 3600}

    @mcp_tool(
        description="Get protected data",
        input_schema={"type": "object", "properties": {}},
    )
    def get_protected_data(self) -> dict:
        """Get protected data (requires authentication)."""
        return {
            "data": "sensitive information",
            "classification": "confidential",
        }


def demo_no_auth():
    """
    NoAuth: No authentication (development only).

    Use case:
    - Local development
    - Internal services on trusted network
    - Testing and debugging
    """
    print("\n" + "=" * 60)
    print("1. NoAuth (Development)")
    print("=" * 60)

    server = SecureMCP()
    handler = create_lambda_handler(server, auth=NoAuth())

    # Any request succeeds (no auth check)
    event = {
        "headers": {},  # No API key needed
        "body": json.dumps(
            {"jsonrpc": "2.0", "id": "1", "method": "tools/list", "params": {}}
        ),
    }

    response = handler(event, {})
    print(f"Status: {response['statusCode']}")
    print("Result: All requests succeed (no authentication)")
    print("⚠️  WARNING: Never use NoAuth in production!")


def demo_api_key_auth():
    """
    APIKeyAuth: API key in X-API-Key header.

    Use case:
    - Production API deployments
    - Multi-tenant applications
    - Rate limiting by client
    """
    print("\n" + "=" * 60)
    print("2. APIKeyAuth (Production)")
    print("=" * 60)

    server = SecureMCP()

    # Multiple API keys for different clients/tenants
    auth = APIKeyAuth(
        api_keys=[
            "client-a-key-abc123",
            "client-b-key-def456",
            "client-c-key-ghi789",
        ]
    )

    handler = create_lambda_handler(server, auth=auth)

    # Request WITHOUT API key (fails)
    event_no_key = {
        "headers": {},
        "body": json.dumps(
            {"jsonrpc": "2.0", "id": "1", "method": "tools/list", "params": {}}
        ),
    }

    response = handler(event_no_key, {})
    print(f"Request without key - Status: {response['statusCode']}")
    print("  Result: Authentication failed (expected)")

    # Request WITH valid API key (succeeds)
    event_with_key = {
        "headers": {"X-API-Key": "client-a-key-abc123"},
        "body": json.dumps(
            {"jsonrpc": "2.0", "id": "2", "method": "tools/list", "params": {}}
        ),
    }

    response = handler(event_with_key, {})
    print(f"Request with valid key - Status: {response['statusCode']}")
    print("  Result: Success")

    # Request WITH invalid API key (fails)
    event_bad_key = {
        "headers": {"X-API-Key": "invalid-key-xyz"},
        "body": json.dumps(
            {"jsonrpc": "2.0", "id": "3", "method": "tools/list", "params": {}}
        ),
    }

    response = handler(event_bad_key, {})
    print(f"Request with invalid key - Status: {response['statusCode']}")
    print("  Result: Authentication failed (expected)")


def demo_sigv4_auth():
    """
    SigV4Auth: AWS Signature Version 4.

    Use case:
    - Lambda Function URLs with IAM auth
    - API Gateway with IAM authorization
    - AWS service-to-service calls
    """
    print("\n" + "=" * 60)
    print("3. SigV4Auth (AWS IAM)")
    print("=" * 60)

    server = SecureMCP()

    # SigV4 auth for AWS Lambda in us-east-1
    auth = SigV4Auth(service="lambda", region="us-east-1")

    handler = create_lambda_handler(server, auth=auth)

    # Request WITHOUT signature headers (fails)
    event_no_sig = {
        "headers": {},
        "body": json.dumps(
            {"jsonrpc": "2.0", "id": "1", "method": "tools/list", "params": {}}
        ),
    }

    response = handler(event_no_sig, {})
    print(f"Request without signature - Status: {response['statusCode']}")
    print("  Result: Authentication failed (expected)")

    # Request WITH signature headers (MVP: basic structure validation)
    event_with_sig = {
        "headers": {
            "Authorization": "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20260613/us-east-1/lambda/aws4_request, SignedHeaders=host;x-amz-date, Signature=abc123",
            "X-Amz-Date": "20260613T120000Z",
        },
        "body": json.dumps(
            {"jsonrpc": "2.0", "id": "2", "method": "tools/list", "params": {}}
        ),
    }

    response = handler(event_with_sig, {})
    print(f"Request with valid signature structure - Status: {response['statusCode']}")
    print("  Result: Success (MVP validates structure, not cryptographic signature)")
    print("  Note: Production would verify actual signature")


def demo_environment_based():
    """
    Environment-based auth selection.

    Use case:
    - Same codebase for dev/staging/production
    - Configuration via environment variables
    """
    print("\n" + "=" * 60)
    print("4. Environment-Based Configuration")
    print("=" * 60)

    server = SecureMCP()

    # Select auth based on environment
    env = os.getenv("ENVIRONMENT", "dev")

    if env == "dev":
        auth = NoAuth()
        print("Environment: development")
        print("  Auth: NoAuth (no authentication)")
    elif env == "staging":
        auth = APIKeyAuth(api_keys=[os.getenv("STAGING_API_KEY", "staging-key")])
        print("Environment: staging")
        print("  Auth: APIKeyAuth (single key from env)")
    elif env == "production":
        api_keys = os.getenv("API_KEYS", "").split(",")
        auth = APIKeyAuth(api_keys=[k.strip() for k in api_keys if k.strip()])
        print("Environment: production")
        print("  Auth: APIKeyAuth (multiple keys from env)")
    else:
        auth = NoAuth()
        print(f"Environment: {env} (unknown, defaulting to NoAuth)")

    handler = create_lambda_handler(server, auth=auth)
    print(f"  Handler created with {auth.__class__.__name__}")


def main():
    """Run all authentication demos."""
    print("\n" + "=" * 60)
    print("MCP Authentication Strategies Demo")
    print("=" * 60)

    demo_no_auth()
    demo_api_key_auth()
    demo_sigv4_auth()
    demo_environment_based()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("""
Authentication Strategy Selection Guide:

1. NoAuth
   ✓ Local development
   ✓ Trusted internal networks
   ✗ Never use in production

2. APIKeyAuth
   ✓ Production APIs
   ✓ Multi-tenant applications
   ✓ Client-specific rate limiting
   - Requires key distribution/rotation

3. SigV4Auth
   ✓ AWS Lambda Function URLs
   ✓ API Gateway with IAM
   ✓ Service-to-service calls
   - More complex to implement
   - Built-in AWS integration

Environment-based configuration allows same code across all environments.
    """)
    print("=" * 60)


if __name__ == "__main__":
    main()

"""
Authentication middleware for MCP servers.

Provides pluggable authentication strategies:
- NoAuth: No authentication (development/testing)
- APIKeyAuth: API key validation from headers
- SigV4Auth: AWS SigV4 signature validation
"""

from abc import ABC, abstractmethod
from typing import Any


class AuthenticationError(Exception):
    """Exception raised when authentication fails."""

    pass


class AuthStrategy(ABC):
    """
    Abstract base class for authentication strategies.

    Subclasses must implement authenticate() method.
    """

    @abstractmethod
    def authenticate(self, headers: dict[str, Any] | None) -> bool:
        """
        Authenticate request based on headers.

        Args:
            headers: Request headers dict

        Returns:
            True if authentication succeeds

        Raises:
            AuthenticationError: If authentication fails
        """
        pass


class NoAuth(AuthStrategy):
    """
    No authentication strategy (bypass authentication).

    Useful for development, testing, or internal services.
    """

    def authenticate(self, _headers: dict[str, Any] | None) -> bool:
        """Always return True (no authentication)."""
        return True


class APIKeyAuth(AuthStrategy):
    """
    API key authentication strategy.

    Validates API key from X-API-Key header against allowed keys.
    """

    def __init__(self, api_keys: list[str]):
        """
        Initialize API key authentication.

        Args:
            api_keys: List of valid API keys
        """
        self.api_keys = set(api_keys)

    def authenticate(self, headers: dict[str, Any] | None) -> bool:
        """
        Authenticate request using API key from headers.

        Args:
            headers: Request headers dict

        Returns:
            True if API key is valid

        Raises:
            AuthenticationError: If API key is missing or invalid

        Example:
            >>> auth = APIKeyAuth(api_keys=["key-123", "key-456"])
            >>> headers = {"X-API-Key": "key-123"}
            >>> auth.authenticate(headers)
            True
        """
        if headers is None:
            headers = {}

        # Normalize headers to lowercase for case-insensitive lookup
        headers_lower = {k.lower(): v for k, v in headers.items()}

        # Check for X-API-Key header
        api_key = headers_lower.get("x-api-key")

        if api_key is None:
            raise AuthenticationError("Missing API key in X-API-Key header")

        if api_key not in self.api_keys:
            raise AuthenticationError("Invalid API key")

        return True


class SigV4Auth(AuthStrategy):
    """
    AWS SigV4 signature authentication strategy.

    Validates AWS Signature Version 4 from request headers.

    Note: This is a basic structure for MVP. Full SigV4 validation
    requires request body, query parameters, and signature calculation.
    """

    def __init__(self, service: str, region: str):
        """
        Initialize SigV4 authentication.

        Args:
            service: AWS service name (e.g., "execute-api")
            region: AWS region (e.g., "us-east-1")
        """
        self.service = service
        self.region = region

    def authenticate(self, headers: dict[str, Any] | None) -> bool:
        """
        Authenticate request using AWS SigV4 signature.

        Args:
            headers: Request headers dict

        Returns:
            True if signature is valid

        Raises:
            AuthenticationError: If signature is missing or invalid

        Note:
            For MVP, this performs basic structure validation.
            Full SigV4 validation would verify the signature cryptographically.
        """
        if headers is None:
            headers = {}

        # Normalize headers to lowercase
        headers_lower = {k.lower(): v for k, v in headers.items()}

        # Check for required AWS signature headers
        authorization = headers_lower.get("authorization")
        x_amz_date = headers_lower.get("x-amz-date")

        if authorization is None:
            raise AuthenticationError("Missing Authorization header for AWS SigV4")

        if x_amz_date is None:
            raise AuthenticationError("Missing X-Amz-Date header for AWS SigV4")

        # Basic structure validation
        if not authorization.startswith("AWS4-HMAC-SHA256"):
            raise AuthenticationError("Invalid AWS SigV4 signature format")

        # MVP: Accept any well-formed signature
        # Full implementation would:
        # 1. Parse credential scope
        # 2. Reconstruct canonical request
        # 3. Calculate signature
        # 4. Compare with provided signature

        return True

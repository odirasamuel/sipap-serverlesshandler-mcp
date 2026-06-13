"""
JSON Schema Validation for MCP Tool Inputs.

Validates tool input arguments against JSON Schema Draft 7.
"""

from typing import Any

import jsonschema
from jsonschema import Draft7Validator


class ValidationError(Exception):
    """Exception raised when input validation fails."""

    pass


def validate_input(data: Any, schema: dict[str, Any] | None) -> bool:
    """
    Validate data against JSON Schema.

    Args:
        data: Data to validate
        schema: JSON Schema (Draft 7) or None to skip validation

    Returns:
        True if validation passes

    Raises:
        ValidationError: If validation fails

    Example:
        schema = {
            "type": "object",
            "properties": {
                "team_id": {"type": "string"},
                "days": {"type": "integer", "default": 7}
            },
            "required": ["team_id"]
        }

        validate_input({"team_id": "arsenal", "days": 7}, schema)
        # Returns True

        validate_input({"days": 7}, schema)
        # Raises ValidationError: 'team_id' is a required property
    """
    # Skip validation if no schema provided
    if schema is None:
        return True

    try:
        # Use Draft7Validator for JSON Schema Draft 7 compliance
        validator = Draft7Validator(schema)
        validator.validate(data)
        return True

    except jsonschema.ValidationError as e:
        # Convert jsonschema.ValidationError to our ValidationError
        # with a clear error message
        error_msg = _format_validation_error(e)
        raise ValidationError(error_msg) from e

    except jsonschema.SchemaError as e:
        # Schema itself is invalid
        raise ValidationError(f"Invalid JSON Schema: {e.message}") from e


def _format_validation_error(error: jsonschema.ValidationError) -> str:
    """
    Format jsonschema validation error into clear message.

    Args:
        error: jsonschema ValidationError

    Returns:
        Formatted error message

    Example:
        "'team_id' is a required property"
        "123 is not of type 'string'"
        "'invalid' is not one of ['active', 'inactive', 'pending']"
    """
    # Get the path to the failing field
    path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"

    # Get the error message
    message = error.message

    # Create formatted error
    if path == "root":
        return f"Validation error: {message}"
    else:
        return f"Validation error at '{path}': {message}"

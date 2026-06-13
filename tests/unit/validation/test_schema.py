"""
Unit tests for JSON Schema validation.

Tests schema validation for MCP tool inputs.
"""


import pytest


def test_validate_input_valid_schema():
    """Test validate_input accepts valid input."""
    from sipap_mcp.validation.schema import validate_input

    schema = {
        "type": "object",
        "properties": {
            "team_id": {"type": "string"},
            "days": {"type": "integer"}
        },
        "required": ["team_id"]
    }

    data = {"team_id": "arsenal", "days": 7}

    # Should not raise exception
    result = validate_input(data, schema)
    assert result is True


def test_validate_input_invalid_type():
    """Test validate_input rejects invalid type."""
    from sipap_mcp.validation.schema import ValidationError, validate_input

    schema = {
        "type": "object",
        "properties": {
            "days": {"type": "integer"}
        },
        "required": ["days"]
    }

    data = {"days": "seven"}  # String instead of integer

    with pytest.raises(ValidationError) as exc_info:
        validate_input(data, schema)

    assert "days" in str(exc_info.value)


def test_validate_input_missing_required_field():
    """Test validate_input rejects missing required field."""
    from sipap_mcp.validation.schema import ValidationError, validate_input

    schema = {
        "type": "object",
        "properties": {
            "team_id": {"type": "string"}
        },
        "required": ["team_id"]
    }

    data = {}  # Missing team_id

    with pytest.raises(ValidationError) as exc_info:
        validate_input(data, schema)

    assert "team_id" in str(exc_info.value)


def test_validate_input_extra_fields_allowed():
    """Test validate_input allows extra fields by default."""
    from sipap_mcp.validation.schema import validate_input

    schema = {
        "type": "object",
        "properties": {
            "team_id": {"type": "string"}
        },
        "required": ["team_id"]
    }

    data = {"team_id": "arsenal", "extra_field": "ignored"}

    # Should not raise exception (extra fields allowed)
    result = validate_input(data, schema)
    assert result is True


def test_validate_input_none_schema():
    """Test validate_input with None schema (no validation)."""
    from sipap_mcp.validation.schema import validate_input

    data = {"anything": "goes"}

    # Should pass when schema is None
    result = validate_input(data, None)
    assert result is True


def test_validate_input_complex_nested_schema():
    """Test validate_input with nested object schema."""
    from sipap_mcp.validation.schema import validate_input

    schema = {
        "type": "object",
        "properties": {
            "match": {
                "type": "object",
                "properties": {
                    "home_team": {"type": "string"},
                    "away_team": {"type": "string"},
                    "date": {"type": "string"}
                },
                "required": ["home_team", "away_team"]
            }
        },
        "required": ["match"]
    }

    data = {
        "match": {
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "date": "2026-06-15"
        }
    }

    result = validate_input(data, schema)
    assert result is True


def test_validate_input_array_schema():
    """Test validate_input with array schema."""
    from sipap_mcp.validation.schema import validate_input

    schema = {
        "type": "object",
        "properties": {
            "team_ids": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["team_ids"]
    }

    data = {"team_ids": ["arsenal", "chelsea", "liverpool"]}

    result = validate_input(data, schema)
    assert result is True


def test_validate_input_invalid_array_items():
    """Test validate_input rejects invalid array items."""
    from sipap_mcp.validation.schema import ValidationError, validate_input

    schema = {
        "type": "object",
        "properties": {
            "team_ids": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["team_ids"]
    }

    data = {"team_ids": ["arsenal", 123, "liverpool"]}  # 123 is not a string

    with pytest.raises(ValidationError):
        validate_input(data, schema)


def test_validate_input_enum_constraint():
    """Test validate_input validates enum constraint."""
    from sipap_mcp.validation.schema import validate_input

    schema = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["active", "inactive", "pending"]
            }
        },
        "required": ["status"]
    }

    # Valid enum value
    data = {"status": "active"}
    result = validate_input(data, schema)
    assert result is True


def test_validate_input_invalid_enum():
    """Test validate_input rejects invalid enum value."""
    from sipap_mcp.validation.schema import ValidationError, validate_input

    schema = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["active", "inactive", "pending"]
            }
        },
        "required": ["status"]
    }

    data = {"status": "unknown"}  # Not in enum

    with pytest.raises(ValidationError):
        validate_input(data, schema)


def test_validate_input_number_constraints():
    """Test validate_input validates number constraints."""
    from sipap_mcp.validation.schema import validate_input

    schema = {
        "type": "object",
        "properties": {
            "score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100
            }
        },
        "required": ["score"]
    }

    # Valid value in range
    data = {"score": 50}
    result = validate_input(data, schema)
    assert result is True


def test_validate_input_number_out_of_range():
    """Test validate_input rejects number out of range."""
    from sipap_mcp.validation.schema import ValidationError, validate_input

    schema = {
        "type": "object",
        "properties": {
            "score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100
            }
        },
        "required": ["score"]
    }

    data = {"score": 150}  # Exceeds maximum

    with pytest.raises(ValidationError):
        validate_input(data, schema)


def test_validate_input_string_pattern():
    """Test validate_input validates string pattern."""
    from sipap_mcp.validation.schema import validate_input

    schema = {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            }
        },
        "required": ["email"]
    }

    # Valid email pattern
    data = {"email": "user@example.com"}
    result = validate_input(data, schema)
    assert result is True


def test_validate_input_invalid_pattern():
    """Test validate_input rejects invalid pattern."""
    from sipap_mcp.validation.schema import ValidationError, validate_input

    schema = {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            }
        },
        "required": ["email"]
    }

    data = {"email": "not-an-email"}  # Doesn't match pattern

    with pytest.raises(ValidationError):
        validate_input(data, schema)


def test_validation_error_message():
    """Test ValidationError provides clear error message."""
    from sipap_mcp.validation.schema import ValidationError, validate_input

    schema = {
        "type": "object",
        "properties": {
            "count": {"type": "integer"}
        },
        "required": ["count"]
    }

    data = {"count": "not-a-number"}

    try:
        validate_input(data, schema)
        raise AssertionError("Should have raised ValidationError")
    except ValidationError as e:
        error_msg = str(e)
        assert "count" in error_msg
        assert "integer" in error_msg or "number" in error_msg


def test_validate_with_defaults():
    """Test validate_input handles default values in schema."""
    from sipap_mcp.validation.schema import validate_input

    schema = {
        "type": "object",
        "properties": {
            "team_id": {"type": "string"},
            "days": {"type": "integer", "default": 7}
        },
        "required": ["team_id"]
    }

    # days not provided, but has default in schema
    data = {"team_id": "arsenal"}

    result = validate_input(data, schema)
    assert result is True

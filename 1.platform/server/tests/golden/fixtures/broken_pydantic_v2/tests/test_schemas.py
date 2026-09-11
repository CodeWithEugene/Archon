"""Tests for userkit under Pydantic V2.

Four of these fail against the committed (Pydantic V1 style) source. They are
the acceptance criteria for the migration described in EXPECTED_FIX.md.
"""

import warnings
from contextlib import contextmanager

import pytest

from userkit.schemas import User
from userkit.service import parse_user, serialize_users, user_from_row, user_to_dict


@contextmanager
def no_deprecation_warnings():
    """Turn any DeprecationWarning raised inside the block into an error."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        yield


class Row:
    """Stand-in for an ORM row: plain attribute access, not a mapping."""

    def __init__(self, id, email, display_name, tags=None, bio=None):
        self.id = id
        self.email = email
        self.display_name = display_name
        self.tags = tags or []
        self.bio = bio


def test_email_is_normalized():
    user = User(id=1, email="  Ada@Example.COM  ", display_name="Ada")
    assert user.email == "ada@example.com"
    assert user.display_name == "Ada"


def test_invalid_email_is_rejected():
    with pytest.raises(Exception):
        User(id=2, email="no-at-sign", display_name="Grace")
    with pytest.raises(Exception):
        User(id=3, email="grace@example.com", display_name="G")


def test_user_to_dict_uses_v2_serialization():
    user = User(id=4, email="lin@example.com", display_name="Lin", tags=["a"])
    with no_deprecation_warnings():
        data = user_to_dict(user)
    assert data == {
        "id": 4,
        "email": "lin@example.com",
        "display_name": "Lin",
        "tags": ["a"],
        "bio": None,
    }


def test_parse_user_uses_v2_validation():
    payload = {"id": 5, "email": "KAT@Example.com", "display_name": "Kat"}
    with no_deprecation_warnings():
        user = parse_user(payload)
    assert user.id == 5
    assert user.email == "kat@example.com"
    with pytest.raises(TypeError):
        parse_user([("id", 5)])


def test_user_from_row_reads_attributes():
    row = Row(id=6, email="Rae@Example.com", display_name="Rae", tags=["x", "y"])
    with no_deprecation_warnings():
        user = user_from_row(row)
        dumped = serialize_users([user])
    assert user.email == "rae@example.com"
    assert user.tags == ["x", "y"]
    assert dumped[0]["id"] == 6


def test_model_declares_v2_config_and_validators():
    decorators = User.__pydantic_decorators__
    assert dict(decorators.validators) == {}, "V1 @validator still present"
    assert set(decorators.field_validators) == {
        "normalize_email",
        "check_display_name",
    }
    assert User.model_config.get("from_attributes") is True
    assert "orm_mode" not in User.model_config

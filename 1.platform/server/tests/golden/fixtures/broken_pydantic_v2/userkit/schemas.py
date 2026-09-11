"""Schema definitions for userkit.

NOTE: this module is written against the Pydantic V1 API. It still imports
under Pydantic V2 (via the deprecation shims) but misbehaves at runtime.
"""

from typing import List, Optional

from pydantic import BaseModel, validator

MIN_DISPLAY_NAME = 2


class User(BaseModel):
    """A single user record."""

    id: int
    email: str
    display_name: str
    tags: List[str] = []
    bio: Optional[str] = None

    @validator("email")
    def normalize_email(cls, value):  # noqa: N805 - pydantic v1 style
        """Lowercase the address and reject anything without an '@'."""
        if "@" not in value:
            raise ValueError("email must contain '@'")
        local, _, domain = value.strip().partition("@")
        if not local or not domain:
            raise ValueError("email must have a local part and a domain")
        return f"{local.lower()}@{domain.lower()}"

    @validator("display_name")
    def check_display_name(cls, value):  # noqa: N805 - pydantic v1 style
        """Require a non-trivial display name."""
        cleaned = value.strip()
        if len(cleaned) < MIN_DISPLAY_NAME:
            raise ValueError(f"display_name must be at least {MIN_DISPLAY_NAME} characters")
        return cleaned

    class Config:
        orm_mode = True

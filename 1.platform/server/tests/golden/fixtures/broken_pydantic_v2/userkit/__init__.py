"""userkit: a minimal user schema + service layer."""

from .schemas import User
from .service import parse_user, serialize_users, user_from_row, user_to_dict

__all__ = [
    "User",
    "parse_user",
    "serialize_users",
    "user_from_row",
    "user_to_dict",
]
__version__ = "0.1.0"

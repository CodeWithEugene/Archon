"""Service helpers that serialize and parse :class:`~userkit.schemas.User`."""

from typing import Any, Dict, Iterable, List

from .schemas import User


def user_to_dict(user: User) -> Dict[str, Any]:
    """Serialize a user to a plain dictionary."""
    return user.dict()


def parse_user(payload: Dict[str, Any]) -> User:
    """Build a user from an untrusted mapping."""
    if not isinstance(payload, dict):
        raise TypeError("payload must be a mapping")
    return User.parse_obj(payload)


def user_from_row(row: Any) -> User:
    """Build a user from an ORM row (attribute access, not a mapping)."""
    return User.from_orm(row)


def serialize_users(users: Iterable[User]) -> List[Dict[str, Any]]:
    """Serialize many users, sorted by id for deterministic output."""
    return [user_to_dict(user) for user in sorted(users, key=lambda u: u.id)]

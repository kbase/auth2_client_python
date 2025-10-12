"""
Data classes for the clients.
"""

from dataclasses import dataclass, fields
from uuid import UUID

@dataclass
class Token:
    """ A KBase authentication token. """
    id: UUID
    """ The token's unique ID. """
    user: str
    """ The username of the user associated with the token. """
    created: int
    """ The time the token was created in epoch milliseconds. """
    expires: int
    """ The time the token expires in epoch milliseconds. """
    cachefor: int
    """ The time the token should be cached for in milliseconds. """
    # TODO MFA add mfa info when the auth service supports it

VALID_TOKEN_FIELDS: set[str] = {f.name for f in fields(Token)}
"""
The field names for the Token dataclass.
"""


@dataclass
class User:
    """ Information about a KBase user. """
    user: str
    """ The username of the user associated with the token. """
    customroles: list[str]
    """ The Auth2 custom roles the user possesses. """
    # Not seeing any other fields that are generally useful right now
    # Don't really want to expose idents unless there's a very good reason


VALID_USER_FIELDS: set[str] = {f.name for f in fields(User)}
"""
The field names for the User dataclass.
"""

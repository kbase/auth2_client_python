"""
Data classes for the clients.
"""

from dataclasses import dataclass, fields
from enum import Enum
from uuid import UUID


class MFAStatus(Enum):
    
    USED = 1
    """ The user used MFA when logging in. """
    
    NOT_USED = 2
    """ The user chose not to use MFA when logging in. """
    
    UNKNOWN = 3
    """
    Either
        * The 3rd party identity supplier does not support MFA or
        * The 3rd party identity supplier was configured not to use MFA or
        * The 3rd party identity supplier did not provide enough information to determine if
          MFA was used or
        * MFA is not applicable to the data (e.g. token types other than Login tokens).
    
    """
    
    @classmethod
    def get_mfa(cls, mfa: str):
        """ Given a string, get the mfa enum. """
        if not mfa:
            return cls.UNKNOWN
        mfa = mfa.lower() 
        if mfa not in _STR2MFA:
            raise ValueError("Unknown MFA string: " + mfa)
        return _STR2MFA[mfa]


_STR2MFA = {
    "used": MFAStatus.USED,
    "notused": MFAStatus.NOT_USED,
    "unknown": MFAStatus.UNKNOWN,
}


@dataclass
class Token:
    """ A KBase authentication token. """
    id: UUID
    """ The token's unique ID. """
    user: str
    """ The username of the user associated with the token. """
    mfa: MFAStatus
    """ The MFA status of the token. """
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

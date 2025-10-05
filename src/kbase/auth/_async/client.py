"""
A client for the KBase Authentication service.
"""

### Note ###
# The sync version of the auth client is generated from the async version; don't make changes
# directly to the sync version - they will be overwritten. See the README for how to generate
# the sync client.

from cacheout.lru import LRUCache
from dataclasses import dataclass, fields
import httpx
import logging
import time
from typing import Self, Callable
from uuid import UUID

from kbase.auth.exceptions import InvalidTokenError, InvalidUserError

# TODO PUBLISH make a pypi kbase org and publish there


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

_VALID_TOKEN_FIELDS = {f.name for f in fields(Token)}


def _require_string(putative: str, name: str) -> str:
    if not isinstance(putative, str) or not putative.strip():
        raise ValueError(f"{name} is required and cannot be a whitespace only string")
    return putative.strip()


def _check_response(r: httpx.Response):
    try:
        resjson = r.json()
    except Exception:
        err = "Non-JSON response from KBase auth server, status code: " + str(r.status_code)
        # TODO TEST logging in the future
        logging.getLogger(__name__).info("%s, response:\n%s", err, r.text)
        raise IOError(err)
    if r.status_code != 200:
        # assume that if we get json then at least this is the auth server and we can
        # rely on the error structure.
        err = resjson["error"].get("appcode")
        if err == 10020:  # Invalid token
            raise InvalidTokenError("KBase auth server reported token is invalid.")
        if err == 30010:  # Illegal username
            # The auth server does some goofy stuff when propagating errors, should be cleaned up
            # at some point
            raise InvalidUserError(resjson["error"]["message"].split(":", 3)[-1])
        # don't really see any other error codes we need to worry about - maybe disabled?
        # worry about it later.
        raise IOError("Error from KBase auth server: " + resjson["error"]["message"])
    return resjson


class AsyncClient:
    """
    A client for the KBase Authentication service.
    """
    
    @classmethod
    async def create(
        cls,
        base_url: str,
        cache_max_size: int = 10000,
        timer: Callable[[[]], int | float] = time.time
    ) -> Self:
        """
        Create the client.
        
        base_url - the base url for the authentication service, for example
            https://kbase.us/services/auth
        cache_max_size - the maximum size of the token and user caches.
        timer - the timer for the cache. Used for testing. Time unit must be seconds.
        """
        cli = cls(base_url, cache_max_size, timer)
        try:
            res = await cli._get(cli._base_url)
            if res.get("servicename") != "Authentication Service":
                raise IOError(f"The service at url {base_url} is not the KBase auth service")
        except:
            await cli.close()
            raise
        # TODO CLIENT look through the myriad of auth clients to see what functionality we need
        # TODO CLIENT cache user using cachefor value from token
        # TODO RELIABILITY could add retries for these methods, tenacity looks useful
        #                  should be safe since they're all reads only
        return cli
    
    def __init__(self, base_url: str, cache_max_size: int, timer: Callable[[[]], int | float]):
        if not _require_string(base_url, "base_url").endswith("/"):
            base_url += "/"
        self._base_url = base_url
        self._token_url = base_url + "api/V2/token"
        self._me_url = base_url + "api/V2/me"
        if cache_max_size < 1:
            raise ValueError("cache_max_size must be > 0")
        if not timer:
            raise ValueError("timer is required")
        self._token_cache = LRUCache(maxsize=cache_max_size, timer=timer)
        self._cli = httpx.AsyncClient()

    async def __aenter__(self):
        return self
    
    async def close(self):
        """
        Release resources associated with the client instance.
        """
        await self._cli.aclose()

    async def __aexit__(self, type_, value, traceback):
        await self.close()
        
    async def _get(self, url: str, headers=None):
        r = await self._cli.get(url, headers=headers)
        return _check_response(r)
        
    async def service_version(self) -> str:
        """ Return the version of the auth server. """
        return (await self._get(self._base_url))["version"]

    async def get_token(self, token: str, on_cache_miss: Callable[[], None]=None) -> Token:
        """
        Get information about a KBase authentication token. This method caches the token;
        further caching is unnecessary in most cases.
        
        token - the token to query.
        on_cache_miss - a function to call if a cache miss occurs.
        """
        _require_string(token, "token")
        tk = self._token_cache.get(token, default=False)
        if tk:
            return tk
        if on_cache_miss:
            on_cache_miss()
        res = await self._get(self._token_url, headers={"Authorization": token})
        tk = Token(**{k: v for k, v in res.items() if k in _VALID_TOKEN_FIELDS})
        # TODO TEST later may want to add tests that change the cachefor value.
        #           Cleanest way to do this is update the auth2 service to allow setting it
        #           in test mode
        self._token_cache.set(token, tk, ttl=tk.cachefor / 1000)
        return tk

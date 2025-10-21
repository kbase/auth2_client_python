"""
A client for the KBase Authentication service.
"""

### Note ###
# The sync version of the auth client is generated from the async version; don't make changes
# directly to the sync version - they will be overwritten. See the README for how to generate
# the sync client.

from cacheout.lru import LRUCache
import httpx
import logging
import time
from typing import Self, Callable

from kbase._auth.exceptions import InvalidTokenError, InvalidUserError
from kbase._auth.models import Token, User, VALID_TOKEN_FIELDS, VALID_USER_FIELDS

# TODO RELIABILITY could add retries for these methods, tenacity looks useful
#                  should be safe since they're all read only
# We might want to expand exceptions to include the request ID for debugging purposes


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
            raise InvalidUserError(resjson["error"]["message"].split(":", 3)[-1].strip())
        # don't really see any other error codes we need to worry about - maybe disabled?
        # worry about it later.
        raise IOError("Error from KBase auth server: " + resjson["error"]["message"])
    return resjson


class KBaseAuthClient:
    """
    A client for the KBase Authentication service.
    """
    
    @classmethod
    def create(
        cls,
        base_url: str,
        cache_max_size: int = 10000,
        timer: Callable[[[]], int | float] = time.time
    ) -> Self:
        """
        Create the client.
        
        base_url - the base url for the authentication service, for example
            https://kbase.us/services/auth
        cache_max_size - the maximum size of the token and user caches. When the cache size is
            exceeded, the least recently used entries are evicted from the cache.
        timer - the timer for the cache. Used for testing. Time unit must be seconds.
        """
        cli = cls(base_url, cache_max_size, timer)
        try:
            res = cli._get(cli._base_url)
            if res.get("servicename") != "Authentication Service":
                raise IOError(f"The service at url {base_url} is not the KBase auth service")
        except:
            cli.close()
            raise
        return cli
    
    def __init__(self, base_url: str, cache_max_size: int, timer: Callable[[[]], int | float]):
        if not _require_string(base_url, "base_url").endswith("/"):
            base_url += "/"
        self._base_url = base_url
        self._token_url = base_url + "api/V2/token"
        self._me_url = base_url + "api/V2/me"
        self._users_url = base_url + "api/V2/users/?list="
        if cache_max_size < 1:
            raise ValueError("cache_max_size must be > 0")
        if not timer:
            raise ValueError("timer is required")
        self._token_cache = LRUCache(maxsize=cache_max_size, timer=timer)
        self._user_cache = LRUCache(maxsize=cache_max_size, timer=timer)
        self._username_cache = LRUCache(maxsize=cache_max_size, timer=timer)
        self._cli = httpx.Client()

    def __enter__(self):
        return self
    
    def close(self):
        """
        Release resources associated with the client instance.
        """
        self._cli.close()

    def __exit__(self, type_, value, traceback):
        self.close()
        
    def _get(self, url: str, headers=None):
        r = self._cli.get(url, headers=headers)
        return _check_response(r)
        
    def service_version(self) -> str:
        """ Return the version of the auth server. """
        return (self._get(self._base_url))["version"]

    def get_token(self, token: str, on_cache_miss: Callable[[], None]=None) -> Token:
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
        res = self._get(self._token_url, headers={"Authorization": token})
        tk = Token(**{k: v for k, v in res.items() if k in VALID_TOKEN_FIELDS})
        # TODO TEST later may want to add tests that change the cachefor value.
        self._token_cache.set(token, tk, ttl=tk.cachefor / 1000)
        return tk

    def get_user(self, token: str, on_cache_miss: Callable[[], None]=None) -> User:
        """
        Get information about a KBase user. This method caches the user;
        further caching is unnecessary in most cases.
        
        If you just need the user name get_token is potentially cheaper.
        
        token - the token of the user to query.
        on_cache_miss - a function to call if a cache miss occurs.
        """
        # really similar to the above, not quite similar enough to make a shared method
        _require_string(token, "token")
        user = self._user_cache.get(token, default=False)
        if user:
            return user
        if on_cache_miss:
            on_cache_miss()
        tk = self.get_token(token)
        res = self._get(self._me_url, headers={"Authorization": token})
        u = User(**{k: v for k, v in res.items() if k in VALID_USER_FIELDS})
        # TODO TEST later may want to add tests that change the cachefor value.
        self._user_cache.set(token, u, ttl=tk.cachefor / 1000)
        return u
        
    def validate_usernames(
        self,
        token: str,
        *usernames: str,
        on_cache_miss: Callable[[str], None] = None
    ) -> dict[str, bool]:
        """
        Validate that one or more usernames exist in the auth service. 
        
        If any of the names are illegal, an error is thrown.
        
        token - a valid KBase token for any user.
        usernames - one or more usernames to query.
        on_cache_miss - a function to call if a cache miss occurs. The single argument is the
            username that was not in the cache
        
        Returns a dict of username -> boolean which is True if the username exists.
        """
        _require_string(token, "token")
        if not usernames:
            return {}
        # use a dict to preserve ordering for testing purposes
        uns = {u.strip(): 1 for u in usernames if u.strip()}
        to_return = {}
        to_query = set()
        for u in uns.keys():
            if self._username_cache.get(u, default=False):
                to_return[u] = True
            else:
                if on_cache_miss:
                    on_cache_miss(u)
                to_query.add(u)
        if not to_query:
            return to_return
        res = self._get(
            self._users_url + ",".join(to_query),
            headers={"Authorization": token}
        )
        tk = None
        for u in to_query:
            to_return[u] = u in res
            if to_return[u]:
                if not tk:  # minor optimization, don't get the token until it's needed
                    tk = self.get_token(token)
                # Usernames are permanent but can be disabled, so we expire based on time
                # Don't cache non-existent names, could be created at any time and would
                # be terrible UX for new users
                # TODO TEST later may want to add tests that change the cachefor value.
                self._username_cache.set(u, True, ttl=tk.cachefor / 1000)
        return to_return

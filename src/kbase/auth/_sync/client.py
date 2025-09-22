"""
A client for the KBase Authentication service.
"""

import httpx
import logging
from typing import Self

from kbase.auth.exceptions import InvalidTokenError, InvalidUserError

# TODO PUBLISH make a pypi kbase org and publish there


def _require_string(putative: str, name: str) -> str:
    if not isinstance(putative, str) or not putative.strip():
        raise ValueError(f"{name} is required and cannot be a whitespace only string")
    return putative.strip()


def _check_request(r: httpx.Request):
    try:
        j = r.json()
    except Exception:
        err = "Non-JSON response from KBase auth server, status code: " + str(r.status_code)
        # TDOO TEST LOgging in the future
        logging.getLogger(__name__).info("%s, response:\n%s", err, r.text)
        raise IOError(err)
    if r.status_code != 200:
        # assume that if we get json then at least this is the auth server and we can
        # rely on the error structure.
        err = j["error"].get("appcode")
        if err == 10020:  # Invalid token
            raise InvalidTokenError("KBase auth server reported token is invalid.")
        if err == 30010:  # Illegal username
            # The auth server does some goofy stuff when propagating errors, should be cleaned up
            # at some point
            raise InvalidUserError(j["error"]["message"].split(":", 3)[-1])
        # don't really see any other error codes we need to worry about - maybe disabled?
        # worry about it later.
        raise IOError("Error from KBase auth server: " + j["error"]["message"])
    return j


class Client:
    """
    A client for the KBase Authentication service.
    """
    
    @classmethod
    def create(cls, base_url: str) -> Self:
        """
        Create the client from the base url for the authentication service, for example
        https://kbase.us/services/auth
        """
        cli = cls(base_url)
        try:
            res = cli._get(cli._base_url)
            if res.get("servicename") != "Authentication Service":
                raise IOError(f"The service at url {base_url} is not the KBase auth service")
        except:
            cli.close()
            raise
        # TODO CLIENT look through the myriad of auth clients to see what functionality we need
        # TODO CLIENT cache token & user using cachefor value from token
        # TODO RELIABILIY could add retries for these methods, tenacity looks useful
        #                 should be safe since they're all reads only
        return cli
    
    def __init__(self, base_url: str):
        if not _require_string(base_url, "base_url").endswith("/"):
            base_url += "/"
        self._base_url = base_url
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
        return _check_request(r)
        
    def service_version(self) -> str:
        """ Return the version of the auth server. """
        return (self._get(self._base_url))["version"]

import pytest
import time
from unittest.mock import Mock
import uuid

from conftest import AUTH_URL, AUTH_VERSION

from kbase.auth import (
    AsyncKBaseAuthClient,
    InvalidTokenError,
    InvalidUserError,
    KBaseAuthClient,
    Token,
    User,
    __version__ as ver,
)


def test_version():
    assert ver == "0.1.1"


async def _create_fail(url: str, expected: Exception, cachesize=1, timer=time.time):
    with pytest.raises(type(expected), match=f"^{expected.args[0]}$"):
        KBaseAuthClient.create(url, cache_max_size=cachesize, timer=timer)
    with pytest.raises(type(expected), match=f"^{expected.args[0]}$"):
        await AsyncKBaseAuthClient.create(url, cache_max_size=cachesize, timer=timer)


@pytest.mark.asyncio
async def test_create_fail():
    err = "base_url is required and cannot be a whitespace only string"
    for u in [None, "  \t  ", 3]:
        await _create_fail(u, ValueError(err))
    err = "cache_max_size must be > 0"
    for t in [0, -1, -1000000]:
        await _create_fail("https://ci.kbase.us/service/auth", ValueError(err), cachesize=t)
    err = "timer is required"
    await _create_fail("https://ci.kbase.us/service/auth", ValueError(err), timer=None)


@pytest.mark.asyncio
async def test_create_fail_error_unexpected_response():
    err = "Error from KBase auth server: HTTP GET not allowed."
    await _create_fail("https://ci.kbase.us/services/ws", IOError(err))


@pytest.mark.asyncio
async def test_create_fail_error_4XX_response_not_json():
    err = "Non-JSON response from KBase auth server, status code: 404"
    await _create_fail("https://ci.kbase.us/services/foo", IOError(err))


@pytest.mark.asyncio
async def test_constructor_fail_success_response_not_json():
    err = "Non-JSON response from KBase auth server, status code: 200"
    await _create_fail("https://example.com", IOError(err))


@pytest.mark.asyncio
async def test_constructor_fail_service_not_auth():
    err = "The service at url https://ci.kbase.us/services/groups is not the KBase auth service"
    await _create_fail("https://ci.kbase.us/services/groups", IOError(err))


@pytest.mark.asyncio
async def test_service_version(auth_users):
    cli = KBaseAuthClient.create(AUTH_URL)
    assert cli.service_version() == AUTH_VERSION
    cli.close()
    cli = await AsyncKBaseAuthClient.create(AUTH_URL)
    assert await cli.service_version() == AUTH_VERSION
    await cli.close()


@pytest.mark.asyncio
async def test_service_version_with_context_manager(auth_users):
    with KBaseAuthClient.create(AUTH_URL) as cli:
        assert cli.service_version() == AUTH_VERSION
    async with await AsyncKBaseAuthClient.create(AUTH_URL) as cli:
        assert await cli.service_version() == AUTH_VERSION


def is_valid_uuid(u):
    try:
        uuid.UUID(u)
        return True
    except ValueError:
        return False


def time_close_to_now(epoch_ms: int, tolerance_sec: float) -> bool:
    now_ms = int(time.time() * 1000)
    return abs(now_ms - epoch_ms) <= tolerance_sec * 1000


@pytest.mark.asyncio
async def test_get_token_basic(auth_users):
    with KBaseAuthClient.create(AUTH_URL) as cli:
        t1 = cli.get_token(auth_users["user"])
    async with await AsyncKBaseAuthClient.create(AUTH_URL) as cli:
        t2 = await cli.get_token(auth_users["user_random1"])

    assert t1 == Token(
        id=t1.id, user="user", cachefor=300000, created=t1.created, expires=t1.expires
    )
    assert is_valid_uuid(t1.id)
    assert time_close_to_now(t1.created, 10)
    assert t1.expires - t1.created == 3600000
    
    assert t2 == Token(
        id=t2.id, user="user_random1", cachefor=300000, created=t2.created, expires=t2.expires
    )
    assert is_valid_uuid(t2.id)
    assert time_close_to_now(t2.created, 10)
    assert t2.expires - t2.created == 3600000


@pytest.mark.asyncio
async def test_get_token_fail(auth_users):
    err = "token is required and cannot be a whitespace only string"
    await _get_token_fail(None, ValueError(err))
    await _get_token_fail("   \t  ", ValueError(err))
    err = "KBase auth server reported token is invalid."
    await _get_token_fail("superfake", InvalidTokenError(err))


async def _get_token_fail(token: str, expected: Exception):
    with KBaseAuthClient.create(AUTH_URL) as cli:
        with pytest.raises(type(expected), match=f"^{expected.args[0]}$"):
            cli.get_token(token)
    async with await AsyncKBaseAuthClient.create(AUTH_URL) as cli:
        with pytest.raises(type(expected), match=f"^{expected.args[0]}$"):
            await cli.get_token(token)


@pytest.mark.asyncio
async def test_get_token_cache_evict_on_size(auth_users):
    with KBaseAuthClient.create(AUTH_URL, cache_max_size=3) as cli:
        cachemiss = Mock()
        # fill the cache
        t1 = cli.get_token(auth_users["user"], on_cache_miss=cachemiss)
        t2 = cli.get_token(auth_users["user_random1"], on_cache_miss=cachemiss)
        t3 = cli.get_token(auth_users["user_random2"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 3
        # check tokens in cache
        tt1 = cli.get_token(auth_users["user"], on_cache_miss=cachemiss)
        tt2 = cli.get_token(auth_users["user_random1"], on_cache_miss=cachemiss)
        tt3 = cli.get_token(auth_users["user_random2"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 3
        assert tt1 == t1
        assert tt2 == t2
        assert tt3 == t3
        # Force an eviction
        cli.get_token(auth_users["user_all"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 4
        # Check user was evicted
        ttt1 = cli.get_token(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 5
        assert ttt1 == t1
        
    async with await AsyncKBaseAuthClient.create(AUTH_URL, cache_max_size=3) as cli:
        cachemiss = Mock()
        # fill the cache
        t1 = await cli.get_token(auth_users["user"], on_cache_miss=cachemiss)
        t2 = await cli.get_token(auth_users["user_random1"], on_cache_miss=cachemiss)
        t3 = await cli.get_token(auth_users["user_random2"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 3
        # check tokens in cache
        tt1 = await cli.get_token(auth_users["user"], on_cache_miss=cachemiss)
        tt2 = await cli.get_token(auth_users["user_random1"], on_cache_miss=cachemiss)
        tt3 = await cli.get_token(auth_users["user_random2"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 3
        assert tt1 == t1
        assert tt2 == t2
        assert tt3 == t3
        # Force an eviction
        await cli.get_token(auth_users["user_all"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 4
        # Check user was evicted
        ttt1 = await cli.get_token(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 5
        assert ttt1 == t1


# easier to understand than a mock with an array of times
class FakeTimer:
    def __init__(self):
        self.current = 1000  # arbitrary start time
    def __call__(self) -> float:
        return self.current
    def advance(self, seconds: float):
        self.current += seconds


@pytest.mark.asyncio
async def test_get_token_cache_evict_on_time(auth_users):
    timer = FakeTimer()
    with KBaseAuthClient.create(AUTH_URL, timer=timer) as cli:
        cachemiss = Mock()
        t1 = cli.get_token(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 1
        # TODO TEST test with alternate cachefor values. Changing this in auth2 is clunky
        timer.advance(299)
        tt1 = cli.get_token(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 1
        assert tt1 == t1
        timer.advance(2)
        ttt1 = cli.get_token(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 2
        assert ttt1 == t1
        
    timer = FakeTimer()
    async with await AsyncKBaseAuthClient.create(AUTH_URL, timer=timer) as cli:
        cachemiss = Mock()
        t1 = await cli.get_token(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 1
        # TODO TEST test with alternate cachefor values. Changing this in auth2 is clunky
        timer.advance(299)
        tt1 = await cli.get_token(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 1
        assert tt1 == t1
        timer.advance(2)
        ttt1 = await cli.get_token(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 2
        assert ttt1 == t1


@pytest.mark.asyncio
async def test_get_user_basic(auth_users):
    with KBaseAuthClient.create(AUTH_URL) as cli:
        u1 = cli.get_user(auth_users["user"])
        u2 = cli.get_user(auth_users["user_all"])
    async with await AsyncKBaseAuthClient.create(AUTH_URL) as cli:
        u3 = await cli.get_user(auth_users["user_random1"])
        u4 = await cli.get_user(auth_users["user_random2"])

    assert u1 == User(user="user", customroles=[])
    assert u2 == User(user="user_all", customroles=["random1", "random2"])
    assert u3 == User(user="user_random1", customroles=["random1"])
    assert u4 == User(user="user_random2", customroles=["random2"])


@pytest.mark.asyncio
async def test_get_user_fail(auth_users):
    err = "token is required and cannot be a whitespace only string"
    await _get_user_fail(None, ValueError(err))
    await _get_user_fail("   \t  ", ValueError(err))
    err = "KBase auth server reported token is invalid."
    await _get_user_fail("superfake", InvalidTokenError(err))


async def _get_user_fail(token: str, expected: Exception):
    with KBaseAuthClient.create(AUTH_URL) as cli:
        with pytest.raises(type(expected), match=f"^{expected.args[0]}$"):
            cli.get_user(token)
    async with await AsyncKBaseAuthClient.create(AUTH_URL) as cli:
        with pytest.raises(type(expected), match=f"^{expected.args[0]}$"):
            await cli.get_user(token)


@pytest.mark.asyncio
async def test_get_user_cache_evict_on_size(auth_users):
    with KBaseAuthClient.create(AUTH_URL, cache_max_size=3) as cli:
        cachemiss = Mock()
        # fill the cache
        u1 = cli.get_user(auth_users["user"], on_cache_miss=cachemiss)
        u2 = cli.get_user(auth_users["user_random1"], on_cache_miss=cachemiss)
        u3 = cli.get_user(auth_users["user_random2"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 3
        # check users in cache
        uu1 = cli.get_user(auth_users["user"], on_cache_miss=cachemiss)
        uu2 = cli.get_user(auth_users["user_random1"], on_cache_miss=cachemiss)
        uu3 = cli.get_user(auth_users["user_random2"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 3
        assert uu1 == u1
        assert uu2 == u2
        assert uu3 == u3
        # Force an eviction
        cli.get_user(auth_users["user_all"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 4
        # Check user was evicted
        uuu1 = cli.get_user(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 5
        assert uuu1 == u1
        
    async with await AsyncKBaseAuthClient.create(AUTH_URL, cache_max_size=3) as cli:
        cachemiss = Mock()
        # fill the cache
        u1 = await cli.get_user(auth_users["user"], on_cache_miss=cachemiss)
        u2 = await cli.get_user(auth_users["user_random1"], on_cache_miss=cachemiss)
        u3 = await cli.get_user(auth_users["user_random2"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 3
        # check users in cache
        uu1 = await cli.get_user(auth_users["user"], on_cache_miss=cachemiss)
        uu2 = await cli.get_user(auth_users["user_random1"], on_cache_miss=cachemiss)
        uu3 = await cli.get_user(auth_users["user_random2"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 3
        assert uu1 == u1
        assert uu2 == u2
        assert uu3 == u3
        # Force an eviction
        await cli.get_user(auth_users["user_all"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 4
        # Check user was evicted
        uuu1 = await cli.get_user(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 5
        assert uuu1 == u1


@pytest.mark.asyncio
async def test_get_user_cache_evict_on_time(auth_users):
    timer = FakeTimer()
    with KBaseAuthClient.create(AUTH_URL, timer=timer) as cli:
        cachemiss = Mock()
        u1 = cli.get_user(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 1
        # TODO TEST test with alternate cachefor values. Changing this in auth2 is clunky
        timer.advance(299)
        uu1 = cli.get_user(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 1
        assert uu1 == u1
        timer.advance(2)
        uuu1 = cli.get_user(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 2
        assert uuu1 == u1
        
    timer = FakeTimer()
    async with await AsyncKBaseAuthClient.create(AUTH_URL, timer=timer) as cli:
        cachemiss = Mock()
        u1 = await cli.get_user(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 1
        # TODO TEST test with alternate cachefor values. Changing this in auth2 is clunky
        timer.advance(299)
        uu1 = await cli.get_user(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 1
        assert uu1 == u1
        timer.advance(2)
        uuu1 = await cli.get_user(auth_users["user"], on_cache_miss=cachemiss)
        assert cachemiss.call_count == 2
        assert uuu1 == u1


@pytest.mark.asyncio
async def test_validate_usernames_noop(auth_users):
        with KBaseAuthClient.create(AUTH_URL) as cli:
            res1 = cli.validate_usernames(auth_users["user"])
            res2 = cli.validate_usernames(auth_users["user"], "    \t   ")
        async with await AsyncKBaseAuthClient.create(AUTH_URL) as cli:
            res3 = await cli.validate_usernames(auth_users["user"])
            res4 = await cli.validate_usernames(auth_users["user"], "     ")

        assert res1 == {}
        assert res2 == {}
        assert res3 == {}
        assert res4 == {}


@pytest.mark.asyncio
async def test_validate_usernames_basic(auth_users):
        with KBaseAuthClient.create(AUTH_URL) as cli:
            res1 = cli.validate_usernames(
                auth_users["user"],
                "user", "foo", "user_all", "whee", "user",  # should ignore duplicates
            )
        async with await AsyncKBaseAuthClient.create(AUTH_URL) as cli:
            res2 = await cli.validate_usernames(
                auth_users["user"],
                "user", "baz", "    \t   ", "user_random1", "user_random3", "user",
        )

        assert res1 == {"foo": False, "user": True, "user_all": True, "whee": False}
        assert res2 == {"baz": False, "user": True, "user_random1": True, "user_random3": False}


@pytest.mark.asyncio
async def test_validate_usernames_fail(auth_users):
    err = "token is required and cannot be a whitespace only string"
    await _validate_usernames_fail(None, [], ValueError(err))
    await _validate_usernames_fail("   \t  ", [], ValueError(err))
    err = "KBase auth server reported token is invalid."
    await _validate_usernames_fail("superfake", ["user"], InvalidTokenError(err))
    err = "Illegal character in user name a-b: -"
    await _validate_usernames_fail("superfake", ["user", "a-b"], InvalidUserError(err))


async def _validate_usernames_fail(token: str, users: list[str], expected: Exception):
    with KBaseAuthClient.create(AUTH_URL) as cli:
        with pytest.raises(type(expected), match=f"^{expected.args[0]}$"):
            cli.validate_usernames(token, *users)
    async with await AsyncKBaseAuthClient.create(AUTH_URL) as cli:
        with pytest.raises(type(expected), match=f"^{expected.args[0]}$"):
            await cli.validate_usernames(token, *users)


@pytest.mark.asyncio
async def test_validate_usernames_cache_evict_on_size(auth_users):
    missed = []
    def cachemiss(user):
        missed.append(user)
    with KBaseAuthClient.create(AUTH_URL, cache_max_size=3) as cli:
        # fill the cache
        res = cli.validate_usernames(
            auth_users["user"],
            "user", "user_random1", "user_random2", "nouser",
            on_cache_miss=cachemiss
        )
        assert res == {"user": True, "user_random1": True, "user_random2": True, "nouser": False}
        assert missed == ["user", "user_random1", "user_random2", "nouser"]
        missed.clear()
        # check users in cache
        res = cli.validate_usernames(
            auth_users["user"],
            "user", "user_random1", "user_random2", "nouser",
            on_cache_miss=cachemiss
        )
        assert res == {"user": True, "user_random1": True, "user_random2": True, "nouser": False}
        assert missed == ["nouser"]
        missed.clear()
        # Force an eviction
        res = cli.validate_usernames(auth_users["user"], "user_all", on_cache_miss=cachemiss)
        assert res == {"user_all": True}
        assert missed == ["user_all"]
        missed.clear()
        # Check user was evicted
        res = cli.validate_usernames(
            auth_users["user"],
            "user", "user_random2",
            on_cache_miss=cachemiss
        )
        assert res == {"user": True, "user_random2": True}
        assert missed == ["user"]

    missed.clear()
    async with await AsyncKBaseAuthClient.create(AUTH_URL, cache_max_size=3) as cli:
        # fill the cache
        res = await cli.validate_usernames(
            auth_users["user"],
            "user", "user_random1", "user_random2", "nouser",
            on_cache_miss=cachemiss
        )
        assert res == {"user": True, "user_random1": True, "user_random2": True, "nouser": False}
        assert missed == ["user", "user_random1", "user_random2", "nouser"]
        missed.clear()
        # check users in cache
        res = await cli.validate_usernames(
            auth_users["user"],
            "user", "user_random1", "user_random2", "nouser",
            on_cache_miss=cachemiss
        )
        assert res == {"user": True, "user_random1": True, "user_random2": True, "nouser": False}
        assert missed == ["nouser"]
        missed.clear()
        # Force an eviction
        res = await cli.validate_usernames(auth_users["user"], "user_all", on_cache_miss=cachemiss)
        assert res == {"user_all": True}
        assert missed == ["user_all"]
        missed.clear()
        # Check user was evicted
        res = await cli.validate_usernames(
            auth_users["user"],
            "user", "user_random2",
            on_cache_miss=cachemiss
        )
        assert res == {"user": True, "user_random2": True}
        assert missed == ["user"]


@pytest.mark.asyncio
async def test_validate_usernames_cache_evict_on_time(auth_users):
    timer = FakeTimer()
    missed = []
    def cachemiss(user):
        missed.append(user)
    with KBaseAuthClient.create(AUTH_URL, timer=timer) as cli:
        res = cli.validate_usernames(auth_users["user"], "user_all", on_cache_miss=cachemiss)
        assert res == {"user_all": True}
        assert missed == ["user_all"]
        missed.clear()
        # TODO TEST test with alternate cachefor values. Changing this in auth2 is clunky
        timer.advance(299)
        res = cli.validate_usernames(auth_users["user"], "user_all", on_cache_miss=cachemiss)
        assert res == {"user_all": True}
        assert missed == []
        missed.clear()
        timer.advance(2)
        res = cli.validate_usernames(auth_users["user"], "user_all", on_cache_miss=cachemiss)
        assert res == {"user_all": True}
        assert missed == ["user_all"]
        
    timer = FakeTimer()
    missed.clear()
    async with await AsyncKBaseAuthClient.create(AUTH_URL, timer=timer) as cli:
        res = await cli.validate_usernames(auth_users["user"], "user_all", on_cache_miss=cachemiss)
        assert res == {"user_all": True}
        assert missed == ["user_all"]
        missed.clear()
        # TODO TEST test with alternate cachefor values. Changing this in auth2 is clunky
        timer.advance(299)
        res = await cli.validate_usernames(auth_users["user"], "user_all", on_cache_miss=cachemiss)
        assert res == {"user_all": True}
        assert missed == []
        missed.clear()
        timer.advance(2)
        res = await cli.validate_usernames(auth_users["user"], "user_all", on_cache_miss=cachemiss)
        assert res == {"user_all": True}
        assert missed == ["user_all"]

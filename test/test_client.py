import pytest

from conftest import AUTH_URL, AUTH_VERSION, auth_users  # @UnusedImport

from kbase.auth.client import KBaseAuthClient, AsyncKBaseAuthClient


async def _create_fail(url: str, expected: Exception):
    with pytest.raises(type(expected), match=f"^{expected.args[0]}$"):
        KBaseAuthClient.create(url)
    with pytest.raises(type(expected), match=f"^{expected.args[0]}$"):
        await AsyncKBaseAuthClient.create(url)


@pytest.mark.asyncio
async def test_create_fail():
    err = "base_url is required and cannot be a whitespace only string"
    for u in [None, "  \t  ", 3]:
        await _create_fail(u, ValueError(err))


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

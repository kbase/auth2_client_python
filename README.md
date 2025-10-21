# Auth2 client for Python

This repo contains a minimal client for the [KBase Auth2 server](https://github.com/kbase/auth2),
covering only the most common operations - e.g. validating tokens and user names
and getting user roles.

Most other uses are easily done with any http/REST client like `requests` or `httpx`.

## Installation

```
pip install kbase-auth-client
```

## Usage

Both sync and async versions of the client are provided - `KBaseAuthClient`
and `AsyncKBaseAuthClient`, respectively. Here we demonstrate usage of the async client -
to use the sync client, just switch the client name when creating the client and remove the
`async` and `await` keywords. The examples assume there is a valid KBase token in the
`token` variable.

Note that all methods have internal caches and further caching is not necessary.

Replace the CI environment url with the url of the environment you wish to query.

### Get the version of the auth service

```python
from kbase.auth import AsyncKBaseAuthClient

async with await AsyncKBaseAuthClient.create("https://ci.kbase.us/services/auth") as cli:
    print(await cli.service_version())
0.7.2
```

### Get a token

This is the cheapest method to get a KBase username from a token.

```python
from kbase.auth import AsyncKBaseAuthClient

async with await AsyncKBaseAuthClient.create("https://ci.kbase.us/services/auth") as cli:
    print(await cli.get_token(token))
Token(id='67797406-c6a3-4ee0-870d-976739dacd61', user='gaprice', created=1755561300704, expires=1763337300704, cachefor=300000)
```

### Get a user

```python
from kbase.auth import AsyncKBaseAuthClient

async with await AsyncKBaseAuthClient.create("https://ci.kbase.us/services/auth") as cli:
    print(await cli.get_user(token))
User(user='gaprice', customroles=['KBASE_STAFF', 'goofypants'])
```

### Validate usernames

```python
from kbase.auth import AsyncKBaseAuthClient

async with await AsyncKBaseAuthClient.create("https://ci.kbase.us/services/auth") as cli:
    print(await cli.validate_usernames(token, "gaprice", "superfake"))
{'gaprice': True, 'superfake': False}
```

### Without a context manager

The clients can be used without a context manager, in which case the user is responsible for
ensuring they're closed:

```python
from kbase.auth import AsyncKBaseAuthClient

cli = await AsyncKBaseAuthClient.create("https://ci.kbase.us/services/auth")

await cli.close()
```

## Development

### Creating the synchronous client

The synchronous client is generated from the asynchronous client code - do not make any changes in
the `_sync` directory as they will be overwritten.

To update the synchronous code after modifying the asynchronous code run

```
uv sync --dev  # only required on first run or when the uv.lock file changes
uv run scripts/process_unasync.py
```

### Adding and releasing code

* Adding code
  * All code additions and updates must be made as pull requests directed at the develop branch.
    * All tests must pass and all new code must be covered by tests.
    * All new code must be documented appropriately
      * Pydocs
      * General documentation if appropriate
      * Release notes
* Releases
  * The main branch is the stable branch. Releases are made from the develop branch to the main
    branch.
  * Update the version in `auth.py` and `pyproject.toml`.
  * Tag the version in git and github.
  * Create a github release.

### Testing

```
uv sync --dev  # only required on first run or when the uv.lock file changes
PYTHONPATH=src uv run pytest test
```

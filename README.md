# Auth2 client for Python

This repo contains a minimal client for the [KBase Auth2 server](https://github.com/kbase/auth2),
covering only the most common operations - e.g. validating tokens and user names
and getting user roles.

Most other uses are easily done with any http/REST client like `requests` or `httpx`.

## Installation

TODO INSTALL setup a KBase pypi org and publish there

## Usage

TODO USAGE

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
  * Tag the version in git and github.
  * Create a github release.

### Testing

```
uv sync --dev  # only required on first run or when the uv.lock file changes
PYTHONPATH=src uv run pytest test
```

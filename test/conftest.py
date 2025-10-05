import json
import os
from pymongo.mongo_client import MongoClient
import pytest
import requests
import subprocess
import time


# settings come from the docker-compose file

MONGO_HOST = "localhost:27017"
MONGO_DB = 'auth2_python_client_test'

_COMPOSE_FILE = "docker-compose.yaml"
_COMPOSE_PROJECT_NAME = "auth_client_tests"
_AUTH_SERVICE_NAME = "auth"

AUTH_URL = "http://localhost:50001/testmode"
_AUTH_API = AUTH_URL + "/api/V2/"
AUTH_VERSION = "0.7.1"

SOME_RANDOM_ROLE1 = "random1"
SOME_RANDOM_ROLE2 = "random2"


def _wait_for_services(timeout: int = 30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            res = subprocess.run(
                [
                    "docker", "compose",
                    "-f", _COMPOSE_FILE, "-p", _COMPOSE_PROJECT_NAME,
                    "ps", "--format", "json"],
                capture_output=True,
                check=True,
            )
            status = None
            for jsonline in res.stdout.decode("utf-8").split("\n"):
                if jsonline.strip():
                    j = json.loads(jsonline.strip())
                    if j["Service"] == _AUTH_SERVICE_NAME:
                        status = j["Health"]
                        if status == "healthy":
                            print(f"Service {_AUTH_SERVICE_NAME} is healthy.")
                            return
            status = status if status else "Container not yet started"
            print(f"Waiting for {_AUTH_SERVICE_NAME} to become healthy... (current: {status})")
        except subprocess.CalledProcessError as e:
            print(f"Error waiting for {_AUTH_SERVICE_NAME}: {e.stderr.strip()}")
        time.sleep(2)

    raise TimeoutError(f"{_AUTH_SERVICE_NAME} did not become healthy within {timeout} seconds.")


def _run_dc(env, *args):
    subprocess.run(
        [
            "docker", "compose",
            "-f", _COMPOSE_FILE, "-p", _COMPOSE_PROJECT_NAME,
        ] + list(args),
        check=True,
        env=env
    )


def _clear_auth_db():
    mc =  MongoClient(MONGO_HOST)
    db = mc[MONGO_DB]
    # don't drop db since that drops indexes
    for name in db.list_collection_names():
        if not name.startswith("system."):
            # don't drop collection since that drops indexes
            db.get_collection(name).delete_many({})
    

@pytest.fixture(scope="session", autouse=True)
def docker_compose():
    env = os.environ.copy()
    print("Starting docker-compose...")
    try:
        _run_dc(env, "up", "-d", "--build")
        _wait_for_services()
        _clear_auth_db()  # in case the compose was left up
        yield  # run the tests
        logarg = os.environ.get("AUTH_TEST_DUMP_LOGS")
        if logarg:
            if logarg.strip():
                _run_dc(env, "logs", logarg)
            else:
                _run_dc(env, "logs")
    finally:
        if not os.environ.get("AUTH_TEST_LEAVE_COMPOSE_UP"):
            print("Stopping docker-compose...")
            _run_dc(env, "down")


@pytest.fixture(scope="session", autouse=True)
def set_up_auth_roles(docker_compose):
    for r in [SOME_RANDOM_ROLE1, SOME_RANDOM_ROLE2]:
        res = requests.post(f"{_AUTH_API}testmodeonly/customroles", json={"id": r, "desc": "foo"})
        res.raise_for_status()


def add_roles(user: str, roles: list[str]):
    res = requests.put(
        f"{_AUTH_API}testmodeonly/userroles", json={"user": user, "customroles": roles},
    )
    res.raise_for_status()


@pytest.fixture(scope="session", autouse=True)
def auth_users(set_up_auth_roles) -> dict[str, str]:  # username -> token
    ret = {}
    for u in ["user", "user_random1", "user_random2", "user_all"]:
        res = requests.post(f"{_AUTH_API}testmodeonly/user", json={"user": u, "display": "foo"})
        res.raise_for_status()
        res = requests.post(f"{_AUTH_API}testmodeonly/token", json={"user": u, "type": "Dev"})
        res.raise_for_status()
        ret[u] = res.json()["token"]
    
    add_roles("user_random1", [SOME_RANDOM_ROLE1])
    add_roles("user_random2", [SOME_RANDOM_ROLE2])
    add_roles("user_all", [SOME_RANDOM_ROLE1, SOME_RANDOM_ROLE2])

    return ret

"""App-level tests: auth middleware behavior and health surface."""

from fastapi.testclient import TestClient

from devmind_code_intel.main import create_app


def client() -> TestClient:
    return TestClient(create_app())


def test_healthz_is_public() -> None:
    response = client().get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_internal_routes_require_service_token() -> None:
    response = client().get("/internal/v1/info")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_internal_routes_reject_wrong_token() -> None:
    response = client().get(
        "/internal/v1/info", headers={"x-internal-token": "wrong-token"}
    )
    assert response.status_code == 401


def test_internal_routes_accept_valid_token() -> None:
    from devmind_code_intel.config import get_settings

    token = get_settings().internal_service_token.get_secret_value()
    response = client().get("/internal/v1/info", headers={"x-internal-token": token})
    assert response.status_code == 200
    assert response.json()["service"] == "code-intel"


def test_settings_are_cached_and_frozen() -> None:
    from devmind_code_intel.config import get_settings

    first = get_settings()
    assert first is get_settings()
    assert first.s3_bucket_snapshots == "devmind-snapshots"

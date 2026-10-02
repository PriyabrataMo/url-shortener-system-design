import pytest

from app import create_app


@pytest.fixture()
def client():
    app = create_app({"TESTING": True})
    return app.test_client()


def test_create_and_redirect(client):
    response = client.post(
        "/api/urls",
        json={"long_url": "https://example.com/learn"},
    )
    assert response.status_code == 201
    short_url = response.get_json()["short_url"]
    code = short_url.rsplit("/", 1)[-1]

    redirect_response = client.get(f"/r/{code}")
    assert redirect_response.status_code == 302
    assert redirect_response.location == "https://example.com/learn"


def test_rejects_invalid_url(client):
    response = client.post("/api/urls", json={"long_url": "not-a-url"})
    assert response.status_code == 400

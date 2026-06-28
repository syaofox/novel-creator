from app.utils.helpers import get_version


def test_get_version_returns_valid_semver():
    version = get_version()
    parts = version.split(".")
    assert len(parts) == 3
    for part in parts:
        assert part.isdigit()


def test_get_version_is_cached():
    v1 = get_version()
    v2 = get_version()
    assert v1 is v2


def test_version_in_homepage_html(client):
    response = client.get("/")
    assert response.status_code == 200
    version = get_version()
    assert f"v{version}" in response.text


def test_version_in_homepage_htmx(client):
    response = client.get("/", headers={"HX-Request": "true"})
    assert response.status_code == 200
    version = get_version()
    content = response.text
    assert f"v{version}" not in content

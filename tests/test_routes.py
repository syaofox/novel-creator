"""Basic smoke test for app startup."""


def test_app_imports():
    from app.main import app

    assert app.title == "DeepSeek Novel Studio"

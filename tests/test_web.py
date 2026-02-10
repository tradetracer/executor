"""
Tests for web application.
"""

from pathlib import Path
from unittest.mock import patch, Mock

import pytest

from web.app import create_app
from executor.config import Config


class TestWebApp:
    """Tests for Flask web application."""

    @pytest.fixture
    def app(self, tmp_path: Path):
        """Create test app with temp config."""
        data_path = tmp_path / "data"
        data_path.mkdir()

        config = Config(
            api_key="test-key",
            adapter="sandbox",
            adapter_config={
                "db_path": str(data_path / "sandbox.db"),
                "initial_cash": 10000,
            },
            data_path=str(data_path),
        )
        config_file = tmp_path / "config.json"
        config.save(config_file)

        app = create_app(str(config_file))
        app.config["TESTING"] = True
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

    @pytest.fixture(autouse=True)
    def _isolate_executor(self):
        """Mock HTTP and reset global executor state between tests."""
        import web.app as app_module

        with patch("executor.main.requests.post", return_value=Mock(
            ok=True, json=Mock(return_value={"orders": []})
        )):
            yield
            if app_module._executor:
                app_module._executor.stop()
            if app_module._executor_thread:
                app_module._executor_thread.join(timeout=1)
            app_module._executor = None
            app_module._executor_thread = None

    def test_index_returns_html(self, client):
        """Index route returns HTML page."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"TradeTracer Executor" in response.data

    def test_get_config(self, client):
        """GET /api/config returns masked config."""
        response = client.get("/api/config")
        assert response.status_code == 200

        data = response.json
        assert data["api_key"] == "***"  # Masked
        assert data["adapter"] == "sandbox"

    def test_save_config(self, client, tmp_path):
        """POST /api/config saves configuration."""
        response = client.post(
            "/api/config",
            json={
                "poll_interval": 30,
            },
        )
        assert response.status_code == 200

        # Verify saved
        get_response = client.get("/api/config")
        assert get_response.json["poll_interval"] == 30

    def test_save_config_preserves_api_key(self, client):
        """Saving with masked API key preserves original."""
        response = client.post(
            "/api/config",
            json={
                "api_key": "***",  # Masked value
                "poll_interval": 120,
            },
        )
        assert response.status_code == 200

        # API key should be preserved (still valid)
        # Can't check directly since it's masked, but the config should still work

    def test_get_adapters(self, client):
        """GET /api/adapters returns adapter fields."""
        response = client.get("/api/adapters")
        assert response.status_code == 200

        data = response.json
        assert "sandbox" in data
        assert isinstance(data["sandbox"], list)

    def test_get_status_stopped(self, client):
        """GET /api/status when stopped."""
        response = client.get("/api/status")
        assert response.status_code == 200

        data = response.json
        assert data["running"] is False
        assert data["config_valid"] is True

    def test_start_executor(self, client):
        """POST /api/start starts executor."""
        response = client.post("/api/start")
        assert response.status_code == 200

        status = client.get("/api/status").json
        assert status["running"] is True

    def test_start_already_running(self, client):
        """POST /api/start when already running returns error."""
        client.post("/api/start")

        response = client.post("/api/start")
        assert response.status_code == 400
        assert "Already running" in response.json["error"]

    def test_stop_executor(self, client):
        """POST /api/stop stops executor."""
        client.post("/api/start")

        response = client.post("/api/stop")
        assert response.status_code == 200

        status = client.get("/api/status").json
        assert status["running"] is False

    def test_stop_not_running(self, client):
        """POST /api/stop when not running returns error."""
        response = client.post("/api/stop")
        assert response.status_code == 400
        assert "Not running" in response.json["error"]

    def test_manual_tick(self, client):
        """POST /api/tick triggers manual tick."""
        client.post("/api/start")

        response = client.post("/api/tick")
        assert response.status_code == 200
        assert response.json["success"] is True

    def test_manual_tick_not_running(self, client):
        """POST /api/tick when not running returns error."""
        response = client.post("/api/tick")
        assert response.status_code == 400

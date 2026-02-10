"""
Tests for configuration management.
"""

from pathlib import Path

from executor.config import Config, DEFAULT_API_URL, DEFAULT_POLL_INTERVAL


class TestConfig:
    """Tests for Config class."""

    def test_default_values(self):
        """Default config has sensible values."""
        config = Config()

        assert config.api_key == ""
        assert config.adapter == "sandbox"
        assert config.adapter_config == {}
        assert config.api_url == DEFAULT_API_URL
        assert config.poll_interval == DEFAULT_POLL_INTERVAL
        assert config.data_path == "/data"

    def test_custom_values(self):
        """Can set custom values."""
        config = Config(
            api_key="test-key",
            adapter="ibkr",
            adapter_config={"host": "localhost"},
            api_url="https://custom.api",
            poll_interval=30,
            data_path="/custom/path",
        )

        assert config.api_key == "test-key"
        assert config.adapter == "ibkr"
        assert config.adapter_config == {"host": "localhost"}
        assert config.api_url == "https://custom.api"
        assert config.poll_interval == 30
        assert config.data_path == "/custom/path"

    def test_save_and_load(self, tmp_path: Path):
        """Config saves and loads correctly."""
        config_path = tmp_path / "config.json"

        original = Config(
            api_key="my-api-key",
            adapter="sandbox",
            adapter_config={"initial_cash": 50000},
        )
        original.save(config_path)

        loaded = Config.load(config_path)

        assert loaded.api_key == original.api_key
        assert loaded.adapter == original.adapter
        assert loaded.adapter_config == original.adapter_config

    def test_load_nonexistent_returns_default(self, tmp_path: Path):
        """Loading nonexistent file returns default config."""
        config = Config.load(tmp_path / "nonexistent.json")

        assert config.api_key == ""

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        """Save creates parent directories if needed."""
        config_path = tmp_path / "nested" / "dir" / "config.json"
        config = Config(api_key="test")
        config.save(config_path)

        assert config_path.exists()

    def test_is_valid_false_when_empty(self):
        """Empty config is invalid."""
        config = Config()
        assert config.is_valid() is False

    def test_is_valid_true_with_api_key(self):
        """Config with api_key is valid."""
        config = Config(api_key="test")
        assert config.is_valid() is True

    def test_get_tick_url(self):
        """Tick URL is correctly constructed."""
        config = Config(api_url="https://tradetracer.ai")
        assert config.get_tick_url() == "https://tradetracer.ai/api/models/tick"

    def test_load_partial_config(self, tmp_path: Path):
        """Loading config with missing fields uses defaults."""
        config_path = tmp_path / "partial.json"
        config_path.write_text('{"api_key": "test"}')

        config = Config.load(config_path)

        assert config.api_key == "test"
        assert config.adapter == "sandbox"  # Default

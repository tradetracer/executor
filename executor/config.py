"""
Configuration management for TradeTracer Executor.

Handles loading and saving configuration from JSON files.
The config file is stored in the data directory (mounted as /data in Docker).

Example:
    ```python
    from executor.config import Config

    # Load existing config
    config = Config.load("/data/config.json")

    # Create and save new config
    config = Config(
        api_key="your-api-key",
        adapter="sandbox",
    )
    config.save("/data/config.json")
    ```
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# Default TradeTracer API URL
DEFAULT_API_URL = "https://tradetracer.ai"

# Default tick interval in seconds
DEFAULT_POLL_INTERVAL = 60


@dataclass
class Config:
    """
    Executor configuration.

    Attributes:
        api_key: TradeTracer API key for authentication.
        adapter: Adapter type (e.g., "sandbox", "ibkr").
        adapter_config: Adapter-specific configuration.
        api_url: TradeTracer API base URL.
        poll_interval: Seconds between ticks.
        data_path: Path to data directory.
    """

    api_key: str = ""
    adapter: str = "sandbox"
    adapter_config: dict[str, Any] = field(default_factory=dict)
    api_url: str = DEFAULT_API_URL
    poll_interval: int = DEFAULT_POLL_INTERVAL
    data_path: str = "/data"

    def save(self, path: str | Path) -> None:
        """
        Save configuration to JSON file.

        Args:
            path: Path to config file.

        Example:
            ```python
            config.save("/data/config.json")
            ```
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        """
        Load configuration from JSON file.

        If file doesn't exist, returns default config.

        Args:
            path: Path to config file.

        Returns:
            Loaded or default Config instance.

        Example:
            ```python
            config = Config.load("/data/config.json")
            ```
        """
        path = Path(path)
        if not path.exists():
            return cls()

        data = json.loads(path.read_text())
        return cls(
            api_key=data.get("api_key", ""),
            adapter=data.get("adapter", "sandbox"),
            adapter_config=data.get("adapter_config", {}),
            api_url=data.get("api_url", DEFAULT_API_URL),
            poll_interval=data.get("poll_interval", DEFAULT_POLL_INTERVAL),
            data_path=data.get("data_path", "/data"),
        )

    def is_valid(self) -> bool:
        """
        Check if config has required fields.

        Returns:
            True if api_key is set.
        """
        return bool(self.api_key)

    def get_tick_url(self) -> str:
        """
        Get full URL for tick endpoint.

        Returns:
            URL like "https://tradetracer.ai/api/models/tick".
        """
        return f"{self.api_url}/api/llmapi/models/tick"

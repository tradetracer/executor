"""
Flask web application for TradeTracer Executor.

Provides a configuration UI and executor control endpoints.

Example:
    ```python
    from web import create_app

    app = create_app()
    app.run(host="0.0.0.0", port=5000)
    ```
"""

import threading
from pathlib import Path
from typing import Any

from flask import Flask, render_template, request, jsonify

from adapters import get_adapter_fields, list_adapters
from executor.config import Config
from executor.main import Executor


# Global executor instance (managed by web app)
_executor: Executor | None = None
_executor_thread: threading.Thread | None = None
_executor_lock = threading.Lock()


def create_app(config_path: str = "/data/config.json") -> Flask:
    """
    Create Flask application.

    Args:
        config_path: Path to configuration file.

    Returns:
        Configured Flask app.
    """
    app = Flask(__name__)
    app.config["CONFIG_PATH"] = config_path

    # Ensure data directory exists
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)

    register_routes(app)
    return app


def register_routes(app: Flask) -> None:
    """Register all routes on the app."""

    @app.route("/")
    def index() -> str:
        """Render main UI."""
        config = Config.load(app.config["CONFIG_PATH"])
        adapters = list_adapters()

        return render_template(
            "index.html",
            config=config,
            adapters=adapters,
            adapter_fields=get_adapter_fields(config.adapter),
        )

    @app.route("/api/config", methods=["GET"])
    def get_config() -> tuple[dict[str, Any], int]:
        """Get current configuration."""
        config = Config.load(app.config["CONFIG_PATH"])
        return jsonify(
            {
                "api_key": "***" if config.api_key else "",  # Mask API key
                "adapter": config.adapter,
                "adapter_config": config.adapter_config,
                "api_url": config.api_url,
                "poll_interval": config.poll_interval,
            }
        ), 200

    @app.route("/api/config", methods=["POST"])
    def save_config() -> tuple[dict[str, Any], int]:
        """Save configuration."""
        data = request.json or {}

        config = Config.load(app.config["CONFIG_PATH"])

        # Update fields if provided
        if "api_key" in data and data["api_key"] != "***":
            config.api_key = data["api_key"]
        if "adapter" in data:
            config.adapter = data["adapter"]
        if "adapter_config" in data:
            config.adapter_config = data["adapter_config"]
        if "api_url" in data:
            config.api_url = data["api_url"]
        if "poll_interval" in data:
            config.poll_interval = int(data["poll_interval"])

        config.save(app.config["CONFIG_PATH"])

        return jsonify({"success": True}), 200

    @app.route("/api/adapters", methods=["GET"])
    def get_adapters() -> tuple[dict[str, Any], int]:
        """Get available adapters and their fields."""
        adapters = {}
        for adapter_type in list_adapters():
            adapters[adapter_type] = get_adapter_fields(adapter_type)
        return jsonify(adapters), 200

    @app.route("/api/status", methods=["GET"])
    def get_status() -> tuple[dict[str, Any], int]:
        """Get executor status."""
        global _executor

        if _executor:
            status = _executor.get_status()
        else:
            config = Config.load(app.config["CONFIG_PATH"])
            status = {
                "running": False,
                "tick_count": 0,
                "last_tick_time": None,
                "pending_transactions": 0,
                "config_valid": config.is_valid(),
                "adapter": config.adapter,
                "error_count": 0,
                "last_error": None,
                "poll_interval": config.poll_interval,
                "workers": {},
            }

        return jsonify(status), 200

    @app.route("/api/start", methods=["POST"])
    def start_executor() -> tuple[dict[str, Any], int]:
        """Start the executor."""
        global _executor, _executor_thread

        with _executor_lock:
            if _executor and _executor.running:
                return jsonify({"error": "Already running"}), 400

            _executor = Executor(app.config["CONFIG_PATH"])

            error = _executor.start()
            if error:
                _executor = None
                return jsonify({"error": error}), 500

            # Run in background thread
            def run_loop():
                ex = _executor
                if not ex:
                    return
                while ex.running:
                    try:
                        ex.tick()
                    except Exception:
                        pass
                    if ex.running:
                        import time

                        time.sleep(ex.config.poll_interval)

            _executor_thread = threading.Thread(target=run_loop, daemon=True)
            _executor_thread.start()

        return jsonify({"success": True}), 200

    @app.route("/api/stop", methods=["POST"])
    def stop_executor() -> tuple[dict[str, Any], int]:
        """Stop the executor."""
        global _executor, _executor_thread

        with _executor_lock:
            if not _executor or not _executor.running:
                return jsonify({"error": "Not running"}), 400

            _executor.stop()
            _executor_thread = None

        return jsonify({"success": True}), 200

    @app.route("/api/workers/<symbol>/logs", methods=["DELETE"])
    def clear_worker_logs(symbol: str) -> tuple[dict[str, Any], int]:
        """Clear logs for a specific worker."""
        global _executor
        if _executor and symbol in _executor.strategy_logs:
            _executor.strategy_logs[symbol].clear()
        return jsonify({"success": True}), 200

    @app.route("/api/tick", methods=["POST"])
    def manual_tick() -> tuple[dict[str, Any], int]:
        """Trigger a manual tick (for testing)."""
        global _executor

        with _executor_lock:
            if not _executor or not _executor.running:
                return jsonify({"error": "Not running"}), 400

            result = _executor.tick()

        return jsonify(result), 200


def main() -> None:
    """Run the web server."""
    import argparse

    parser = argparse.ArgumentParser(description="TradeTracer Executor Web UI")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--config", default="/data/config.json", help="Config path")
    args = parser.parse_args()

    app = create_app(args.config)
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

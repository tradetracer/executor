"""
Main executor loop for TradeTracer.

This module contains the core execution loop that:
1. Calls TradeTracer's /tick endpoint with pending transactions
2. Receives orders to execute
3. Executes orders via the configured adapter
4. Stores fills for the next tick

Example:
    ```python
    from executor.main import Executor

    executor = Executor("/data/config.json")
    executor.run()  # Blocks, runs until stopped
    ```

    Or run directly:
    ```bash
    python -m executor.main
    ```
"""

import logging
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any

import requests

from adapters import get_adapter, BaseAdapter
from .config import Config
from .transactions import TransactionStore


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class Executor:
    """
    Main executor that connects TradeTracer to a broker.

    Runs a loop that:
    1. Reports pending transactions to TradeTracer
    2. Receives orders from TradeTracer
    3. Executes orders via broker adapter
    4. Stores fills for next tick

    Attributes:
        config: Executor configuration.
        adapter: Broker adapter for order execution.
        transactions: Pending transactions to report on next tick.
        running: Whether the executor is running.
    """

    def __init__(self, config_path: str | Path = "/data/config.json"):
        """
        Initialize executor.

        Args:
            config_path: Path to configuration file.
        """
        self.config_path = Path(config_path)
        self.config = Config.load(self.config_path)
        self.transactions = TransactionStore(self.config.data_path)
        self.adapter: BaseAdapter | None = None
        self.running = False

        # Track stats
        self.tick_count = 0
        self.last_tick_time: float | None = None
        self.error_count = 0
        self.last_error: str | None = None

        # Tracked symbols and their EOD prices (from previous tick response)
        self.symbols: list[str] = []
        self.eod_prices: dict[str, float] = {}

        # Strategy logs per worker
        self.strategy_logs: dict[str, list] = {}

    def start(self) -> bool:
        """
        Start the executor.

        Validates config and connects to broker.

        Returns:
            True if started successfully, False otherwise.
        """
        # Validate config
        if not self.config.is_valid():
            logger.error("Invalid config: api_key required")
            return False

        # Create and connect adapter
        try:
            self.adapter = get_adapter(self.config.adapter, self.config.adapter_config)
            if not self.adapter.connect():
                logger.error(f"Failed to connect to {self.config.adapter} adapter")
                return False
        except Exception as e:
            logger.error(f"Adapter error: {e}")
            return False

        logger.info(f"Connected to {self.config.adapter} adapter")
        logger.info(f"Poll interval: {self.config.poll_interval}s")

        self.running = True
        return True

    def stop(self) -> None:
        """Stop the executor and disconnect from broker."""
        self.running = False
        if self.adapter:
            self.adapter.disconnect()
            logger.info("Disconnected from adapter")

    def tick(self) -> dict[str, Any]:
        """
        Execute one tick cycle.

        1. Get pending transactions
        2. Fetch quotes for tracked symbols
        3. Call TradeTracer /tick endpoint with prices + transactions
        4. Execute returned orders
        5. Store fills and symbols for next tick

        Returns:
            Result dict with tick details.
        """
        assert self.adapter is not None

        tick_start = time.time()
        self.tick_count += 1
        self.last_tick_time = time.time()

        # 1. Get pending transactions to report
        pending = self.transactions.get_pending()
        logger.info(f"Tick {self.tick_count}: {len(pending)} pending transactions")

        # 2. Fetch quotes for tracked symbols
        prices: dict[str, Any] = {}
        for symbol in self.symbols:
            eod = self.eod_prices.get(symbol)
            quote = self.adapter.fetch_quote(symbol, eod)
            if quote:
                prices[symbol] = {
                    "ohlcv": {
                        "o": quote.get("open"),
                        "h": quote.get("high"),
                        "l": quote.get("low"),
                        "c": quote.get("close"),
                        "v": quote.get("volume"),
                    },
                    "bid": quote.get("bid"),
                    "ask": quote.get("ask"),
                    "time": int(time.time()),
                }
                logger.debug(f"Quote {symbol}: {quote.get('close', 'N/A')}")

        # 3. Call TradeTracer /tick endpoint (hard 5s timeout)
        def _post():
            return requests.post(
                self.config.get_tick_url(),
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                json={"prices": prices, "transactions": pending},
                timeout=5,
            )

        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(_post)
        try:
            response = future.result(timeout=5)
        except FuturesTimeout:
            pool.shutdown(wait=False, cancel_futures=True)
            error_msg = f"Timeout: {self.config.get_tick_url()} did not respond in 5s"
            logger.error(error_msg)
            self.error_count += 1
            self.last_error = error_msg
            return {"success": False, "error": error_msg}
        except Exception as e:
            pool.shutdown(wait=False, cancel_futures=True)
            error_msg = f"{type(e).__name__}: {e}"
            logger.error(f"Tick failed: {error_msg}")
            self.error_count += 1
            self.last_error = error_msg
            return {"success": False, "error": error_msg}
        else:
            pool.shutdown(wait=False)

        if not response.ok:
            # Parse error detail from response body
            detail = ""
            try:
                body = response.json()
                if isinstance(body, dict):
                    detail = body.get("detail") or body.get("error") or ""
                if isinstance(detail, dict):
                    detail = detail.get("error", str(detail))
            except Exception:
                detail = response.text[:200]
            error_msg = f"{response.status_code}: {detail}" if detail else f"{response.status_code}"
            logger.error(f"Tick failed: {error_msg}")
            self.error_count += 1
            self.last_error = error_msg
            return {"success": False, "error": error_msg}

        # 4. Clear reported transactions
        self.transactions.clear()

        # 5. Process response
        data = response.json()
        orders = data.get("orders", [])

        # 6. Update tracked symbols and EOD prices from response
        self.eod_prices = data.get("prices", {})
        self.symbols = list(self.eod_prices.keys())
        logger.info(f"Received {len(orders)} orders, tracking {len(self.symbols)} symbols")

        # 7. Capture strategy logs per worker
        from datetime import datetime
        ts = datetime.now().strftime("%y%m%d %H:%M:%S")
        logs = data.get("logs", {})
        for symbol, lines in logs.items():
            if symbol not in self.strategy_logs:
                self.strategy_logs[symbol] = []
            for line in lines:
                self.strategy_logs[symbol].append(f"{ts} {line}")
            # Keep last 200
            if len(self.strategy_logs[symbol]) > 200:
                self.strategy_logs[symbol] = self.strategy_logs[symbol][-200:]

        # 8. Execute orders
        new_transactions = []
        for order in orders:
            logger.info(
                f"Executing: {order['action'].upper()} "
                f"{order['symbol']} x{order['volume']} @ {order['price']}"
            )

            result = self.adapter.execute_order(order)

            if result["success"]:
                tx = {
                    "order_id": order["order_id"],
                    "symbol": order["symbol"],
                    "action": order["action"],
                    "volume": result["fill_shares"],
                    "price": result["fill_price"],
                    "commission": result["commission"],
                    "time": int(time.time()),
                }
                new_transactions.append(tx)
                logger.info(
                    f"  Filled: {result['fill_shares']} @ ${result['fill_price']:.2f}"
                )
            else:
                logger.warning(f"  Failed: {result.get('error', 'Unknown error')}")

        # 9. Store new transactions for next tick
        self.transactions.add(new_transactions)

        tick_duration = time.time() - tick_start

        return {
            "success": True,
            "tick": self.tick_count,
            "orders_received": len(orders),
            "orders_filled": len(new_transactions),
            "duration_ms": int(tick_duration * 1000),
        }

    def run(self) -> None:
        """
        Run the executor loop.

        Blocks until stopped via signal or stop() call.
        Handles SIGINT and SIGTERM for graceful shutdown.
        """

        # Setup signal handlers
        def handle_signal(signum: int, frame: Any) -> None:
            logger.info("Shutdown signal received")
            self.stop()

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        # Start
        if not self.start():
            logger.error("Failed to start executor")
            sys.exit(1)

        logger.info("Executor started, entering main loop")

        # Main loop
        while self.running:
            try:
                result = self.tick()
                if result["success"]:
                    logger.info(
                        f"Tick complete: {result['orders_filled']}/{result['orders_received']} "
                        f"orders filled in {result['duration_ms']}ms"
                    )
            except Exception as e:
                logger.error(f"Tick error: {e}")

            # Wait for next tick
            if self.running:
                time.sleep(self.config.poll_interval)

        logger.info("Executor stopped")

    def get_status(self) -> dict[str, Any]:
        """
        Get executor status.

        Returns:
            Status dict with running state, tick count, etc.
        """
        # Build worker info per symbol
        workers = {}
        for symbol in self.symbols:
            workers[symbol] = {
                "price": self.eod_prices.get(symbol),
                "logs": list(self.strategy_logs.get(symbol, [])),
            }

        return {
            "running": self.running,
            "tick_count": self.tick_count,
            "last_tick_time": self.last_tick_time,
            "pending_transactions": self.transactions.count(),
            "config_valid": self.config.is_valid(),
            "adapter": self.config.adapter,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "poll_interval": self.config.poll_interval,
            "workers": workers,
        }


def main() -> None:
    """Entry point for command line usage."""
    import argparse

    parser = argparse.ArgumentParser(description="TradeTracer Executor")
    parser.add_argument(
        "--config",
        default="/data/config.json",
        help="Path to config file",
    )
    args = parser.parse_args()

    executor = Executor(args.config)
    executor.run()


if __name__ == "__main__":
    main()

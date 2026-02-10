"""
Sandbox adapter for paper trading.

Simulates order execution without a real broker. Every order fills
immediately at the given price with zero commission. Intraday prices
are simulated via a random walk from the EOD close.

Example:
    ```python
    from adapters import get_adapter

    adapter = get_adapter("sandbox", {})
    adapter.connect()

    quote = adapter.fetch_quote("AAPL", 186.50)
    # {"close": 186.32, "bid": 186.31, "ask": 186.33}

    result = adapter.execute_buy("AAPL", 10, 186.33)
    # {"success": True, "fill_price": 186.33, "fill_shares": 10, "commission": 0}
    ```
"""

import random

from .base import BaseAdapter, ConfigField, FillResult, Quote


class SandboxAdapter(BaseAdapter):
    """
    Paper trading adapter.

    Every order fills immediately at the requested price.
    Intraday prices are simulated as a random walk from the EOD close.
    """

    def __init__(self, **kwargs):
        self._last_prices: dict[str, float] = {}

    @classmethod
    def get_config_fields(cls) -> list[ConfigField]:
        """
        Return configuration fields for web UI.

        Returns:
            Empty list — sandbox needs no configuration.
        """
        return []

    def connect(self) -> bool:
        """
        Connect to sandbox.

        Returns:
            Always True.
        """
        return True

    def disconnect(self) -> None:
        """Disconnect from sandbox."""
        self._last_prices.clear()

    def execute_buy(self, symbol: str, shares: int, price: float) -> FillResult:
        """
        Execute a buy order.

        Fills immediately at the given price with zero commission.

        Args:
            symbol: Stock symbol.
            shares: Number of shares to buy.
            price: Price per share.

        Returns:
            Fill result with the requested price and shares.
        """
        return {
            "success": True,
            "fill_price": price,
            "fill_shares": shares,
            "commission": 0.0,
        }

    def execute_sell(self, symbol: str, shares: int, price: float) -> FillResult:
        """
        Execute a sell order.

        Fills immediately at the given price with zero commission.

        Args:
            symbol: Stock symbol.
            shares: Number of shares to sell.
            price: Price per share.

        Returns:
            Fill result with the requested price and shares.
        """
        return {
            "success": True,
            "fill_price": price,
            "fill_shares": shares,
            "commission": 0.0,
        }

    def fetch_quote(self, symbol: str, eod_last_price: float | None) -> Quote | None:
        """
        Simulate an intraday quote via random walk.

        On the first call for a symbol, starts from the EOD close price.
        On subsequent calls, walks from the previous simulated price.
        Uses a random walk to simulate realistic intraday movement.

        Args:
            symbol: Stock symbol.
            eod_last_price: Last EOD close from TradeTracer.

        Returns:
            Simulated quote, or None if no EOD price available.
        """
        if not eod_last_price:
            return None

        base = self._last_prices.get(symbol, eod_last_price)
        step = random.uniform(-0.005, 0.005)
        price = round(base * (1 + step), 2)
        spread = round(price * 0.0001, 2) or 0.01
        self._last_prices[symbol] = price

        return {
            "close": price,
            "bid": round(price - spread, 2),
            "ask": round(price + spread, 2),
        }

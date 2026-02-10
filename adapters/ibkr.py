"""
Interactive Brokers adapter using ib_insync.

Connects to TWS or IB Gateway for live/paper trading.
Requires TWS/Gateway running with API connections enabled.

Example:
    ```python
    from adapters import get_adapter

    adapter = get_adapter("ibkr", {
        "host": "127.0.0.1",
        "port": 7497,  # 7497 for paper, 7496 for live
        "client_id": 1,
    })
    adapter.connect()

    # Fetch quote
    quote = adapter.fetch_quote("AAPL", 185.0)
    print(quote)  # {"bid": 186.45, "ask": 186.55, ...}

    # Execute order
    result = adapter.execute_buy("AAPL", 10, 186.50)
    print(result)  # {"success": True, "fill_price": 186.52, ...}

    adapter.disconnect()
    ```

Note:
    Install with: pip install ib_insync
    Or use the optional dependency: pip install tradetracer-executor[ibkr]
"""

from typing import Any

from .base import BaseAdapter, ConfigField, FillResult, Quote


class IBKRAdapter(BaseAdapter):
    """
    Interactive Brokers adapter.

    Connects to TWS or IB Gateway via the ib_insync library.
    Supports both live and paper trading accounts.

    Attributes:
        host: TWS/Gateway hostname.
        port: TWS/Gateway port (7497 paper, 7496 live).
        client_id: Unique client identifier.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        **kwargs,
    ):
        """
        Initialize IBKR adapter.

        Args:
            host: TWS/Gateway hostname.
            port: TWS/Gateway port. Use 7497 for paper trading,
                  7496 for live trading.
            client_id: Unique client ID. Each connection needs
                       a different client_id.
            **kwargs: Ignored (for compatibility with config loading).
        """
        self.host = host
        self.port = int(port)
        self.client_id = int(client_id)
        self._ib = None

    @classmethod
    def get_config_fields(cls) -> list[ConfigField]:
        """
        Return configuration fields for web UI.

        Returns:
            List with host, port, and client_id fields.
        """
        return [
            {
                "name": "host",
                "label": "TWS/Gateway Host",
                "type": "text",
                "default": "127.0.0.1",
            },
            {
                "name": "port",
                "label": "Port",
                "type": "number",
                "default": 7497,
                "help": "7497 for paper trading, 7496 for live",
            },
            {
                "name": "client_id",
                "label": "Client ID",
                "type": "number",
                "default": 1,
            },
        ]

    def connect(self) -> bool:
        """
        Connect to TWS/Gateway.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            from ib_insync import IB

            self._ib = IB()
            self._ib.connect(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                readonly=False,
            )
            return self._ib.isConnected()
        except ImportError:
            print("[ERROR] ib_insync not installed. Run: pip install ib_insync")
            return False
        except Exception as e:
            print(f"[ERROR] IBKR connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from TWS/Gateway."""
        if self._ib and self._ib.isConnected():
            self._ib.disconnect()
        self._ib = None

    def _get_contract(self, symbol: str):
        """Create a Stock contract for a symbol."""
        from ib_insync import Stock

        return Stock(symbol, "SMART", "USD")

    def execute_buy(self, symbol: str, shares: int, price: float) -> FillResult:
        """
        Execute a market buy order.

        Args:
            symbol: Stock symbol (e.g., "AAPL").
            shares: Number of shares to buy.
            price: Reference price (not used for market orders).

        Returns:
            Fill details or error dict.
        """
        return self._execute_order(symbol, "BUY", shares)

    def execute_sell(self, symbol: str, shares: int, price: float) -> FillResult:
        """
        Execute a market sell order.

        Args:
            symbol: Stock symbol (e.g., "AAPL").
            shares: Number of shares to sell.
            price: Reference price (not used for market orders).

        Returns:
            Fill details or error dict.
        """
        return self._execute_order(symbol, "SELL", shares)

    def _execute_order(self, symbol: str, action: str, shares: int) -> FillResult:
        """
        Execute a market order.

        Args:
            symbol: Stock symbol.
            action: "BUY" or "SELL".
            shares: Number of shares.

        Returns:
            Fill details or error dict.
        """
        if not self._ib or not self._ib.isConnected():
            return {"success": False, "error": "Not connected"}

        try:
            from ib_insync import MarketOrder

            contract = self._get_contract(symbol)
            order = MarketOrder(action, shares)

            trade = self._ib.placeOrder(contract, order)

            # Wait for fill (up to 30 seconds)
            timeout = 30
            while not trade.isDone() and timeout > 0:
                self._ib.sleep(1)
                timeout -= 1

            if trade.orderStatus.status == "Filled":
                return {
                    "success": True,
                    "fill_price": trade.orderStatus.avgFillPrice,
                    "fill_shares": int(trade.orderStatus.filled),
                    "commission": self._get_commission(trade),
                }
            else:
                return {
                    "success": False,
                    "error": f"Order not filled: {trade.orderStatus.status}",
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_commission(self, trade) -> float:
        """Extract commission from trade fills."""
        total = 0.0
        for fill in trade.fills:
            if fill.commissionReport:
                total += fill.commissionReport.commission or 0.0
        return total

    def fetch_quote(self, symbol: str, eod_last_price: float | None) -> Quote | None:
        """
        Fetch a real-time quote from TWS/Gateway.

        Args:
            symbol: Stock symbol (e.g., "AAPL").
            eod_last_price: EOD close from TradeTracer (unused, real data
                is fetched from the broker).

        Returns:
            Quote dict with OHLCV and bid/ask, or None if unavailable.
        """
        if not self._ib or not self._ib.isConnected():
            return None

        try:
            contract = self._get_contract(symbol)

            # Request market data snapshot
            self._ib.qualifyContracts(contract)
            ticker = self._ib.reqMktData(contract, snapshot=True)

            # Wait for data (up to 5 seconds)
            timeout = 5
            while ticker.last != ticker.last and timeout > 0:  # NaN check
                self._ib.sleep(0.5)
                timeout -= 0.5

            # Check if we have valid data
            if not _is_valid(ticker.last) and not _is_valid(ticker.bid):
                return None

            return {
                "open": _safe_float(ticker.open),
                "high": _safe_float(ticker.high),
                "low": _safe_float(ticker.low),
                "close": _safe_float(ticker.last),
                "volume": _safe_int(ticker.volume),
                "bid": _safe_float(ticker.bid),
                "ask": _safe_float(ticker.ask),
            }

        except Exception as e:
            print(f"[WARN] Failed to get quote for {symbol}: {e}")
            return None


def _is_valid(value: Any) -> bool:
    """Check if value is valid (not None, not NaN)."""
    if value is None:
        return False
    try:
        import math

        return not math.isnan(value)
    except (TypeError, ValueError):
        return False


def _safe_float(value: Any) -> float | None:
    """Convert to float, returning None for invalid values."""
    if not _is_valid(value):
        return None
    return float(value)


def _safe_int(value: Any) -> int | None:
    """Convert to int, returning None for invalid values."""
    if not _is_valid(value):
        return None
    return int(value)
